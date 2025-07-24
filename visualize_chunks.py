import os
import sys
from pathlib import Path
import base64
from openai import OpenAI
from PIL import Image, ImageDraw
import io
import re
from typing import List, Tuple

from prompts import chunking as chunking_prompt

class ChunkVisualizer:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required.")
        self.client = OpenAI(api_key=api_key)

    def get_chunks_from_image(self, image: Image.Image) -> List[Tuple[int, int, int, int]]:
        """Get chunk coordinates from an image using OpenAI's model."""
        print(f"Processing image with resolution {image.width}x{image.height}...")
        
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": chunking_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{img_base64}"
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
        for (x1, y1, x2, y2) in chunk_coords:
            draw.rectangle([x1, y1, x2, y2], outline="red", width=5)

        image.save(output_path)
        print(f"Saved visualized chunks to {output_path}")
        image.show()


def main():
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    image_path = Path("public/hidden_extracted/anmeldung_page_1.jpg")
    output_path = Path("visualized_chunks.jpg")

    visualizer = ChunkVisualizer(api_key=api_key)
    visualizer.draw_chunks(image_path, output_path)

if __name__ == "__main__":
    main() 