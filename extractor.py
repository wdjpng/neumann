import os
from pathlib import Path
from pdf2image import convert_from_path

pdf_dir = Path("public/letters_de")
output_dir = Path("public/hidden_extracted")
output_dir.mkdir(parents=True, exist_ok=True)

for pdf_file in pdf_dir.glob("*.pdf"):
    pages = convert_from_path(str(pdf_file))
    base_name = pdf_file.stem
    for i, page in enumerate(pages, 1):
        page_path = output_dir / f"{base_name}_page_{i}.jpg"
        page.save(page_path, "JPEG")
