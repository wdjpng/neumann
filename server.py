from flask import Flask, jsonify, send_from_directory, request, send_file, abort
import asyncio
import io
import json
import os
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image
import pymupdf

import chunk_extractor
import text_extractor
import extraction_pipeline

app = Flask(__name__, static_folder='public')

# Track debug mode
DEBUG_MODE = False


@app.route('/')
def index():
    return send_from_directory('public', 'index.html')


@app.route('/favicon.ico')
def favicon():
    return '', 204


@app.route('/<path:path>')
def serve_public(path):
    return send_from_directory('public', path)


@app.route('/api/letters')
def get_letters():
    # Get all letters from outputs_gpt-5_2 directory
    outputs_dir = os.path.join('public', 'outputs_gpt-5_2')
    letters = []
    if os.path.exists(outputs_dir):
        for entry in os.listdir(outputs_dir):
            entry_path = os.path.join(outputs_dir, entry)
            if os.path.isdir(entry_path):
                # Check if letter.pdf exists in this directory
                if os.path.exists(os.path.join(entry_path, 'letter.pdf')):
                    letters.append(entry)
    letters.sort()
    return jsonify(letters)


@app.route('/api/metadata')
def get_metadata():
    metadata_path = os.path.join('public', 'metadata', 'metadata.json')
    if os.path.exists(metadata_path):
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        return jsonify(metadata)
    return jsonify({})


@app.route('/api/debug-mode')
def get_debug_mode():
    return jsonify({'debug': DEBUG_MODE})


@app.route('/api/html-parts/<letter_id>')
def get_html_parts(letter_id):
    html_parts_dir = os.path.join('public', 'html_parts')
    if not os.path.exists(html_parts_dir):
        return jsonify([])
    matching_files = [f for f in os.listdir(html_parts_dir)
                      if f.startswith(letter_id) and f.endswith('.html')]
    matching_files.sort()
    return jsonify(matching_files)


@app.route('/api/html-files/<letter_id>')
def get_html_files(letter_id):
    result = {}
    # Check in outputs_gpt-5_2 directory
    outputs_dir = os.path.join('public', 'outputs_gpt-5_2', letter_id)
    html_de_path = os.path.join(outputs_dir, 'html_de.html')
    if os.path.exists(html_de_path):
        result['html_de'] = 'html_de.html'
    html_en_path = os.path.join(outputs_dir, 'html_en.html')
    if os.path.exists(html_en_path):
        result['html_en'] = 'html_en.html'
    return jsonify(result)


@app.route('/api/chunks/<letter_id>')
def get_chunks(letter_id):
    chunks_dir = os.path.join('public', 'chunks')
    if not os.path.exists(chunks_dir):
        return jsonify([])
    matching_chunks = [f for f in os.listdir(chunks_dir)
                       if f.startswith(letter_id) and f.endswith('.jpg')]
    matching_chunks.sort()
    return jsonify(matching_chunks)


# ===== QC API =====

PUBLIC_ROOT = Path('public')
DEFAULT_BASE = PUBLIC_ROOT / 'outputs_gpt-5'
REVIEW_STATE_FILE = 'review_state.json'

TASKS: Dict[str, Dict[str, Any]] = {}
TASKS_LOCK = threading.Lock()


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + 'Z'


def _add_task_record(name: str, meta: Optional[Dict[str, Any]]) -> str:
    task_id = str(uuid.uuid4())
    rec = {
        'id': task_id,
        'name': name,
        'status': 'queued',
        'created_at': _now_iso(),
        'started_at': None,
        'finished_at': None,
        'meta': meta or {},
        'error': None,
    }
    with TASKS_LOCK:
        TASKS[task_id] = rec
    return task_id


def _update_task(task_id: str, **updates: Any) -> None:
    with TASKS_LOCK:
        if task_id in TASKS:
            TASKS[task_id].update(updates)


def _run_in_background(name: str, target, *, meta: Optional[Dict[str, Any]] = None) -> str:
    task_id = _add_task_record(name, meta or {})

    def runner():
        _update_task(task_id, status='running', started_at=_now_iso())
        try:
            target()
            _update_task(task_id, status='done', finished_at=_now_iso())
        except Exception as exc:  # pragma: no cover - background safety
            _update_task(task_id, status='error', finished_at=_now_iso(), error=str(exc))

    threading.Thread(target=runner, daemon=True).start()
    return task_id


def _list_output_bases() -> List[str]:
    if not PUBLIC_ROOT.exists():
        return []
    bases = [p.name for p in PUBLIC_ROOT.iterdir()
             if p.is_dir() and p.name.startswith('outputs')]
    bases.sort()
    return bases


def _resolve_base() -> Tuple[Path, str]:
    requested = request.args.get('base')
    bases = _list_output_bases()
    if requested in bases:
        return PUBLIC_ROOT / requested, requested
    if DEFAULT_BASE.name in bases:
        return DEFAULT_BASE, DEFAULT_BASE.name
    if bases:
        return PUBLIC_ROOT / bases[0], bases[0]
    return DEFAULT_BASE, DEFAULT_BASE.name


