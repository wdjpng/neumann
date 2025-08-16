from flask import Flask, jsonify, send_from_directory, request, send_file
import os
import json
import io
import time
from pathlib import Path
from PIL import Image
import asyncio
import threading
import uuid
from datetime import datetime

import chunk_extractor
import text_extractor
import pymupdf
import postprocessing

app = Flask(__name__, static_folder='public')

@app.route('/')
def index():
    return send_from_directory('public', 'index.html')

@app.route('/favicon.ico')
def favicon():
    return '', 204  # No Content response for favicon

@app.route('/<path:path>')
def serve_public(path):
    return send_from_directory('public', path)

@app.route('/api/letters')
def get_letters():
    letters_dir = os.path.join('public', 'samples')
    letters = [f for f in os.listdir(letters_dir) if f.endswith('.pdf')]
    return jsonify(letters)

@app.route('/api/metadata')
def get_metadata():
    metadata_path = os.path.join('public', 'metadata', 'metadata.json')
    if os.path.exists(metadata_path):
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        return jsonify(metadata)
    return jsonify({})

@app.route('/api/html-parts/<letter_id>')
def get_html_parts(letter_id):
    """Get all HTML parts files that match the given letter ID"""
    html_parts_dir = os.path.join('public', 'html_parts')
    if not os.path.exists(html_parts_dir):
        return jsonify([])
    
    # Find all files that start with the letter_id
    matching_files = [f for f in os.listdir(html_parts_dir) 
                     if f.startswith(letter_id) and f.endswith('.html')]
    matching_files.sort()  # Sort for consistent ordering
    return jsonify(matching_files)

@app.route('/api/html-files/<letter_id>')
def get_html_files(letter_id):
    """Get HTML files from html_de and html_en directories for the given letter ID"""
    result = {}
    
    # Check html_de
    html_de_path = os.path.join('public', 'html_de', f'{letter_id}_.html')
    if os.path.exists(html_de_path):
        result['html_de'] = f'{letter_id}_.html'
    
    # Check html_en
    html_en_path = os.path.join('public', 'html_en', f'{letter_id}_.html')
    if os.path.exists(html_en_path):
        result['html_en'] = f'{letter_id}_.html'
    
    return jsonify(result)

@app.route('/api/chunks/<letter_id>')
def get_chunks(letter_id):
    """Get all image chunks that match the given letter ID"""
    chunks_dir = os.path.join('public', 'chunks')
    if not os.path.exists(chunks_dir):
        return jsonify([])
    
    # Find all files that start with the letter_id
    matching_chunks = [f for f in os.listdir(chunks_dir) 
                      if f.startswith(letter_id) and f.endswith('.jpg')]
    matching_chunks.sort()  # Sort for consistent ordering
    return jsonify(matching_chunks)

# ===== QC API =====

BASE_OUTPUTS = Path('public') / 'outputs_gpt-5'

# Lightweight background task manager
_TASKS = {}
_TASKS_LOCK = threading.Lock()

def _now_iso():
    return datetime.utcnow().isoformat() + 'Z'

def _add_task_record(name: str, meta: dict):
    task_id = str(uuid.uuid4())
    rec = {
        'id': task_id,
        'name': name,
        'status': 'queued',
        'started_at': None,
        'finished_at': None,
        'meta': meta or {},
        'error': None,
    }
    with _TASKS_LOCK:
        _TASKS[task_id] = rec
    return task_id

def _update_task(task_id: str, **updates):
    with _TASKS_LOCK:
        if task_id in _TASKS:
            _TASKS[task_id].update(updates)

def _run_in_background(name: str, target, *, meta: dict = None):
    task_id = _add_task_record(name, meta or {})
    def runner():
        _update_task(task_id, status='running', started_at=_now_iso())
        try:
            target()
            _update_task(task_id, status='done', finished_at=_now_iso())
        except Exception as e:
            _update_task(task_id, status='error', finished_at=_now_iso(), error=str(e))
    threading.Thread(target=runner, daemon=True).start()
    return task_id

def _list_output_bases():
    pub = Path('public')
    bases = [p.name for p in pub.iterdir() if p.is_dir() and p.name.startswith('outputs')]
    bases.sort()
    return bases

