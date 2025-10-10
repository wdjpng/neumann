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
        "Your task is to unite them into one html file. They already contain a lot of formatting that may not be consistent. Synthesize one single consistent formatting of the main body of the letter. If there are obivous duplicates, remove them. Header of the letter should be more or less left as is. But do not alter the content of the letter."
        "Output in the usual format of ```html (actual code)```\n\nHTML files of the letter:\n"
    )
    prompt = base_prompt + "\n\n".join(html_chunks)
    if feedback:
        prompt += "\n\nReviewer feedback/instructions to incorporate:\n" + feedback
    response, reasoning = await gpt.get_text_response(prompt, return_reasoning=True, effort="high")

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
    try:
        print(f"Starting translation for: {output_folder}")
        base_prompt = (
            "Translate the given html file to English. Try to preserve the style / feel of the language of the original, and do not change the content. Some sentences in the original are disjoin even though they should not be, so please unify paragraphs where linebreaks are seem unintentional with > 35% probability. I also want the text to fit nicely on the screen of the user, so please also remove newlines whenever they seem unnecessary. Also join hyphenated words which would not normally be hyphenated. Make sure that your edits results in a consistently formatted html file, ensuring that e.g. paragraphs are separated by same number of linebreaks. Other than those exceptions now described for which you should edit, you are asked to keep closely preserve the original formatting. \n\nWhen in doubt, translate the preserve meaning and the \"vibe\" rather than the exact phrasing. You may first think, but then please finish your output with the translated html file in the format ```html (your code)```\n\nHere the html file to translate:\n"
        )
        prompt = base_prompt + original_html
        if feedback:
            prompt += "\n\nReviewer feedback/instructions to incorporate:\n" + feedback
        
        print("Calling Claude API for translation...")
        response = await gpt.get_text_response(prompt, model="claude")
        print(f"Received response from Claude (length: {len(response)} chars)")

        text = response.strip()
        # Look for code fences anywhere in the response (not just at the start)
        try:
            # Find the first ``` and last ```
            start_fence = text.find("```")
            # Skip past the fence and language identifier (e.g., ```html)
            fence_line_end = text.find("\n", start_fence)
            end_fence = text.rfind("```")
            
            if fence_line_end != -1 and end_fence != -1 and end_fence > fence_line_end:
                text = text[fence_line_end+1:end_fence].strip()
                print("Extracted HTML from code fence")
            else:
                print("No code fence found, using raw response")
        except Exception as e:
            print(f"Error in parsing html after translation: {e}")
            pass
        
        print(f"Writing translated HTML (length: {len(text)} chars)")
        with open(output_folder / "html_en.html", "w") as f:
            f.write(text)
        with open(output_folder / "html_de.html", "w") as f:
            f.write(original_html)
        
        print(f"Translation completed successfully for: {output_folder}")
        return text
    
    except Exception as e:
        print(f"ERROR in save_and_translate_html:")
        print(f"  Exception type: {type(e).__name__}")
        print(f"  Exception message: {e}")
        import traceback
        traceback.print_exc()
        raise


