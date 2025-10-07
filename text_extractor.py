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


async def transcribe_chunk(image: Image.Image, feedback: str = "") -> Tuple[str, str]:
    base_prompt = (
        "You will be given an image of a chunk of a letter. Your task is to fully transcribe all text in the image to html. "
        "Keep formatting as close to the original as possible, including linebreaks. Make it pretty! If there, for example, is a very nice header, "
        "make sure to accurerely and artfully replicate that header in html. Use mathjax to render mathematical expressions. Please completely ignore lines of text which are partially cut off from the screenshot. Output only the html code, no other text.   "
        "Output only the html (without the ```html and ```)."
    )
    prompt = base_prompt if not feedback else (base_prompt + "\n\nReviewer feedback/instructions to incorporate:\n" + feedback)
    response, reasoning = await gpt.get_text_response(prompt, image, return_reasoning=True)

    text = response.strip()
    if text.startswith("```"):
        # Extract between first and last triple backticks
        try:
            first = text.find("\n")
            if first == -1:
                first = text.find("```", 3)
            start = text.find("\n", 0, first) + 1 if first != -1 else 3
            end = text.rfind("```")
            if end != -1:
                text = text[start:end].strip()
        except Exception:
            pass
    return text, reasoning

def log_chunks(to_log : List[Tuple], output_path: Path) -> None:
    for i, entry in enumerate(to_log):
        # Support both (text, reasoning) and (page_idx, chunk_idx, text, reasoning)
        if len(entry) == 2:
            text, reasoning = entry
            page_chunk_name = f"{i}"
        elif len(entry) == 4:
            page_idx, chunk_idx, text, reasoning = entry
            page_chunk_name = f"{page_idx}_{chunk_idx}"
        else:
            # Fallback to index-based naming
            text, reasoning = entry[-2], entry[-1]
            page_chunk_name = f"{i}"
        with open(output_path / f"{page_chunk_name}_reasoning.txt", "w") as f:
            f.write(reasoning)
        with open(output_path / f"{page_chunk_name}.html", "w") as f:
            f.write(text)


# Unifies all html files of one letter into one html file
async def unite_html(html_chunks: List[str], image: Image.Image, feedback: str = "") -> Tuple[str, str]:
    base_prompt = (
        "You will be given multiple html files all attempting to transcribe different parts of scans of a letter with one or more pages. "
        "Your task is to unite them into one html file. They already contain a lot of formatting, which you should synthesize to one single consistent formatting. But do not alter the content of the letter."
        "You are given a scan of the first page of the letter as context. Please try to match the style of the first page as closely as possible (e.g. if it has a nice header, replicate that header in html. try to replicate the background color, etc.) "
        "Output in the usual format of ```html (actual code)```\n\nHTML files of the letter:\n"
    )
    prompt = base_prompt + "\n\n".join(html_chunks)
    if feedback:
        prompt += "\n\nReviewer feedback/instructions to incorporate:\n" + feedback
    response, reasoning = await gpt.get_text_response(prompt, image, return_reasoning=True, effort="medium")

    text = response.strip()
    if text.startswith("```"):
        try:
            # Support ```html or ```HTML or just ```
            fence_line_end = text.find("\n")
            end = text.rfind("```")
            if fence_line_end != -1 and end != -1 and end > fence_line_end:
                text = text[fence_line_end+1:end].strip()
        except Exception:
            pass
    return text, reasoning
        


async def save_and_translate_html(original_html: str, output_folder: Path, feedback: str = "") -> str:
    base_prompt = (
        "You will be given an html file. Your task is to translate it to english. Preserve the original's linguistic style as well as formatting. "
        "But do remove needless linebreaks. Also there might be page numbers somewhere - remove those (but if present keep the document number on the top left). "
        "Output in the usual format of ```html (actual code)``` (attached to this prompt is the original html file)\n\n"
    )
    prompt = base_prompt + original_html
    if feedback:
        prompt += "\n\nReviewer feedback/instructions to incorporate:\n" + feedback
    response = await gpt.get_text_response(prompt, effort="medium")

    text = response.strip()
    if text.startswith("```"):
        try:
            fence_line_end = text.find("\n")
            end = text.rfind("```")
            if fence_line_end != -1 and end != -1 and end > fence_line_end:
                text = text[fence_line_end+1:end].strip()
        except Exception:
            pass
    with open(output_folder / "html_en.html", "w") as f:
        f.write(text)
    with open(output_folder / "html_de.html", "w") as f:
        f.write(original_html)

    return text