def _resolve_base():
    name = request.args.get('base', None)
    bases = _list_output_bases()
    if name in bases:
        return Path('public') / name, name
    # default
    return BASE_OUTPUTS, BASE_OUTPUTS.name

@app.route('/qc')
def qc_page():
    return send_from_directory('public', 'qc.html')

@app.route('/api/qc/bases')
def qc_bases():
    return jsonify(_list_output_bases())

@app.route('/api/qc/tasks')
def qc_tasks_list():
    base = request.args.get('base')
    letter = request.args.get('letter')
    with _TASKS_LOCK:
        tasks = list(_TASKS.values())
    # optional filter
    if base:
        tasks = [t for t in tasks if t.get('meta', {}).get('base') == base]
    if letter:
        tasks = [t for t in tasks if t.get('meta', {}).get('letter') == letter]
    # sort newest first
    tasks.sort(key=lambda t: (t.get('started_at') or t.get('finished_at') or ''), reverse=True)
    return jsonify({'tasks': tasks[:200]})

@app.route('/api/qc/tasks/<task_id>')
def qc_task_detail(task_id):
    with _TASKS_LOCK:
        t = _TASKS.get(task_id)
    if not t:
        return ('Not found', 404)
    return jsonify(t)

@app.route('/api/qc/letters')
def qc_letters():
    base_outputs, _base_name = _resolve_base()
    if not base_outputs.exists():
        return jsonify([])
    letters = [p.name for p in base_outputs.iterdir() if p.is_dir()]
    letters.sort()
    return jsonify(letters)

@app.route('/api/qc/letters_status')
def qc_letters_status():
    base_outputs, _base_name = _resolve_base()
    status = {}
    if base_outputs.exists():
        for p in base_outputs.iterdir():
            if p.is_dir():
                st = _load_review_state(p)
                status[p.name] = {
                    'approved_pdf': bool(st.get('approved_pdf')),
                    'html_de_mtime': st.get('html_de_mtime', 0),
                    'html_en_mtime': st.get('html_en_mtime', 0)
                }
    return jsonify(status)

@app.route('/api/qc/<letter>/approve_pdf', methods=['POST'])
def qc_approve_pdf(letter):
    base_outputs, _base_name = _resolve_base()
    letter_dir = base_outputs / letter
    state = _load_review_state(letter_dir)
    data = request.get_json(silent=True) or {}
    approved = data.get('approved', None)
    if approved is None:
        # toggle
        current = bool(state.get('approved_pdf'))
        state['approved_pdf'] = not current
    else:
        state['approved_pdf'] = bool(approved)
    state['approved_pdf_at'] = time.time() if state.get('approved_pdf') else None
    _save_review_state(letter_dir, state)
    return jsonify({'status': 'ok', 'approved': state.get('approved_pdf', False)})

def _find_pdf_for_letter(base_outputs: Path, letter: str) -> Path:
	# Try multiple common locations/names
	candidates = [
		base_outputs / f'{letter}.pdf',
		base_outputs / letter / f'{letter}.pdf',
	]
	# Any PDF inside the letter directory
	letter_dir = base_outputs / letter
	if letter_dir.exists():
		candidates.extend(sorted(letter_dir.glob('*.pdf')))
	# Any PDF in base starting with letter
	candidates.extend(sorted(base_outputs.glob(f'{letter}*.pdf')))
	for p in candidates:
		if p and p.exists():
			return p
	# Fallback to samples
	fallback = Path('public') / 'samples' / f'{letter}.pdf'
	return fallback if fallback.exists() else None

# Helper to ensure page images exist by rendering from PDF

def _ensure_pages_rendered(base_outputs: Path, letter: str) -> bool:
	letter_dir = base_outputs / letter
	pages_dir = letter_dir / 'pages'
	try:
		if pages_dir.exists() and any(pages_dir.glob('page_*.png')):
			return True
		pages_dir.mkdir(parents=True, exist_ok=True)
		pdf_path = _find_pdf_for_letter(base_outputs, letter)
		if not pdf_path:
			return False
		pdf = pymupdf.open(pdf_path)
		matrix = pymupdf.Matrix(4.167, 4.167)
		for i, page in enumerate(pdf):
			pix = page.get_pixmap(matrix=matrix)
			img_bytes = pix.tobytes('png')
			(pages_dir / f'page_{i+1}.png').write_bytes(img_bytes)
		return True
	except Exception:
		return False

