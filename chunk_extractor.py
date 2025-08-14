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
import concurrent.futures
from pydantic import validate_call
import gpt

async def get_chunks_coords_from_image(image: Image.Image, output_file_path: Path = None) -> List[Tuple[int, int, int, int]]:
        """Get chunk coordinates from an image using OpenAI's model."""
        content, reasoning = await gpt.get_text_response("You are given an image which you are supposed to split into reasonably‑sized chunks. More specifically, split it into two to ten rectangular chunks. No chunk should contain more than two to four lines of mathematical expression except if the only way to not split up one big mathematical expression is to put multiple in one chunk. Other than that, make sure then no more then around eight lines of text are in each chunk, but the most important part really just is that not too many equations / mathematical expressions are in one chunk. You will be asked to output the top left and bottom right coordinates of the chunk. Coordinates must be integers in the pixel coordinate system of the original image, with (0, 0) at the top‑left of the image. Every single line of text or mathematical expression must be fully contained in one chunk. Note that some lines of text are not quite straight - still make sure that the entire line of text is contained in at least one bounding box! *Never* distribute one mathematical expression over two chunks - the whole expression must be contained in one chunk! For each chunk, output in order (x1, y1, x2, y2), one entry per line. x1,y1 are the coordinates of the top left corner and x2,y2 are the coordinates of the bottom right corner of the chunk. Finally, on the last line, output the resolution of the image in the format (width, height). Do **not** output anything except the list of chunks coordinate pairs and the image resolution. (The image is attached to this prompt as context.)\n\n\nAdditional instructions:\nWhen this does not seem unreasonably, include the whole width of each letter page in each chunk.\n You may liberally use up to ten chunks in total if this helps split mathematical expressions neatly into different chunks of no more than two two three expressions each. But for text and especially the header, really do not use more chunks than strictly necessary to fulfill your goals as stated above. \n(The image is attached to this prompt as context.)", image=image, return_reasoning=True)

        if output_file_path is not None:
            with open(output_file_path, "w") as f:
                f.write(reasoning)

        pattern = re.compile(r'\(([0-9,\s]+)\)')
        matches = [[int(x.strip()) for x in match.split(',')] for match in pattern.findall(content)]
        
        if not matches:
            print(f"Warning: Could not parse coordinates from response: {content}")
            return []
            
        x_scale, y_scale = image.width / matches[-1][0], image.height / matches[-1][1]
        coords = []
        for (x1, y1, x2, y2) in matches[:-1]:
            x_1, x_2 = round(x1 * x_scale), round(x2 * x_scale)
            y_1, y_2 = round(y1 * y_scale), round(y2 * y_scale)
            coords.append((x_1, y_1, x_2, y_2))
        
        # # The model's coordinates are relative to an image where the shorter side is 768px.
        # # We need to rescale them to the original image size.
        
        # short_side, long_side = min(orig_w, orig_h), max(orig_w, orig_h)
        
        # scale = 1.0
        # if long_side > 2048:
        #     scale *= 2048 / long_side
        # if short_side * scale > 768:
        #     scale *= 768 / (short_side * scale)
        
        # # Model's image size
        # model_w = int(round(orig_w / scale))
        # model_h = int(round(orig_h / scale))
        # # For each coordinate, rescale to original image
        # def rescale(x, y):
        #     return (
        #         int(round(x * orig_w / model_w)),
        #         int(round(y * orig_h / model_h))
        #     )
        # coords = [rescale(x1, y1) + rescale(x2, y2) for (x1, y1, x2, y2) in coords]
            
        return coords

def save_chunks(image: Image.Image, chunk_coords: List[Tuple[int, int, int, int]], output_dir: Path, page_num: int):
    
    chunks = []
    for j, (x1, y1, x2, y2) in enumerate(chunk_coords):
        chunk_image = image.crop((x1, y1, x2, y2))
        output_filename = f"chunks/{page_num}_chunk_{j+1}.png"
        chunk_image.save(output_dir / output_filename, "PNG")
        chunks.append(chunk_image)

    # Save chunk coordinates as a txt file, one chunk per line
    coords_path = output_dir / f"chunks/{page_num}_chunk_coords.txt"
    with open(coords_path, "w") as f:
        for x1, y1, x2, y2 in chunk_coords:
            f.write(f"{x1},{y1},{x2},{y2}\n")

    return chunks
        

def draw_chunks_borders(image: Image.Image, chunk_coords: List[Tuple[int, int, int, int]]) -> Image.Image:
    """Draw colored borders around chunks on the image and return the modified image."""
    # Create a copy to avoid modifying the original image
    image_with_borders = image.copy()
    draw = ImageDraw.Draw(image_with_borders)
    
    # Define colors for chunk borders
    colors = [
        "red", "blue", "green", "orange", "purple", "yellow", 
        "cyan", "magenta", "lime", "pink", "brown", "gray",
        "navy", "olive", "maroon", "teal", "silver", "gold"
    ]
    
    # Draw rectangle border for each chunk
    for i, (x1, y1, x2, y2) in enumerate(chunk_coords):
        color = colors[i % len(colors)]
        draw.rectangle([x1, y1, x2, y2], outline=color, width=5)
        
        # Optional: Add chunk number label
        draw.text((x1 + 5, y1 + 5), f"Chunk {i+1}", fill=color)
    
    return image_with_borders
    