def _public_url(path: Optional[Path]) -> Optional[str]:
    if not path or not path.exists():
        return None
    try:
        rel = path.relative_to(PUBLIC_ROOT)
        return '/' + rel.as_posix()
    except ValueError:
        return None


def _load_review_state(letter_dir: Path) -> Dict[str, Any]:
    state_path = letter_dir / REVIEW_STATE_FILE
    if state_path.exists():
        try:
            return json.loads(state_path.read_text())
        except Exception:
            return {}
    return {}


def _save_review_state(letter_dir: Path, state: Dict[str, Any]) -> None:
    letter_dir.mkdir(parents=True, exist_ok=True)
    (letter_dir / REVIEW_STATE_FILE).write_text(json.dumps(state, indent=2))


def _find_pdf_for_letter(base_path: Path, letter: str) -> Optional[Path]:
    letter_dir = base_path / letter
    candidates: List[Path] = [
        base_path / f'{letter}.pdf',
        letter_dir / f'{letter}.pdf',
        letter_dir / 'letter.pdf',
    ]
    if letter_dir.exists():
        candidates.extend(sorted(letter_dir.glob('*.pdf')))
        candidates.extend(sorted(letter_dir.glob('*.PDF')))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    fallback = PUBLIC_ROOT / 'samples' / f'{letter}.pdf'
    return fallback if fallback.exists() else None


def _ensure_pages_rendered(letter_dir: Path, base_path: Path, letter: str) -> bool:
    pages_dir = letter_dir / 'pages'
    try:
        if pages_dir.exists() and any(pages_dir.glob('page_*.png')):
            return True
        pages_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = _find_pdf_for_letter(base_path, letter)
        if not pdf_path:
            return False
        with pymupdf.open(pdf_path) as pdf:
            matrix = pymupdf.Matrix(4.167, 4.167)
            for idx, page in enumerate(pdf):
                pix = page.get_pixmap(matrix=matrix)
                (pages_dir / f'page_{idx+1}.png').write_bytes(pix.tobytes('png'))
        return True
    except Exception:
        return False


def _load_coords_file(chunks_dir: Path, page_index: int) -> List[Tuple[int, int, int, int]]:
    coords_path = chunks_dir / f'{page_index}_chunk_coords.txt'
    coords: List[Tuple[int, int, int, int]] = []
    if coords_path.exists():
        with coords_path.open('r') as fh:
            for line in fh:
                parts = [part.strip() for part in line.split(',')]
                if len(parts) != 4:
                    continue
                try:
                    x1, y1, x2, y2 = (int(p) for p in parts)
                except ValueError:
                    continue
                coords.append((x1, y1, x2, y2))
    return coords


def _coords_to_payload(coords: List[Tuple[int, int, int, int]], page_index: int) -> List[Dict[str, Any]]:
    payload: List[Dict[str, Any]] = []
    for idx, (x1, y1, x2, y2) in enumerate(coords):
        payload.append({
            'id': f'{page_index}_{idx}',
            'chunk_index': idx,
            'x1': x1,
            'y1': y1,
            'x2': x2,
            'y2': y2,
        })
    return payload


def _count_chunks(letter_dir: Path) -> int:
    chunks_dir = letter_dir / 'chunks'
    if not chunks_dir.exists():
        return 0
    total = 0
    for coords_file in chunks_dir.glob('*_chunk_coords.txt'):
        try:
            with coords_file.open('r') as fh:
                total += sum(1 for line in fh if line.strip())
        except Exception:
            continue
    return total


def _letter_needs_rebuild(letter_dir: Path) -> bool:
    chunks_dir = letter_dir / 'chunks'
    de_path = letter_dir / 'html_de.html'
    if not chunks_dir.exists():
        return False
    latest_chunk_mtime = 0.0
    for html_file in chunks_dir.glob('*_*.html'):
        try:
            latest_chunk_mtime = max(latest_chunk_mtime, os.path.getmtime(html_file))
        except Exception:
            continue
    try:
        de_mtime = os.path.getmtime(de_path) if de_path.exists() else 0.0
    except Exception:
        de_mtime = 0.0
    return latest_chunk_mtime > de_mtime or not de_path.exists()


def _letter_needs_translate(letter_dir: Path) -> bool:
    de_path = letter_dir / 'html_de.html'
    en_path = letter_dir / 'html_en.html'
    if not de_path.exists():
        return False
    try:
        de_mtime = os.path.getmtime(de_path)
        en_mtime = os.path.getmtime(en_path) if en_path.exists() else 0.0
    except Exception:
        return True
    return en_mtime < de_mtime