@app.route('/api/qc/<letter>/pages')
def qc_pages(letter):
    base_outputs, base_name = _resolve_base()
    letter_dir = base_outputs / letter
    pages_dir = letter_dir / 'pages'
    if not pages_dir.exists() or not any(pages_dir.glob('page_*.png')):
        _ensure_pages_rendered(base_outputs, letter)
    if not pages_dir.exists():
        return jsonify([])
    pages = sorted([p.name for p in pages_dir.glob('page_*.png')])
    return jsonify([{
        'index': int(name.split('_')[1].split('.')[0]) - 1,
        'image': f'/{base_name}/{letter}/pages/{name}',
        'reasoning_txt': f'/{base_name}/{letter}/chunks/page_{int(name.split("_")[1].split(".")[0])}.txt'
    } for name in pages])

@app.route('/api/qc/<letter>/page/<int:page_index>/overlay.png')
def qc_page_overlay(letter, page_index):
    base_outputs, _base_name = _resolve_base()
    letter_dir = base_outputs / letter
    pages_dir = letter_dir / 'pages'
    if not pages_dir.exists() or not any(pages_dir.glob('page_*.png')):
        _ensure_pages_rendered(base_outputs, letter)
    page_path = letter_dir / 'pages' / f'page_{page_index+1}.png'
    coords_path = letter_dir / 'chunks' / f'{page_index}_chunk_coords.txt'
    if not page_path.exists() or not coords_path.exists():
        return ('Not found', 404)
    image = Image.open(page_path)
    coords = []
    with open(coords_path, 'r') as f:
        for line in f:
            parts = [int(x.strip()) for x in line.strip().split(',')]
            if len(parts) == 4:
                coords.append(tuple(parts))
    overlay = chunk_extractor.draw_chunks_borders(image, coords)
    buf = io.BytesIO()
    overlay.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

@app.route('/api/qc/<letter>/page/<int:page_index>/reasoning')
def qc_page_reasoning(letter, page_index):
    base_outputs, _base_name = _resolve_base()
    reason_path = base_outputs / letter / 'chunks' / f'page_{page_index+1}.txt'
    if not reason_path.exists():
        return jsonify({'reasoning': ''})
    with open(reason_path, 'r') as f:
        return jsonify({'reasoning': f.read()})

@app.route('/api/qc/<letter>/page/<int:page_index>/regenerate_chunks', methods=['POST'])
def qc_regenerate_page_chunks(letter, page_index):
    """Regenerate chunk coordinates using AI and then process chunks"""
    base_outputs, base_name = _resolve_base()
    letter_dir = base_outputs / letter
    chunks_dir = letter_dir / 'chunks'
    pages_dir = letter_dir / 'pages'
    if not pages_dir.exists() or not any(pages_dir.glob('page_*.png')):
        _ensure_pages_rendered(base_outputs, letter)
    page_img_path = pages_dir / f'page_{page_index+1}.png'
    if not page_img_path.exists():
        return ('Page image not found', 404)

    def task():
        # Load page image and regenerate coordinates using AI
        image = Image.open(page_img_path)
        reasoning_path = chunks_dir / f'page_{page_index+1}.txt'
        
        async def run_generation():
            coords = await chunk_extractor.get_chunks_coords_from_image(image, reasoning_path)
            return coords
        
        coords = asyncio.run(run_generation())
        
        # Write coords file
        coords_path = chunks_dir / f'{page_index}_chunk_coords.txt'
        with open(coords_path, 'w') as f:
            for x1, y1, x2, y2 in coords:
                f.write(f"{x1},{y1},{x2},{y2}\n")

        # Remove old chunk images and html/reasoning for this page
        for p in list(chunks_dir.glob(f'{page_index}_chunk_*.png')):
            try:
                p.unlink()
            except Exception:
                pass
        for p in list(chunks_dir.glob(f'{page_index}_*.html')):
            try:
                p.unlink()
            except Exception:
                pass
        for p in list(chunks_dir.glob(f'{page_index}_*_reasoning.*')):
            try:
                p.unlink()
            except Exception:
                pass

        # Re-crop and transcribe with new coordinates
        pil_chunks = chunk_extractor.save_chunks(image, coords, letter_dir, page_index)
        async def run_transcription():
            tasks = [text_extractor.transcribe_chunk(img) for img in pil_chunks]
            results = await asyncio.gather(*tasks)
            for j, (html, reasoning) in enumerate(results):
                (chunks_dir / f'{page_index}_{j}.html').write_text(html)
                (chunks_dir / f'{page_index}_{j}_reasoning.txt').write_text(reasoning)
        asyncio.run(run_transcription())

    task_id = _run_in_background(
        name=f'Regenerate chunks — {letter} p{page_index+1}',
        target=task,
        meta={'base': base_name, 'letter': letter, 'page_index': page_index}
    )
    return jsonify({'status': 'queued', 'task_id': task_id})

