#!/usr/bin/env python3

import os
import sys
from pathlib import Path
import fitz  # PyMuPDF
import base64
from openai import OpenAI
from PIL import Image
import io
from typing import List

class LetterTranslator:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = OpenAI(api_key=api_key)
        
        self.translation_prompt = """Create a 1:1 replica of this letter in English. Copy the handwriting as close as possible. Copy details like a stamp, borders, or holes in the page. The only modification which I would like to make is a small but noticeable watermark with the words "AI generated" written at some prominent point where it does not disturb the rest of the replica.

The intention is to have an English translation open in a museum which should be as close to the original visually and in terms of content as possible."""

    def pdf_to_images(self, pdf_path: str) -> List[Image.Image]:
        """Convert PDF pages to PIL Images"""
        doc = fitz.open(pdf_path)
        images = []
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            # Render page to image at 300 DPI for high quality
            mat = fitz.Matrix(300/72, 300/72)
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            if img.width > 2000 or img.height > 1000:
                img.thumbnail((2000, 1000))
            images.append(img)
            
        doc.close()
        return images

    def translate_page(self, image: Image.Image) -> Image.Image:
        """Translate a single page using OpenAI o3"""
        print(f"Uploading image with resolution {image.width}x{image.height}")
        # Convert image to base64
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

        response = self.client.responses.create(
            model="o3",
            input=[{
                    "role": "user",
                    "content": [
                    {"type": "input_text", "text": self.translation_prompt},
                        {
                        "type": "input_image",
                        "image_url": "data:image/png;base64," + img_base64,
                    },
                ],
            }],
            tools=[{"type": "image_generation"}],
        )
        
        # Extract image from response
        image_data = [
            output.result
            for output in response.output
            if output.type == "image_generation_call"
        ]
            
        if image_data:
            image_base64_result = image_data[0]
            img_bytes = base64.b64decode(image_base64_result)
                                return Image.open(io.BytesIO(img_bytes))
        
        raise Exception("No image found in API response")

    def images_to_pdf(self, images: List[Image.Image], output_path: str):
        """Convert list of images to PDF"""
        if not images:
            return
            
        # Convert all images to RGB if they aren't already
        rgb_images = []
        for img in images:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            rgb_images.append(img)
        
        # Save as PDF
        rgb_images[0].save(
            output_path, 
            save_all=True, 
            append_images=rgb_images[1:] if len(rgb_images) > 1 else [],
            format='PDF'
        )

    def translate_letter(self, input_pdf: str, output_pdf: str):
        """Translate an entire letter from German to English"""
        print(f"Translating {input_pdf} -> {output_pdf}")
        
        # Convert PDF to images
        print("Converting PDF to images...")
        pages = self.pdf_to_images(input_pdf)
        print(f"Found {len(pages)} pages")
        
        # Translate each page
        translated_pages = []
        for i, page in enumerate(pages, 1):
            print(f"Translating page {i}/{len(pages)}...")
            try:
                translated_page = self.translate_page(page)
                translated_pages.append(translated_page)
                print(f"Page {i} translated successfully")
            except Exception as e:
                print(f"Error translating page {i}: {e}")
                # Optionally continue with remaining pages or stop
                raise
        
        # Convert translated images back to PDF
        print("Combining translated pages into PDF...")
        self.images_to_pdf(translated_pages, output_pdf)
        print(f"Translation complete: {output_pdf}")

    def translate_all_letters(self, letters_de_dir: str, letters_en_dir: str):
        """Translate all letters in the directory"""
        letters_de_path = Path(letters_de_dir)
        letters_en_path = Path(letters_en_dir)
        
        # Create output directory if it doesn't exist
        letters_en_path.mkdir(parents=True, exist_ok=True)
        
        # Find all PDF files in the German letters directory
        pdf_files = list(letters_de_path.glob("*.pdf"))
        
        if not pdf_files:
            print("No PDF files found in letters_de directory")
            return
        
        print(f"Found {len(pdf_files)} letters to translate")
        
        for pdf_file in pdf_files:
            output_file = letters_en_path / pdf_file.name
            try:
                self.translate_letter(str(pdf_file), str(output_file))
            except Exception as e:
                print(f"Failed to translate {pdf_file.name}: {e}")
                continue

def main():
    # Check for API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set")
        print("Please set it with: export OPENAI_API_KEY='your-api-key-here'")
        sys.exit(1)
    
    # Set up paths
    script_dir = Path(__file__).parent
    letters_de_dir = script_dir / "public" / "letters_de"
    letters_en_dir = script_dir / "public" / "letters_en"
    
    # Create translator and run
    translator = LetterTranslator(api_key)
    translator.translate_all_letters(str(letters_de_dir), str(letters_en_dir))

if __name__ == "__main__":
    main()