def _letter_summary(base_path: Path, letter: str) -> Dict[str, Any]:
    letter_dir = base_path / letter
    state = _load_review_state(letter_dir)
    pages_dir = letter_dir / 'pages'
    page_count = 0
    if pages_dir.exists():
        page_count = sum(1 for _ in pages_dir.glob('page_*.png'))
    html_de_path = letter_dir / 'html_de.html'
    html_en_path = letter_dir / 'html_en.html'
    summary = {
        'id': letter,
        'label': letter,
        'page_count': page_count,
        'chunk_count': _count_chunks(letter_dir),
        'finished': bool(state.get('approved_pdf')),
        'html_de_mtime': os.path.getmtime(html_de_path) if html_de_path.exists() else 0.0,
        'html_en_mtime': os.path.getmtime(html_en_path) if html_en_path.exists() else 0.0,
        'needs_rebuild': _letter_needs_rebuild(letter_dir),
        'needs_translate': _letter_needs_translate(letter_dir),
        'pdf_url': _public_url(_find_pdf_for_letter(base_path, letter)),
    }
    reasoning_path = letter_dir / 'reasoning_in_unite_html.txt'
    summary['reasoning_url'] = _public_url(reasoning_path) if reasoning_path.exists() else None
    return summary


def _gather_pages_payload(letter_dir: Path, base_path: Path, letter: str) -> List[Dict[str, Any]]:
    if not _ensure_pages_rendered(letter_dir, base_path, letter):
        return []
    pages_dir = letter_dir / 'pages'
    chunks_dir = letter_dir / 'chunks'
    payload: List[Dict[str, Any]] = []
    if not pages_dir.exists():
        return payload
    for page_path in sorted(pages_dir.glob('page_*.png')):
        try:
            idx = int(page_path.stem.split('_')[1]) - 1
        except (IndexError, ValueError):
            continue
        coords = _load_coords_file(chunks_dir, idx)
        coords_payload = _coords_to_payload(coords, idx)
        with Image.open(page_path) as img:
            width, height = img.size
        payload.append({
            'index': idx,
            'image_url': _public_url(page_path),
            'size': {'width': width, 'height': height},
            'coords': coords_payload,
            'chunk_count': len(coords_payload),
            'reasoning_url': _public_url(letter_dir / 'chunks' / f'page_{idx+1}.txt'),
        })
    payload.sort(key=lambda item: item['index'])
    return payload


def _collect_chunk_metadata(letter_dir: Path) -> List[Dict[str, Any]]:
    chunks_dir = letter_dir / 'chunks'
    if not chunks_dir.exists():
        return []
    state = _load_review_state(letter_dir)
    approved_map = state.get('chunks') or {}
    entries: List[Dict[str, Any]] = []
    for coords_file in sorted(chunks_dir.glob('*_chunk_coords.txt'),
                              key=lambda p: int(p.stem.split('_')[0])):
        try:
            page_idx = int(coords_file.stem.split('_')[0])
        except ValueError:
            continue
        try:
            with coords_file.open('r') as fh:
                lines = [ln for ln in fh.read().splitlines() if ln.strip()]
        except Exception:
            lines = []
        for chunk_idx in range(len(lines)):
            image_path = chunks_dir / f'{page_idx}_chunk_{chunk_idx+1}.png'
            html_path = chunks_dir / f'{page_idx}_{chunk_idx}.html'
            reasoning_txt = chunks_dir / f'{page_idx}_{chunk_idx}_reasoning.txt'
            reasoning_html = chunks_dir / f'{page_idx}_{chunk_idx}_reasoning.html'
            reasoning_path = reasoning_txt if reasoning_txt.exists() else (
                reasoning_html if reasoning_html.exists() else None
            )
            html_mtime = os.path.getmtime(html_path) if html_path.exists() else 0.0
            key = f'{page_idx}_{chunk_idx}'
            approved = approved_map.get(key, 0) == html_mtime and html_mtime != 0
            entries.append({
                'page_index': page_idx,
                'chunk_index': chunk_idx,
                'id': key,
                'image_url': _public_url(image_path),
                'html_url': _public_url(html_path),
                'reasoning_url': _public_url(reasoning_path) if reasoning_path else None,
                'html_mtime': html_mtime,
                'approved': approved,
            })
    entries.sort(key=lambda item: (item['page_index'], item['chunk_index']))
    return entries


def _normalize_coords_payload(coords_payload: List[Dict[str, Any]]) -> List[Tuple[int, int, int, int]]:
    coords: List[Tuple[int, int, int, int]] = []
    for entry in coords_payload:
        try:
            x1 = int(entry['x1'])
            y1 = int(entry['y1'])
            x2 = int(entry['x2'])
            y2 = int(entry['y2'])
        except (KeyError, TypeError, ValueError):
            raise ValueError('Invalid coordinate entry')
        coords.append((x1, y1, x2, y2))
    return coords


def _clear_page_artifacts(chunks_dir: Path, page_index: int) -> None:
    patterns = [
        f'{page_index}_chunk_*.png',
        f'{page_index}_*.html',
        f'{page_index}_*_reasoning.*',
    ]
    for pattern in patterns:
        for path in chunks_dir.glob(pattern):
            try:
                path.unlink()
            except Exception:
                continue


async def _async_rebuild_unified(letter_dir: Path, feedback: str = '') -> None:
    chunks_dir = letter_dir / 'chunks'
    page0 = letter_dir / 'pages' / 'page_1.png'
    if not page0.exists():
        return
    html_chunks: List[str] = []
    for html_file in sorted(chunks_dir.glob('*_*.html')):
        try:
            html_chunks.append(html_file.read_text())
        except Exception:
            continue
    if not html_chunks:
        return
    with Image.open(page0) as first_page:
        html_de, reasoning = await text_extractor.unite_html(html_chunks, first_page, feedback=feedback)
    (letter_dir / 'reasoning_in_unite_html.txt').write_text(reasoning)
    (letter_dir / 'html_de.html').write_text(html_de)