@app.route('/api/qc/<letter>/page/<int:page_index>/update_chunks', methods=['POST'])
def qc_update_page_chunks(letter, page_index):
    data = request.get_json(force=True)
    coords = data.get('coords', [])
    if not isinstance(coords, list) or not all(len(c) == 4 for c in coords):
        return ('Invalid coords', 400)
    
    base_outputs, _base_name = _resolve_base()
    letter_dir = base_outputs / letter
    chunks_dir = letter_dir / 'chunks'
    pages_dir = letter_dir / 'pages'
    if not pages_dir.exists() or not any(pages_dir.glob('page_*.png')):
        _ensure_pages_rendered(base_outputs, letter)
    page_img_path = pages_dir / f'page_{page_index+1}.png'
    if not page_img_path.exists():
        return ('Page image not found', 404)

    def task():
        # Write coords file
        coords_path = chunks_dir / f'{page_index}_chunk_coords.txt'
        with open(coords_path, 'w') as f:
            for x1, y1, x2, y2 in coords:
                f.write(f"{x1},{y1},{x2},{y2}\n")

        # Remove old chunk images and html/reasoning for this page
        for p in list(chunks_dir.glob(f'{page_index}_chunk_*.png')):
            try:
                p.unlink()
            except Exception:
                pass
        for p in list(chunks_dir.glob(f'{page_index}_*.html')):
            try:
                p.unlink()
            except Exception:
                pass
        for p in list(chunks_dir.glob(f'{page_index}_*_reasoning.*')):
            try:
                p.unlink()
            except Exception:
                pass

        # Re-crop and transcribe
        image = Image.open(page_img_path)
        pil_chunks = chunk_extractor.save_chunks(image, [(c[0],c[1],c[2],c[3]) for c in coords], letter_dir, page_index)
        async def run():
            tasks = [text_extractor.transcribe_chunk(img) for img in pil_chunks]
            results = await asyncio.gather(*tasks)
            for j, (html, reasoning) in enumerate(results):
                (chunks_dir / f'{page_index}_{j}.html').write_text(html)
                (chunks_dir / f'{page_index}_{j}_reasoning.txt').write_text(reasoning)
        asyncio.run(run())

    task_id = _run_in_background(
        name=f'Update chunks — {letter} p{page_index+1}',
        target=task,
        meta={'base': _resolve_base()[1], 'letter': letter, 'page_index': page_index}
    )
    return jsonify({'status': 'queued', 'task_id': task_id})

# Helper predicates for pending work

def _letter_needs_rebuild(letter_dir: Path) -> bool:
    chunks_dir = letter_dir / 'chunks'
    de_path = letter_dir / 'html_de.html'
    if not chunks_dir.exists():
        return False
    latest_chunk_mtime = 0
    for f in chunks_dir.glob('*_*.html'):
        try:
            latest_chunk_mtime = max(latest_chunk_mtime, os.path.getmtime(f))
        except Exception:
            pass
    try:
        de_mtime = os.path.getmtime(de_path) if de_path.exists() else 0
    except Exception:
        de_mtime = 0
    return latest_chunk_mtime > de_mtime or not de_path.exists()

def _letter_needs_translate(letter_dir: Path) -> bool:
    de_path = letter_dir / 'html_de.html'
    en_path = letter_dir / 'html_en.html'
    if not de_path.exists():
        return False
    try:
        de_mtime = os.path.getmtime(de_path)
        en_mtime = os.path.getmtime(en_path) if en_path.exists() else 0
    except Exception:
        return True
    return en_mtime < de_mtime

