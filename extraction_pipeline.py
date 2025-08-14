import asyncio
import chunk_extractor, text_extractor
from pathlib import Path
from PIL import Image
import pymupdf
import io
import os


async def process_folder(folder_path : Path, output_path = Path("public/outputs_gpt-5") ):
    processed_files = []
    for file in os.listdir(folder_path):
        if file.endswith(".pdf"):
            pdf = pymupdf.open(folder_path/file)
            (output_path/file[:-4]/"chunks").mkdir(parents=True, exist_ok=True)
            processed_files.append(asyncio.create_task(process_pdf(pdf, output_path/file[:-4])))

    await asyncio.gather(*processed_files)

    
async def process_pdf(pdf : pymupdf.Document, output_path : Path):
    print(f"Processing {pdf.name}...")

    # Use ~4.17x scale for 300 DPI (300/72 = 4.167)
    matrix = pymupdf.Matrix(4.167, 4.167)
    images = [Image.open(io.BytesIO(page.get_pixmap(matrix=matrix).tobytes("png"))) for page in pdf]
   
    # TODO undo
    # Save all images in output_path and reload them
    image_paths = []
    (output_path / "pages").mkdir(parents=True, exist_ok=True)
    for i, img in enumerate(images):
        img_path = output_path / "pages" / f"page_{i+1}.png"
        img.save(img_path)
        image_paths.append(img_path)
    images = [Image.open(p) for p in image_paths]
    
    async def _with_index(i, task):
        return i, await task

    indexed_pages = [_with_index(i, asyncio.create_task(chunk_extractor.get_chunks_coords_from_image(img, output_path/f"chunks/page_{i+1}.txt"))) for i, img in enumerate(images)]
    entries = []

    for coro in asyncio.as_completed(indexed_pages):
        page_idx, coords = await coro
        print(f"Page {page_idx} has {len(coords)} chunks")
        for chunk_idx, img in enumerate(chunk_extractor.save_chunks(images[page_idx], coords, output_path, page_idx)):
            entries.append((page_idx, chunk_idx, asyncio.create_task(text_extractor.transcribe_chunk(img))))

    texts_reasoning_pairs = await asyncio.gather(*[t for _, _, t in sorted(entries)])
    print("Extracted text for all chunks")
    text_extractor.log_chunks(texts_reasoning_pairs, output_path/"chunks")

    html_de, reasoning = await text_extractor.unite_html([text for text, _ in texts_reasoning_pairs], images[0])

    with open(output_path/"reasoning_in_unite_html.txt", "w") as f:
        f.write(reasoning)

    # todo undo later
    with open(output_path/"html_de.html", "w") as f:
        f.write(html_de)
    # await text_extractor.save_and_translate_html(html_de, output_path)
    return reasoning



async def main():
    await process_folder(Path("public/samples"))

if __name__ == "__main__":
    asyncio.run(main())