def _enqueue_update_chunks(letter_dir: Path, base_path: Path, base_name: str,
                           letter: str, page_index: int,
                           coords: List[Tuple[int, int, int, int]],
                           rebuild: bool, feedback: str) -> str:
    chunks_dir = letter_dir / 'chunks'
    pages_dir = letter_dir / 'pages'
    pages_dir.mkdir(parents=True, exist_ok=True)
    if not (pages_dir / f'page_{page_index+1}.png').exists():
        if not _ensure_pages_rendered(letter_dir, base_path, letter):
            abort(404, 'Page image not found')
    page_img_path = pages_dir / f'page_{page_index+1}.png'
    if not page_img_path.exists():
        abort(404, 'Page image not found')
    coords_path = chunks_dir / f'{page_index}_chunk_coords.txt'
    chunks_dir.mkdir(parents=True, exist_ok=True)

    def task():
        ordered_coords = sorted(coords, key=lambda tup: (tup[1], tup[0]))
        with coords_path.open('w') as fh:
            for x1, y1, x2, y2 in ordered_coords:
                fh.write(f'{x1},{y1},{x2},{y2}\n')
        _clear_page_artifacts(chunks_dir, page_index)
        with Image.open(page_img_path) as page_img:
            pil_chunks = chunk_extractor.save_chunks(page_img, ordered_coords, letter_dir, page_index)

        async def run():
            results = await asyncio.gather(*[text_extractor.transcribe_chunk(img) for img in pil_chunks])
            for idx, (html, reasoning) in enumerate(results):
                (chunks_dir / f'{page_index}_{idx}.html').write_text(html)
                (chunks_dir / f'{page_index}_{idx}_reasoning.txt').write_text(reasoning)
            if rebuild:
                await _async_rebuild_unified(letter_dir, feedback)

        asyncio.run(run())

    name = f'Update chunks — {letter} p{page_index+1}'
    if rebuild:
        name = f'Update chunks + Rebuild — {letter} p{page_index+1}'
    return _run_in_background(
        name=name,
        target=task,
        meta={'base': base_name, 'letter': letter, 'page_index': page_index}
    )


def _enqueue_regenerate(letter_dir: Path, base_path: Path, base_name: str,
                        letter: str, page_index: int) -> str:
    pages_dir = letter_dir / 'pages'
    if not (pages_dir / f'page_{page_index+1}.png').exists():
        if not _ensure_pages_rendered(letter_dir, base_path, letter):
            abort(404, 'Page image not found')
    page_img_path = pages_dir / f'page_{page_index+1}.png'
    if not page_img_path.exists():
        abort(404, 'Page image not found')
    chunks_dir = letter_dir / 'chunks'
    chunks_dir.mkdir(parents=True, exist_ok=True)
    reasoning_path = chunks_dir / f'page_{page_index+1}.txt'

    def task():
        with Image.open(page_img_path) as page_image:
            async def run_generation():
                return await chunk_extractor.get_chunks_coords_from_image(page_image, reasoning_path)

            coords = asyncio.run(run_generation())
        ordered_coords = sorted(coords, key=lambda tup: (tup[1], tup[0]))
        coords_path = chunks_dir / f'{page_index}_chunk_coords.txt'
        with coords_path.open('w') as fh:
            for x1, y1, x2, y2 in ordered_coords:
                fh.write(f'{x1},{y1},{x2},{y2}\n')
        _clear_page_artifacts(chunks_dir, page_index)
        with Image.open(page_img_path) as page_image_for_crop:
            pil_chunks = chunk_extractor.save_chunks(page_image_for_crop, ordered_coords, letter_dir, page_index)

        async def run():
            results = await asyncio.gather(*[text_extractor.transcribe_chunk(img) for img in pil_chunks])
            for idx, (html, reasoning) in enumerate(results):
                (chunks_dir / f'{page_index}_{idx}.html').write_text(html)
                (chunks_dir / f'{page_index}_{idx}_reasoning.txt').write_text(reasoning)

        asyncio.run(run())

    return _run_in_background(
        name=f'Regenerate chunks — {letter} p{page_index+1}',
        target=task,
        meta={'base': base_name, 'letter': letter, 'page_index': page_index}
    )


def _get_chunk_detail(letter_dir: Path, page_index: int, chunk_index: int) -> Dict[str, Any]:
    chunks_dir = letter_dir / 'chunks'
    image_path = chunks_dir / f'{page_index}_chunk_{chunk_index+1}.png'
    html_path = chunks_dir / f'{page_index}_{chunk_index}.html'
    reasoning_txt = chunks_dir / f'{page_index}_{chunk_index}_reasoning.txt'
    reasoning_html = chunks_dir / f'{page_index}_{chunk_index}_reasoning.html'
    if reasoning_txt.exists():
        reasoning = reasoning_txt.read_text()
    elif reasoning_html.exists():
        reasoning = reasoning_html.read_text()
    else:
        reasoning = ''
    html = html_path.read_text() if html_path.exists() else ''
    mtime = os.path.getmtime(html_path) if html_path.exists() else 0.0
    state = _load_review_state(letter_dir)
    approved_map = state.get('chunks') or {}
    key = f'{page_index}_{chunk_index}'
    approved = approved_map.get(key, 0) == mtime and mtime != 0
    return {
        'page_index': page_index,
        'chunk_index': chunk_index,
        'image_url': _public_url(image_path),
        'html': html,
        'reasoning': reasoning,
        'html_mtime': mtime,
        'approved': approved,
    }