@app.route('/api/qc/<letter>/chunk/<int:page_idx>/<int:chunk_idx>/retry', methods=['POST'])
def qc_chunk_retry_pair(letter, page_idx, chunk_idx):
    data = request.get_json(force=True)
    feedback = data.get('feedback', '')
    base_outputs, _base_name = _resolve_base()
    letter_dir = base_outputs / letter
    chunks_dir = letter_dir / 'chunks'
    img_path = chunks_dir / f'{page_idx}_chunk_{chunk_idx+1}.png'
    if not img_path.exists():
        return ('Chunk image not found', 404)

    def task():
        image = Image.open(img_path)
        async def run():
            html, reasoning = await text_extractor.transcribe_chunk(image, feedback=feedback)
            (chunks_dir / f'{page_idx}_{chunk_idx}.html').write_text(html)
            (chunks_dir / f'{page_idx}_{chunk_idx}_reasoning.txt').write_text(reasoning)
        asyncio.run(run())

    task_id = _run_in_background(
        name=f'Retry chunk — {letter} p{page_idx+1} c{chunk_idx+1}',
        target=task,
        meta={'base': _resolve_base()[1], 'letter': letter, 'page_index': page_idx, 'chunk_index': chunk_idx}
    )
    return jsonify({'status': 'queued', 'task_id': task_id})

@app.route('/api/qc/<letter>/rebuild_html', methods=['POST'])
def qc_rebuild_html(letter):
    data = request.get_json(silent=True) or {}
    feedback = data.get('feedback', '')
    base_outputs, _base_name = _resolve_base()
    letter_dir = base_outputs / letter
    chunks_dir = letter_dir / 'chunks'
    page0 = (letter_dir / 'pages' / 'page_1.png')
    if not page0.exists():
        return ('Missing first page image', 400)

    def task():
        image = Image.open(page0)
        html_chunks = []
        html_files = sorted(chunks_dir.glob('*_*.html'))
        if html_files:
            for f in html_files:
                html_chunks.append(f.read_text())
        async def run():
            html_de, reasoning = await text_extractor.unite_html(html_chunks, image, feedback=feedback)
            (letter_dir / 'reasoning_in_unite_html.txt').write_text(reasoning)
            (letter_dir / 'html_de.html').write_text(html_de)
        asyncio.run(run())

    task_id = _run_in_background(
        name=f'Rebuild HTML — {letter}',
        target=task,
        meta={'base': _resolve_base()[1], 'letter': letter}
    )
    return jsonify({'status': 'queued', 'task_id': task_id})

@app.route('/api/qc/all/rebuild_html', methods=['POST'])
def qc_rebuild_html_all():
    base_outputs, base_name = _resolve_base()
    letters = [p.name for p in base_outputs.iterdir() if p.is_dir()]
    enqueued = []
    for letter in letters:
        letter_dir = base_outputs / letter
        if not _letter_needs_rebuild(letter_dir):
            continue
        chunks_dir = letter_dir / 'chunks'
        page0 = (letter_dir / 'pages' / 'page_1.png')
        if not page0.exists():
            continue
        def make_task(letter=letter, page0=page0, chunks_dir=chunks_dir, letter_dir=letter_dir):
            def task():
                image = Image.open(page0)
                html_chunks = []
                html_files = sorted(chunks_dir.glob('*_*.html'))
                if html_files:
                    for f in html_files:
                        html_chunks.append(f.read_text())
                async def run():
                    html_de, reasoning = await text_extractor.unite_html(html_chunks, image, feedback='')
                    (letter_dir / 'reasoning_in_unite_html.txt').write_text(reasoning)
                    (letter_dir / 'html_de.html').write_text(html_de)
                asyncio.run(run())
            return task
        task_id = _run_in_background(
            name=f'Rebuild HTML — {letter}',
            target=make_task(),
            meta={'base': base_name, 'letter': letter}
        )
        enqueued.append({'letter': letter, 'task_id': task_id})
    return jsonify({'status': 'queued', 'tasks': enqueued})

