#!/usr/bin/env python3

import os
import sys
from pathlib import Path
import base64
from openai import OpenAI
from PIL import Image, ImageDraw
import io
import re
from typing import List, Tuple
import random
import concurrent.futures

from prompts import chunking as chunking_prompt

class ChunkExtractor:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required.")
        self.client = OpenAI(api_key=api_key)
        # Define a list of distinct colors for chunk boxes
        self.colors = [
            "red", "blue", "green", "orange", "purple", "yellow", 
            "cyan", "magenta", "lime", "pink", "brown", "gray",
            "navy", "olive", "maroon", "teal", "silver", "gold"
        ]

    def get_chunks_from_image(self, image: Image.Image) -> List[Tuple[int, int, int, int]]:
        """Get chunk coordinates from an image using OpenAI's model."""
        print(f"Processing image with resolution {image.width}x{image.height}...")
        
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

        response = self.client.chat.completions.create(
            model="o3",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": chunking_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{img_base64}",
                                "detail": "high"
                            },
                        },
                    ],
                }
            ],
        )

        content = response.choices[0].message.content
        if not content:
            print("Warning: No content in response from API.")
            return []
            
        print("Raw response from model:", content)

        content = content.strip().replace("```", "").replace("json", "").strip()
        
        coords = []
        pattern = re.compile(r'\((\d+),\s*(\d+)\)\s*\((\d+),\s*(\d+)\)')
        matches = pattern.findall(content)

        if not matches:
            print(f"Warning: Could not parse coordinates from response: {content}")
        
        for match in matches:
            coords.append(tuple(map(int, match)))
        # The model's coordinates are relative to an image where the shorter side is 768px.
        # We need to rescale them to the original image size.
        orig_w, orig_h = image.width, image.height
        short_side, long_side = min(orig_w, orig_h), max(orig_w, orig_h)
        # Determine scaling factor
        scale = short_side / 768
        # Model's image size
        model_w = int(round(orig_w / scale))
        model_h = int(round(orig_h / scale))
        # For each coordinate, rescale to original image
        def rescale(x, y):
            return (
                int(round(x * orig_w / model_w)),
                int(round(y * orig_h / model_h))
            )
        coords = [rescale(x1, y1) + rescale(x2, y2) for (x1, y1, x2, y2) in coords]
            
        return coords

    def draw_chunks(self, image_path: Path, output_path: Path):
        """Loads an image, gets chunks, and draws them on a new image."""
        try:
            image = Image.open(image_path)
        except FileNotFoundError:
            print(f"Error: Image file not found at {image_path}", file=sys.stderr)
            sys.exit(1)

        chunk_coords = self.get_chunks_from_image(image)
        if not chunk_coords:
            print("No chunks found, exiting.", file=sys.stderr)
            return

        draw = ImageDraw.Draw(image)
        for i, (x1, y1, x2, y2) in enumerate(chunk_coords):
            # Use different color for each chunk, cycling through the color list
            color = self.colors[i % len(self.colors)]
            draw.rectangle([x1, y1, x2, y2], outline=color, width=5)

        image.save(output_path)
        print(f"Saved visualized chunks to {output_path}")
        image.show()

    def _process_page_for_extraction(self, page_image_data: bytes, pdf_stem: str, page_num: int, num_pages: int, output_dir: Path):
        """Helper to process a single page for chunk extraction."""
        page_image = Image.open(io.BytesIO(page_image_data))
        print(f"  Processing page {page_num}/{num_pages}")
        
        try:
            chunk_coords = self.get_chunks_from_image(page_image)
        except Exception as e:
            print(f"    Error getting chunks from OpenAI API for page {page_num}: {e}")
            return

        if not chunk_coords:
            print(f"    No chunks found for page {page_num}.")
            return
        
        print(f"    Found {len(chunk_coords)} chunks for page {page_num}.")

        for j, (x1, y1, x2, y2) in enumerate(chunk_coords):
            print(f"      Chunk {j+1} coordinates: ({x1}, {y1}) ({x2}, {y2})")
            chunk_image = page_image.crop((x1, y1, x2, y2))
            output_filename = f"{pdf_stem}_page_{page_num}_chunk_{j+1}.jpg"
            output_path = output_dir / output_filename
            chunk_image.save(output_path, "JPEG")
            print(f"      Saved chunk {j+1} to {output_path}")

    def extract_chunks_from_pdf(self, pdf_path: Path, output_dir: Path, parallelize: bool = False):
        """Extracts text chunks from a PDF and saves them as images."""
        try:
            import fitz  # PyMuPDF - only import when needed for PDF processing
        except ImportError:
            print("Error: PyMuPDF is required for PDF processing. Install with: uv pip install PyMuPDF", file=sys.stderr)
            return
        
        print(f"Processing {pdf_path.name}...")
        try:
            doc = fitz.open(str(pdf_path))
            pages_data = []
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                mat = fitz.Matrix(300 / 72, 300 / 72)
                pix = page.get_pixmap(matrix=mat)
                pages_data.append(pix.tobytes("png"))
            
            if parallelize:
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    futures = [
                        executor.submit(self._process_page_for_extraction, page_data, pdf_path.stem, i + 1, len(doc), output_dir)
                        for i, page_data in enumerate(pages_data)
                    ]
                    concurrent.futures.wait(futures)
            else:
                for i, page_data in enumerate(pages_data):
                    self._process_page_for_extraction(page_data, pdf_path.stem, i + 1, len(doc), output_dir)

            doc.close()
            
        except Exception as e:
            print(f"Error converting {pdf_path.name} to images: {e}")

    def process_folder(self, folder_path: Path, visualize: bool = False, parallelize: bool = False):
        """Process all PDF files in a folder."""
        if not folder_path.is_dir():
            print(f"Error: {folder_path} is not a directory.", file=sys.stderr)
            sys.exit(1)
        
        pdf_files = list(folder_path.glob("*.pdf"))
        if not pdf_files:
            print(f"No PDF files found in {folder_path}")
            return
        
        print(f"Found {len(pdf_files)} PDF files to process.")
        
        if not visualize:
            output_dir = Path("public/chunks")
            output_dir.mkdir(exist_ok=True)
        if parallelize:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                if visualize:
                    executor.map(lambda pdf_file: self.visualize_pdf_pages(pdf_file, parallelize=parallelize), pdf_files)
                else:
                    executor.map(lambda pdf_file: self.extract_chunks_from_pdf(pdf_file, output_dir, parallelize=parallelize), pdf_files)
        else:
            for pdf_file in pdf_files:
                if visualize:
                    self.visualize_pdf_pages(pdf_file, parallelize=parallelize)
                else:
                    self.extract_chunks_from_pdf(pdf_file, output_dir, parallelize=parallelize)

    def _process_page_for_visualization(self, page_image_data: bytes, pdf_stem: str, page_num: int, num_pages: int):
        """Helper to process a single page for chunk visualization."""
        page_image = Image.open(io.BytesIO(page_image_data))
        print(f"  Processing page {page_num}/{num_pages}")
        
        chunk_coords = self.get_chunks_from_image(page_image)
        if not chunk_coords:
            print(f"    No chunks found for page {page_num}.")
            return
        
        draw = ImageDraw.Draw(page_image)
        for i, (x1, y1, x2, y2) in enumerate(chunk_coords):
            color = self.colors[i % len(self.colors)]
            draw.rectangle([x1, y1, x2, y2], outline=color, width=5)
        
        output_filename = f"{pdf_stem}_page_{page_num}_visualized.jpg"
        output_path = Path(output_filename)
        page_image.save(output_path)
        print(f"    Saved visualized page to {output_path}")
        page_image.show()

    def visualize_pdf_pages(self, pdf_path: Path, parallelize: bool = False):
        """Convert PDF pages to images and visualize chunks for each page."""
        try:
            import fitz  # PyMuPDF - only import when needed for PDF processing
        except ImportError:
            print("Error: PyMuPDF is required for PDF processing. Install with: uv pip install PyMuPDF", file=sys.stderr)
            return
        
        print(f"Processing PDF: {pdf_path.name}...")
        
        try:
            doc = fitz.open(str(pdf_path))
            pages_data = []
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                mat = fitz.Matrix(300 / 72, 300 / 72)
                pix = page.get_pixmap(matrix=mat)
                pages_data.append(pix.tobytes("png"))
            
            if parallelize:
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    futures = [
                        executor.submit(self._process_page_for_visualization, page_data, pdf_path.stem, i + 1, len(doc))
                        for i, page_data in enumerate(pages_data)
                    ]
                    concurrent.futures.wait(futures)
            else:
                for i, page_data in enumerate(pages_data):
                    self._process_page_for_visualization(page_data, pdf_path.stem, i + 1, len(doc))
                
            doc.close()
            
        except Exception as e:
            print(f"Error processing {pdf_path.name}: {e}")