def _save_chunk_html(letter_dir: Path, page_index: int, chunk_index: int, html: str) -> float:
    chunks_dir = letter_dir / 'chunks'
    chunks_dir.mkdir(parents=True, exist_ok=True)
    html_file = chunks_dir / f'{page_index}_{chunk_index}.html'
    html_file.write_text(html)
    return os.path.getmtime(html_file)


def _approve_chunk(letter_dir: Path, page_index: int, chunk_index: int) -> float:
    chunks_dir = letter_dir / 'chunks'
    html_file = chunks_dir / f'{page_index}_{chunk_index}.html'
    if not html_file.exists():
        abort(404, 'Chunk HTML not found')
    mtime = os.path.getmtime(html_file)
    state = _load_review_state(letter_dir)
    state.setdefault('chunks', {})[f'{page_index}_{chunk_index}'] = mtime
    _save_review_state(letter_dir, state)
    return mtime


def _unapprove_chunk(letter_dir: Path, page_index: int, chunk_index: int) -> None:
    state = _load_review_state(letter_dir)
    chunks_map = state.get('chunks') or {}
    key = f'{page_index}_{chunk_index}'
    if key in chunks_map:
        del chunks_map[key]
        state['chunks'] = chunks_map
        _save_review_state(letter_dir, state)


def _enqueue_retry_chunk(letter_dir: Path, base_name: str, letter: str,
                         page_index: int, chunk_index: int, feedback: str) -> str:
    chunks_dir = letter_dir / 'chunks'
    img_path = chunks_dir / f'{page_index}_chunk_{chunk_index+1}.png'
    if not img_path.exists():
        abort(404, 'Chunk image not found')

    def task():
        with Image.open(img_path) as img:
            async def run():
                html, reasoning = await text_extractor.transcribe_chunk(img, feedback=feedback)
                (chunks_dir / f'{page_index}_{chunk_index}.html').write_text(html)
                (chunks_dir / f'{page_index}_{chunk_index}_reasoning.txt').write_text(reasoning)

            asyncio.run(run())

    return _run_in_background(
        name=f'Retry chunk — {letter} p{page_index+1} c{chunk_index+1}',
        target=task,
        meta={'base': base_name, 'letter': letter, 'page_index': page_index, 'chunk_index': chunk_index}
    )


def _get_html_payload(letter_dir: Path, lang: str) -> Dict[str, Any]:
    path = letter_dir / f'html_{lang}.html'
    if not path.exists():
        return {'html': '', 'mtime': 0.0}
    return {'html': path.read_text(), 'mtime': os.path.getmtime(path)}


def _get_html_meta(letter_dir: Path, lang: str) -> Dict[str, Any]:
    path = letter_dir / f'html_{lang}.html'
    return {
        'exists': path.exists(),
        'mtime': os.path.getmtime(path) if path.exists() else 0.0,
        'url': _public_url(path),
    }


def _save_html(letter_dir: Path, lang: str, html: str) -> float:
    path = letter_dir / f'html_{lang}.html'
    letter_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(html)
    return os.path.getmtime(path)


def _approve_html(letter_dir: Path, lang: str) -> float:
    path = letter_dir / f'html_{lang}.html'
    if not path.exists():
        abort(404, 'Not found')
    mtime = os.path.getmtime(path)
    state = _load_review_state(letter_dir)
    key = 'html_de_mtime' if lang == 'de' else 'html_en_mtime'
    state[key] = mtime
    _save_review_state(letter_dir, state)
    return mtime


def _toggle_finished(letter_dir: Path, value: Optional[bool]) -> bool:
    state = _load_review_state(letter_dir)
    current = bool(state.get('approved_pdf'))
    new_value = not current if value is None else bool(value)
    state['approved_pdf'] = new_value
    state['approved_pdf_at'] = time.time() if new_value else None
    _save_review_state(letter_dir, state)
    return new_value


@app.route('/qc')
def qc_page():
    return send_from_directory('public', 'qc.html')


@app.get('/api/qc/bases')
def qc_bases():
    return jsonify(_list_output_bases())


@app.get('/api/qc/overview')
def qc_overview():
    base_path, base_name = _resolve_base()
    letters = []
    if base_path.exists():
        for entry in sorted([p for p in base_path.iterdir() if p.is_dir()], key=lambda p: p.name.lower()):
            letters.append(_letter_summary(base_path, entry.name))
    return jsonify({
        'base': base_name,
        'bases': _list_output_bases(),
        'letters': letters,
    })