@app.route('/api/qc/all/translate', methods=['POST'])
def qc_translate_all():
    base_outputs, base_name = _resolve_base()
    letters = [p.name for p in base_outputs.iterdir() if p.is_dir()]
    enqueued = []
    for letter in letters:
        letter_dir = base_outputs / letter
        if not _letter_needs_translate(letter_dir):
            continue
        html_de_path = letter_dir / 'html_de.html'
        if not html_de_path.exists():
            continue
        original_html = html_de_path.read_text()
        def make_task(letter=letter, original_html=original_html, letter_dir=letter_dir):
            def task():
                async def run():
                    await text_extractor.save_and_translate_html(original_html, letter_dir, feedback='')
                asyncio.run(run())
            return task
        task_id = _run_in_background(
            name=f'Translate — {letter}',
            target=make_task(),
            meta={'base': base_name, 'letter': letter}
        )
        enqueued.append({'letter': letter, 'task_id': task_id})
    return jsonify({'status': 'queued', 'tasks': enqueued})

@app.route('/api/qc/<letter>/deep_reload', methods=['POST'])
def qc_deep_reload(letter):
	# Re-run chunking, chunk->html, and unify, then translate
	base_outputs, _base_name = _resolve_base()
	pdf_path = _find_pdf_for_letter(base_outputs, letter)
	if not pdf_path:
		return ('PDF not found', 404)
	output_dir = base_outputs / letter
	output_dir.mkdir(parents=True, exist_ok=True)

	def task():
		async def run():
			pdf = pymupdf.open(pdf_path)
			await extraction_pipeline.process_pdf(pdf, output_path=output_dir)
			# translate to EN
			de_path = output_dir / 'html_de.html'
			if de_path.exists():
				await text_extractor.save_and_translate_html(de_path.read_text(), output_dir)
		import extraction_pipeline
		asyncio.run(run())

	task_id = _run_in_background(
		name=f'Deep reload — {letter}',
		target=task,
		meta={'base': _resolve_base()[1], 'letter': letter}
	)
	return jsonify({'status': 'queued', 'task_id': task_id})

@app.route('/api/qc/<letter>/translate', methods=['POST'])
def qc_translate(letter):
    data = request.get_json(silent=True) or {}
    feedback = data.get('feedback', '')
    base_outputs, _base_name = _resolve_base()
    letter_dir = base_outputs / letter
    html_de_path = letter_dir / 'html_de.html'
    if not html_de_path.exists():
        return ('html_de.html not found', 404)
    original_html = html_de_path.read_text()

    def task():
        async def run():
            await text_extractor.save_and_translate_html(original_html, letter_dir, feedback=feedback)
        asyncio.run(run())

    task_id = _run_in_background(
        name=f'Translate — {letter}',
        target=task,
        meta={'base': _resolve_base()[1], 'letter': letter}
    )
    return jsonify({'status': 'queued', 'task_id': task_id})

@app.route('/api/qc/<letter>/html_de')
def qc_html_de(letter):
    base_outputs, _base_name = _resolve_base()
    letter_dir = base_outputs / letter
    html_path = letter_dir / 'html_de.html'
    if not html_path.exists():
        return jsonify({'html': '', 'mtime': 0})
    return jsonify({'html': html_path.read_text(), 'mtime': os.path.getmtime(html_path)})

@app.route('/api/qc/<letter>/html_en')
def qc_html_en(letter):
    base_outputs, _base_name = _resolve_base()
    letter_dir = base_outputs / letter
    html_path = letter_dir / 'html_en.html'
    if not html_path.exists():
        return jsonify({'html': '', 'mtime': 0})
    return jsonify({'html': html_path.read_text(), 'mtime': os.path.getmtime(html_path)})

@app.route('/api/qc/<letter>/html_de/save', methods=['POST'])
def qc_html_de_save(letter):
    data = request.get_json(force=True)
    html = data.get('html', '')
    base_outputs, _base_name = _resolve_base()
    letter_dir = base_outputs / letter
    html_path = letter_dir / 'html_de.html'
    html_path.write_text(html)
    return jsonify({'status': 'ok', 'mtime': os.path.getmtime(html_path)})

@app.route('/api/qc/<letter>/html_en/save', methods=['POST'])
def qc_html_en_save(letter):
    data = request.get_json(force=True)
    html = data.get('html', '')
    base_outputs, _base_name = _resolve_base()
    letter_dir = base_outputs / letter
    html_path = letter_dir / 'html_en.html'
    html_path.write_text(html)
    return jsonify({'status': 'ok', 'mtime': os.path.getmtime(html_path)})