def main():
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Extract and visualize chunks from PDFs or images.")
    parser.add_argument("--visualize", help="Visualize chunks instead of extracting.", action="store_true")
    parser.add_argument("--parallelize", help="Run chunkification on all pages simultaneously for faster results.", action="store_true")
    parser.add_argument("input_path", help="Path to a PDF file, image file, or folder containing PDFs.", type=Path)

    args = parser.parse_args()

    extractor = ChunkExtractor(api_key=api_key)
    input_path = args.input_path

    if input_path.is_dir():
        # Handle folder input
        extractor.process_folder(input_path, visualize=args.visualize, parallelize=args.parallelize)
    elif input_path.is_file():
        if args.visualize:
            if input_path.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                # Handle single image file
                output_path = Path(f"{input_path.stem}_visualized.jpg")
                extractor.draw_chunks(input_path, output_path)
            elif input_path.suffix.lower() == '.pdf':
                # Handle single PDF file
                extractor.visualize_pdf_pages(input_path, parallelize=args.parallelize)
            else:
                print("Error: Unsupported file format. Use JPG, PNG, or PDF files.", file=sys.stderr)
                sys.exit(1)
        else:
            # Extract chunks (no visualization)
            if input_path.suffix.lower() == '.pdf':
                output_dir = Path("public/chunks")
                output_dir.mkdir(exist_ok=True)
                extractor.extract_chunks_from_pdf(input_path, output_dir, parallelize=args.parallelize)
            else:
                print("Error: Chunk extraction only supports PDF files.", file=sys.stderr)
                sys.exit(1)
    else:
        print(f"Error: {input_path} does not exist.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    main()
