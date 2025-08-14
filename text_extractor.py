from PIL import Image
import gpt
from pathlib import Path
from typing import List, Tuple

# Code to print concise warnings with source location
import warnings
warnings.simplefilter("always")
warnings.filterwarnings("always")
import traceback

def show_concise_warning(message, category, filename, lineno, file=None, line=None):
    stack = traceback.extract_stack()
    # Find the last frame that's in our code (not in the warnings module)
    for frame in reversed(stack[:-1]):  # Skip the current frame
        if not frame.filename.endswith('warnings.py'):
            print(f"WARNING: {message}")
            print(f"  at {frame.filename}:{frame.lineno} in {frame.name}")
            if frame.line:
                print(f"  -> {frame.line.strip()}")
            break

warnings.showwarning = show_concise_warning


async def transcribe_chunk(image: Image.Image) -> Tuple[str, str]:
    response, reasoning = await gpt.get_text_response("You will be given an image of a chunk of a letter. Your task is to fully transcribe all text in the image to html. Keep formatting as close to the original as possible, including linebreaks. Make it pretty! If there, for example, is a very nice header, make sure to accurerely and artfully replicate that header in html. Output only the html code, no other text. Output only the html (without the ```html and ```).", image, return_reasoning=True)
    
    return response[7:-3].strip(), reasoning

def log_chunks(to_log : List[Tuple[str, str]], output_path: Path) -> None:
    for i, (text, reasoning) in enumerate(to_log):
        with open(output_path / f"{i}_reasoning.txt", "w") as f:
            f.write(reasoning)
        with open(output_path / f"{i}.html", "w") as f:
            f.write(text)


# Unifies all html files of one letter into one html file
async def unite_html(html_chunks: List[str], image: Image.Image) -> Tuple[str, str]:
    response, reasoning = await gpt.get_text_response("You will be given multiple html files all attempting to transcribe different parts of scans of a letter with one or more pages. Your task is to unite them into one html file. They already contain a lot of formatting, which you should synthesize to one single consistent formatting. You are given a scan of the first page of the letter as context. Please try to match the style of the first page as closely as possible (e.g. if it has a nice header, replicate that header in html. try to replicate the background color, etc.) Output in the usual format of ```html (actual code)```\n\nHTML files of the letter:\n" + "\n\n".join(html_chunks), image, return_reasoning=True, effort="medium")

    assert response.startswith("```html") and response.endswith("```")
    return response[7:-3].strip(), reasoning
        


async def save_and_translate_html(original_html: str, output_folder: Path) -> str:
    response = await gpt.get_text_response("You will be given an html file. Your task is to translate it to english. Preserve the original's linguistic style as well as formatting. But do remove needless linebreaks. Also there might be page numbers somewhere - remove those (but if present keep the document number on the top left). Output in the usual format of ```html (actual code)``` (attached to this prompt is the original html file)\n\n" + original_html, effort="medium")

    assert response.startswith("```html") and response.endswith("```")
    with open(output_folder / "html_en.html", "w") as f:
        f.write(response[7:-3].strip())
    with open(output_folder / "html_de.html", "w") as f:
        f.write(original_html)

    return response[7:-3].strip()