@app.route('/api/qc/<letter>/html_de/approve', methods=['POST'])
def qc_html_de_approve(letter):
    base_outputs, _base_name = _resolve_base()
    letter_dir = base_outputs / letter
    html_path = letter_dir / 'html_de.html'
    if not html_path.exists():
        return ('Not found', 404)
    mtime = os.path.getmtime(html_path)
    state = _load_review_state(letter_dir)
    state['html_de_mtime'] = mtime
    _save_review_state(letter_dir, state)
    return jsonify({'status': 'ok', 'approved_mtime': mtime})

@app.route('/api/qc/<letter>/html_en/approve', methods=['POST'])
def qc_html_en_approve(letter):
    base_outputs, _base_name = _resolve_base()
    letter_dir = base_outputs / letter
    html_path = letter_dir / 'html_en.html'
    if not html_path.exists():
        return ('Not found', 404)
    mtime = os.path.getmtime(html_path)
    state = _load_review_state(letter_dir)
    state['html_en_mtime'] = mtime
    _save_review_state(letter_dir, state)
    return jsonify({'status': 'ok', 'approved_mtime': mtime})

REVIEW_STATE_FILE = 'review_state.json'

def _load_review_state(letter_dir: Path):
    state_path = letter_dir / REVIEW_STATE_FILE
    if state_path.exists():
        try:
            return json.loads(state_path.read_text())
        except Exception:
            return {}
    return {}

def _save_review_state(letter_dir: Path, state: dict):
    (letter_dir / REVIEW_STATE_FILE).write_text(json.dumps(state, indent=2))

@app.route('/api/qc/<letter>/review_state')
def qc_review_state(letter):
    base_outputs, _base_name = _resolve_base()
    letter_dir = base_outputs / letter
    state = _load_review_state(letter_dir)
    return jsonify(state)

@app.route('/api/qc/<letter>/chunks')
def qc_chunks(letter):
    base_outputs, base_name = _resolve_base()
    letter_dir = base_outputs / letter
    chunks_dir = letter_dir / 'chunks'
    if not chunks_dir.exists():
        return jsonify({'chunks': []})
    state = _load_review_state(letter_dir)
    approved = (state.get('chunks') or {})
    result = []
    # For each page coords file, enumerate chunks
    for coords_file in sorted(chunks_dir.glob('*_chunk_coords.txt')):
        page_idx = int(coords_file.stem.split('_')[0])
        with open(coords_file, 'r') as f:
            lines = [ln for ln in f.read().strip().splitlines() if ln.strip()]
        for j in range(len(lines)):
            img_rel = f'/{base_name}/{letter}/chunks/{page_idx}_chunk_{j+1}.png'
            html_file = chunks_dir / f'{page_idx}_{j}.html'
            html_path = str(html_file) if html_file.exists() else None
            mtime = os.path.getmtime(html_path) if html_path else 0
            reason_txt = chunks_dir / f'{page_idx}_{j}_reasoning.txt'
            reason_html = chunks_dir / f'{page_idx}_{j}_reasoning.html'
            reason_path = reason_txt if reason_txt.exists() else (reason_html if reason_html.exists() else None)
            key = f'{page_idx}_{j}'
            is_approved = False
            try:
                is_approved = approved.get(key, 0) == mtime
            except Exception:
                is_approved = False
            result.append({
                'page_index': page_idx,
                'chunk_index': j,
                'image_url': img_rel,
                'html_rel': f'/{base_name}/{letter}/chunks/{page_idx}_{j}.html' if html_path else None,
                'reasoning_rel': f'/{base_name}/{letter}/chunks/{reason_path.name}' if reason_path else None,
                'html_mtime': mtime,
                'approved': is_approved
            })
    return jsonify({'chunks': result})