@app.get('/api/qc/tasks')
def qc_tasks_list():
    base_filter = request.args.get('base')
    letter_filter = request.args.get('letter')
    with TASKS_LOCK:
        tasks = list(TASKS.values())
    if base_filter:
        tasks = [t for t in tasks if t.get('meta', {}).get('base') == base_filter]
    if letter_filter:
        tasks = [t for t in tasks if t.get('meta', {}).get('letter') == letter_filter]
    tasks.sort(key=lambda t: t.get('started_at') or t.get('created_at') or '', reverse=True)
    return jsonify({'tasks': tasks[:200]})


@app.get('/api/qc/tasks/<task_id>')
def qc_task_detail(task_id):
    with TASKS_LOCK:
        info = TASKS.get(task_id)
    if not info:
        return ('Not found', 404)
    return jsonify(info)


@app.get('/api/qc/letter/<letter>/context')
def qc_letter_context(letter):
    base_path, base_name = _resolve_base()
    letter_dir = base_path / letter
    if not letter_dir.exists():
        abort(404, 'Letter not found')
    pages = _gather_pages_payload(letter_dir, base_path, letter)
    chunks = _collect_chunk_metadata(letter_dir)
    state = _load_review_state(letter_dir)
    return jsonify({
        'letter': letter,
        'base': base_name,
        'pages': pages,
        'chunks': chunks,
        'finished': bool(state.get('approved_pdf')),
        'html_de': _get_html_meta(letter_dir, 'de'),
        'html_en': _get_html_meta(letter_dir, 'en'),
        'pdf_url': _public_url(_find_pdf_for_letter(base_path, letter)),
        'reasoning_unified_url': _public_url(letter_dir / 'reasoning_in_unite_html.txt'),
    })


@app.get('/api/qc/letter/<letter>/pages')
def qc_letter_pages(letter):
    base_path, _base_name = _resolve_base()
    letter_dir = base_path / letter
    if not letter_dir.exists():
        abort(404, 'Letter not found')
    pages = _gather_pages_payload(letter_dir, base_path, letter)
    return jsonify({'pages': pages})


@app.get('/api/qc/letter/<letter>/pages/<int:page_index>/coords')
def qc_page_coords(letter, page_index):
    base_path, _base_name = _resolve_base()
    letter_dir = base_path / letter
    if not letter_dir.exists():
        abort(404, 'Letter not found')
    coords = _coords_to_payload(_load_coords_file(letter_dir / 'chunks', page_index), page_index)
    return jsonify({'coords': coords})


@app.post('/api/qc/letter/<letter>/pages/<int:page_index>/update')
def qc_update_page(letter, page_index):
    data = request.get_json(force=True)
    coords_payload = data.get('coords')
    if not isinstance(coords_payload, list):
        abort(400, 'Invalid coords payload')
    try:
        coords = _normalize_coords_payload(coords_payload)
    except ValueError as exc:
        abort(400, str(exc))
    rebuild = bool(data.get('rebuild', False))
    feedback = data.get('feedback', '')
    base_path, base_name = _resolve_base()
    letter_dir = base_path / letter
    if not letter_dir.exists():
        abort(404, 'Letter not found')
    task_id = _enqueue_update_chunks(letter_dir, base_path, base_name, letter, page_index, coords, rebuild, feedback)
    return jsonify({'status': 'queued', 'task_id': task_id})


@app.post('/api/qc/letter/<letter>/pages/<int:page_index>/regenerate')
def qc_regenerate_page(letter, page_index):
    base_path, base_name = _resolve_base()
    letter_dir = base_path / letter
    if not letter_dir.exists():
        abort(404, 'Letter not found')
    task_id = _enqueue_regenerate(letter_dir, base_path, base_name, letter, page_index)
    return jsonify({'status': 'queued', 'task_id': task_id})


@app.get('/api/qc/letter/<letter>/page/<int:page_index>/reasoning')
def qc_page_reasoning(letter, page_index):
    base_path, _base_name = _resolve_base()
    letter_dir = base_path / letter
    if not letter_dir.exists():
        abort(404, 'Letter not found')
    reason_path = letter_dir / 'chunks' / f'page_{page_index+1}.txt'
    if not reason_path.exists():
        return jsonify({'reasoning': ''})
    return jsonify({'reasoning': reason_path.read_text()})


@app.get('/api/qc/letter/<letter>/page/<int:page_index>/overlay.png')
def qc_page_overlay(letter, page_index):
    base_path, _base_name = _resolve_base()
    letter_dir = base_path / letter
    if not letter_dir.exists():
        abort(404, 'Letter not found')
    pages_dir = letter_dir / 'pages'
    chunks_dir = letter_dir / 'chunks'
    if not (pages_dir / f'page_{page_index+1}.png').exists():
        if not _ensure_pages_rendered(letter_dir, base_path, letter):
            abort(404, 'Page image not found')
    page_path = pages_dir / f'page_{page_index+1}.png'
    coords = _load_coords_file(chunks_dir, page_index)
    if not page_path.exists() or not coords:
        abort(404, 'Not found')
    image = Image.open(page_path)
    overlay = chunk_extractor.draw_chunks_borders(image, coords)
    buf = io.BytesIO()
    overlay.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')


@app.get('/api/qc/letter/<letter>/chunks')
def qc_chunks(letter):
    base_path, _base_name = _resolve_base()
    letter_dir = base_path / letter
    if not letter_dir.exists():
        abort(404, 'Letter not found')
    chunks = _collect_chunk_metadata(letter_dir)
    return jsonify({'chunks': chunks})


@app.get('/api/qc/letter/<letter>/chunk/<int:page_index>/<int:chunk_index>')
def qc_chunk_detail(letter, page_index, chunk_index):
    base_path, _base_name = _resolve_base()
    letter_dir = base_path / letter
    if not letter_dir.exists():
        abort(404, 'Letter not found')
    detail = _get_chunk_detail(letter_dir, page_index, chunk_index)
    return jsonify(detail)


@app.post('/api/qc/letter/<letter>/chunk/<int:page_index>/<int:chunk_index>/save')
def qc_chunk_save(letter, page_index, chunk_index):
    data = request.get_json(force=True)
    html = data.get('html', '')
    base_path, _base_name = _resolve_base()
    letter_dir = base_path / letter
    if not letter_dir.exists():
        abort(404, 'Letter not found')
    mtime = _save_chunk_html(letter_dir, page_index, chunk_index, html)
    return jsonify({'status': 'ok', 'html_mtime': mtime})


@app.post('/api/qc/letter/<letter>/chunk/<int:page_index>/<int:chunk_index>/approve')
def qc_chunk_approve(letter, page_index, chunk_index):
    base_path, _base_name = _resolve_base()
    letter_dir = base_path / letter
    if not letter_dir.exists():
        abort(404, 'Letter not found')
    mtime = _approve_chunk(letter_dir, page_index, chunk_index)
    return jsonify({'status': 'ok', 'approved_mtime': mtime})


@app.post('/api/qc/letter/<letter>/chunk/<int:page_index>/<int:chunk_index>/unapprove')
def qc_chunk_unapprove(letter, page_index, chunk_index):
    base_path, _base_name = _resolve_base()
    letter_dir = base_path / letter
    if not letter_dir.exists():
        abort(404, 'Letter not found')
    _unapprove_chunk(letter_dir, page_index, chunk_index)
    return jsonify({'status': 'ok'})


@app.post('/api/qc/letter/<letter>/chunk/<int:page_index>/<int:chunk_index>/retry')
def qc_chunk_retry(letter, page_index, chunk_index):
    data = request.get_json(silent=True) or {}
    feedback = data.get('feedback', '')
    base_path, base_name = _resolve_base()
    letter_dir = base_path / letter
    if not letter_dir.exists():
        abort(404, 'Letter not found')
    task_id = _enqueue_retry_chunk(letter_dir, base_name, letter, page_index, chunk_index, feedback)
    return jsonify({'status': 'queued', 'task_id': task_id})


@app.get('/api/qc/letter/<letter>/html/<lang>')
def qc_html_get(letter, lang):
    if lang not in ('de', 'en'):
        abort(400, 'Invalid language')
    base_path, _base_name = _resolve_base()
    letter_dir = base_path / letter
    if not letter_dir.exists():
        abort(404, 'Letter not found')
    payload = _get_html_payload(letter_dir, lang)
    return jsonify(payload)


@app.post('/api/qc/letter/<letter>/html/<lang>')
def qc_html_save(letter, lang):
    if lang not in ('de', 'en'):
        abort(400, 'Invalid language')
    data = request.get_json(force=True)
    html = data.get('html', '')
    base_path, _base_name = _resolve_base()
    letter_dir = base_path / letter
    if not letter_dir.exists():
        abort(404, 'Letter not found')
    mtime = _save_html(letter_dir, lang, html)
    return jsonify({'status': 'ok', 'mtime': mtime})


@app.post('/api/qc/letter/<letter>/html/<lang>/approve')
def qc_html_approve(letter, lang):
    if lang not in ('de', 'en'):
        abort(400, 'Invalid language')
    base_path, _base_name = _resolve_base()
    letter_dir = base_path / letter
    if not letter_dir.exists():
        abort(404, 'Letter not found')
    mtime = _approve_html(letter_dir, lang)
    return jsonify({'status': 'ok', 'approved_mtime': mtime})


@app.post('/api/qc/letter/<letter>/rebuild')
def qc_rebuild_letter(letter):
    data = request.get_json(silent=True) or {}
    feedback = data.get('feedback', '')
    base_path, base_name = _resolve_base()
    letter_dir = base_path / letter
    if not letter_dir.exists():
        abort(404, 'Letter not found')

    def task():
        async def run():
            await _async_rebuild_unified(letter_dir, feedback)

        asyncio.run(run())

    task_id = _run_in_background(
        name=f'Rebuild HTML — {letter}',
        target=task,
        meta={'base': base_name, 'letter': letter}
    )
    return jsonify({'status': 'queued', 'task_id': task_id})