@app.route('/api/qc/<letter>/chunk/<int:page_idx>/<int:chunk_idx>')
def qc_chunk_detail_pair(letter, page_idx, chunk_idx):
    base_outputs, base_name = _resolve_base()
    letter_dir = base_outputs / letter
    chunks_dir = letter_dir / 'chunks'
    image_url = f'/{base_name}/{letter}/chunks/{page_idx}_chunk_{chunk_idx+1}.png'
    html_file = chunks_dir / f'{page_idx}_{chunk_idx}.html'
    html = html_file.read_text() if html_file.exists() else ''
    reason_txt = chunks_dir / f'{page_idx}_{chunk_idx}_reasoning.txt'
    reason_html = chunks_dir / f'{page_idx}_{chunk_idx}_reasoning.html'
    reasoning = reason_txt.read_text() if reason_txt.exists() else (reason_html.read_text() if reason_html.exists() else '')
    mtime = os.path.getmtime(html_file) if html_file.exists() else 0
    state = _load_review_state(letter_dir)
    key = f'{page_idx}_{chunk_idx}'
    approved_mtime = (state.get('chunks') or {}).get(key, 0)
    approved = approved_mtime == mtime and mtime != 0
    return jsonify({'page_index': page_idx, 'chunk_index': chunk_idx, 'image_url': image_url, 'html': html, 'reasoning': reasoning, 'html_mtime': mtime, 'approved': approved})

@app.route('/api/qc/<letter>/chunk/<int:page_idx>/<int:chunk_idx>/save', methods=['POST'])
def qc_chunk_save_pair(letter, page_idx, chunk_idx):
    data = request.get_json(force=True)
    html = data.get('html', '')
    base_outputs, base_name = _resolve_base()
    letter_dir = base_outputs / letter
    chunks_dir = letter_dir / 'chunks'
    html_file = chunks_dir / f'{page_idx}_{chunk_idx}.html'
    with open(html_file, 'w') as f:
        f.write(html)
    

    
    return jsonify({'status': 'ok', 'html_mtime': os.path.getmtime(html_file)})

@app.route('/api/qc/<letter>/chunk/<int:page_idx>/<int:chunk_idx>/approve', methods=['POST'])
def qc_chunk_approve_pair(letter, page_idx, chunk_idx):
    base_outputs, _base_name = _resolve_base()
    letter_dir = base_outputs / letter
    chunks_dir = letter_dir / 'chunks'
    html_file = chunks_dir / f'{page_idx}_{chunk_idx}.html'
    if not html_file.exists():
        return ('Not found', 404)
    mtime = os.path.getmtime(html_file)
    state = _load_review_state(letter_dir)
    state.setdefault('chunks', {})[f'{page_idx}_{chunk_idx}'] = mtime
    _save_review_state(letter_dir, state)
    return jsonify({'status': 'ok', 'approved_mtime': mtime})

@app.route('/api/qc/<letter>/page/<int:page_index>/coords')
def qc_page_coords(letter, page_index):
    base_outputs, _base_name = _resolve_base()
    letter_dir = base_outputs / letter
    coords_path = letter_dir / 'chunks' / f'{page_index}_chunk_coords.txt'
    if not coords_path.exists():
        return jsonify({'coords': []})
    coords = []
    with open(coords_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = [int(x.strip()) for x in line.split(',')]
            if len(parts) == 4:
                coords.append({'x1': parts[0], 'y1': parts[1], 'x2': parts[2], 'y2': parts[3]})
    return jsonify({'coords': coords})

@app.route('/api/qc/<letter>/postprocess', methods=['POST'])
def qc_postprocess(letter):
    base_outputs, base_name = _resolve_base()
    letter_dir = base_outputs / letter
    html_path = letter_dir / 'html_de.html'
    if not html_path.exists():
        return ('html_de.html not found', 404)
    # Ensure first page image exists
    if not _ensure_pages_rendered(base_outputs, letter):
        return ('First page image not available', 404)
    page1_path = letter_dir / 'pages' / 'page_1.png'
    if not page1_path.exists():
        return ('First page image not found', 404)

    def task():
        async def run():
            first_img = Image.open(page1_path)
            result_img = await postprocessing.post_process(html_path.read_text(), first_img)
            # Save output preview image
            out_path = letter_dir / 'postprocessed_preview.png'
            result_img.save(out_path)
        asyncio.run(run())

    task_id = _run_in_background(
        name=f'Postprocess — {letter}',
        target=task,
        meta={'base': base_name, 'letter': letter}
    )
    return jsonify({'status': 'queued', 'task_id': task_id, 'output': f'/{base_name}/{letter}/postprocessed_preview.png'})

if __name__ == '__main__':
    print('Starting server...')
    app.run(debug=True, port=8001) 