@app.post('/api/qc/batch/rebuild_changed')
def qc_rebuild_all_changed():
    base_path, base_name = _resolve_base()
    tasks = []
    if base_path.exists():
        for letter_dir in sorted([p for p in base_path.iterdir() if p.is_dir()], key=lambda p: p.name.lower()):
            if not _letter_needs_rebuild(letter_dir):
                continue

            def make_task(letter=letter_dir.name, letter_dir=letter_dir):
                def task():
                    async def run():
                        await _async_rebuild_unified(letter_dir, '')

                    asyncio.run(run())
                return task

            task_id = _run_in_background(
                name=f'Rebuild HTML — {letter_dir.name}',
                target=make_task(),
                meta={'base': base_name, 'letter': letter_dir.name}
            )
            tasks.append({'letter': letter_dir.name, 'task_id': task_id})
    return jsonify({'status': 'queued', 'tasks': tasks})


@app.post('/api/qc/letter/<letter>/translate')
def qc_translate_letter(letter):
    data = request.get_json(silent=True) or {}
    feedback = data.get('feedback', '')
    base_path, base_name = _resolve_base()
    letter_dir = base_path / letter
    if not letter_dir.exists():
        abort(404, 'Letter not found')
    html_de_path = letter_dir / 'html_de.html'
    if not html_de_path.exists():
        abort(404, 'html_de.html not found')
    original_html = html_de_path.read_text()

    def task():
        async def run():
            await text_extractor.save_and_translate_html(original_html, letter_dir, feedback=feedback)

        asyncio.run(run())

    task_id = _run_in_background(
        name=f'Translate — {letter}',
        target=task,
        meta={'base': base_name, 'letter': letter}
    )
    return jsonify({'status': 'queued', 'task_id': task_id})


@app.post('/api/qc/batch/translate_all')
def qc_translate_all():
    base_path, base_name = _resolve_base()
    tasks = []
    if base_path.exists():
        for letter_dir in sorted([p for p in base_path.iterdir() if p.is_dir()], key=lambda p: p.name.lower()):
            if not _letter_needs_translate(letter_dir):
                continue
            html_de_path = letter_dir / 'html_de.html'
            if not html_de_path.exists():
                continue
            original_html = html_de_path.read_text()

            def make_task(letter=letter_dir.name, original_html=original_html, letter_dir=letter_dir):
                def task():
                    async def run():
                        await text_extractor.save_and_translate_html(original_html, letter_dir, feedback='')

                    asyncio.run(run())
                return task

            task_id = _run_in_background(
                name=f'Translate — {letter_dir.name}',
                target=make_task(),
                meta={'base': base_name, 'letter': letter_dir.name}
            )
            tasks.append({'letter': letter_dir.name, 'task_id': task_id})
    return jsonify({'status': 'queued', 'tasks': tasks})


@app.post('/api/qc/letter/<letter>/deep_reload')
def qc_deep_reload(letter):
    base_path, base_name = _resolve_base()
    letter_dir = base_path / letter
    pdf_path = _find_pdf_for_letter(base_path, letter)
    if not pdf_path:
        abort(404, 'PDF not found')
    letter_dir.mkdir(parents=True, exist_ok=True)

    def task():
        async def run():
            with pymupdf.open(pdf_path) as pdf:
                await extraction_pipeline.process_pdf(pdf, output_path=letter_dir)
            de_path = letter_dir / 'html_de.html'
            if de_path.exists():
                await text_extractor.save_and_translate_html(de_path.read_text(), letter_dir)

        asyncio.run(run())

    task_id = _run_in_background(
        name=f'Deep reload — {letter}',
        target=task,
        meta={'base': base_name, 'letter': letter}
    )
    return jsonify({'status': 'queued', 'task_id': task_id})


@app.post('/api/qc/letter/<letter>/finished')
def qc_toggle_finished(letter):
    data = request.get_json(silent=True) or {}
    requested = data.get('value', None)
    requested_bool = None if requested is None else bool(requested)
    base_path, _base_name = _resolve_base()
    letter_dir = base_path / letter
    if not letter_dir.exists():
        abort(404, 'Letter not found')
    new_value = _toggle_finished(letter_dir, requested_bool)
    return jsonify({'status': 'ok', 'finished': new_value})


@app.get('/api/qc/letter/<letter>/review_state')
def qc_review_state(letter):
    base_path, _base_name = _resolve_base()
    letter_dir = base_path / letter
    if not letter_dir.exists():
        abort(404, 'Letter not found')
    return jsonify(_load_review_state(letter_dir))


@app.get('/api/qc/letter/<letter>/reasoning')
def qc_letter_reasoning(letter):
    base_path, _base_name = _resolve_base()
    letter_dir = base_path / letter
    if not letter_dir.exists():
        abort(404, 'Letter not found')
    reasoning_path = letter_dir / 'reasoning_in_unite_html.txt'
    if not reasoning_path.exists():
        return jsonify({'reasoning': ''})
    return jsonify({'reasoning': reasoning_path.read_text()})


if __name__ == '__main__':
    import sys
    # Check if --debug flag is passed
    DEBUG_MODE = '--debug' in sys.argv
    print(f'Starting server... (Debug mode: {DEBUG_MODE})')
    app.run(debug=DEBUG_MODE, port=5000)
