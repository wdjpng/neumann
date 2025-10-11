import asyncio
import json
from pathlib import Path
from typing import Optional
import gpt


async def extract_metadata_from_letter(html_content: str) -> dict:
    """Extract metadata from a letter's HTML content using AI."""
    
    prompt = """Please extract the author, recipient, and date of the letter. Also, provide a two-sentence summary and a suggested, succinct title. Choose a title length such that the text will take up either one or two  more or less full lines of text  when displayed as follows: Width: 260px (full content width, text is centered). Font: At ~1.1em (17.6px) font size in Georgia serif

Since all letters are either from or two von Neumann, do not mention von Neumann in the title. Please return the information in a json format, with the keys 'author', 'recipient', 'date', 'summary', and 'title'. If any of the information is not available, please use the value 'unknown'. Date should be in the format Month xth, yyyy. For additional context, here some of the reference numnber (the number at the top left), author, recipient, date pairs: Hs 91:676 - John von Neumann an Hermann Weyl  - 01.03.1925

Hs 91:677 - John von Neumann an Hermann Weyl  - 25.07.1925

Hs 91:678 - John von Neumann an Hermann Weyl  - 27.06.1927

Hs 91:679 - John von Neumann an Hermann Weyl  - 30.06.1928

Hs 91:680 - John von Neumann an Hermann Weyl  - 16.07.1928

Hs 91:681 - John von Neumann an Hermann Weyl  - 19.08.1928

Hs 91:682 - John von Neumann an Hermann Weyl  - 15.05.1929

Hs 91:683 - John von Neumann an Hermann Weyl  - 22.07.1929

Hs 91:684 - John von Neumann an Hermann Weyl  - 24.11.1929

Hs 91:685 - John von Neumann an Hermann Weyl  - 05.08.1930

Hs 91:686 - John von Neumann an Hermann Weyl  - 11.12.1931

Hs 91:687 - John von Neumann an Hermann Weyl  - 1920-1955

Hs 975:3327 - John von Neumann an Paul Bernays (1888-1977) - 04.06.1926

Hs 975:3328 - John von Neumann an Paul Bernays (1888-1977) - 10.03.1931

Hs 975:3329 - John von Neumann an Paul Bernays (1888-1977) - 12.06.1933

Here is the letter content:

""" + html_content + """

First output five suggestions for a title, then analyze whether they fulfull the length constraint. Then output the JSON object, without any additional text or markdown formatting."""

    response = await gpt.get_text_response(prompt, model="claude")
    
    # Clean up response - handle random text before JSON object
    text = response.strip()
    
    # First, try to remove markdown code fences if present
    if "```" in text:
        try:
            # Extract between first and last triple backticks
            start = text.find("```")
            fence_line_end = text.find("\n", start)
            end = text.rfind("```")
            if fence_line_end != -1 and end != -1 and end > fence_line_end:
                text = text[fence_line_end+1:end].strip()
        except Exception:
            pass
    
    # Find the JSON object - look for first { and extract to matching }
    json_start = text.find("{")
    if json_start != -1:
        # Find the matching closing brace
        brace_count = 0
        json_end = -1
        for i in range(json_start, len(text)):
            if text[i] == "{":
                brace_count += 1
            elif text[i] == "}":
                brace_count -= 1
                if brace_count == 0:
                    json_end = i + 1
                    break
        
        if json_end != -1:
            text = text[json_start:json_end]
    
    # Parse the JSON response
    try:
        metadata = json.loads(text)
        return metadata
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        print(f"Response was: {text}")
        raise


async def process_single_subfolder(subfolder: Path, html_file: str) -> None:
    """Process a single subfolder to extract and save metadata."""
    html_path = subfolder / html_file
    metadata_path = subfolder / "metadata.json"
    
    # Skip if HTML file doesn't exist
    if not html_path.exists():
        print(f"Skipping {subfolder.name}: {html_file} not found")
        return
    
    # Skip if metadata already exists (optional - comment out to regenerate)
    # if metadata_path.exists():
    #     print(f"Skipping {subfolder.name}: metadata.json already exists")
    #     return
    
    print(f"Processing {subfolder.name}...")
    
    try:
        # Read the HTML content
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Extract metadata
        metadata = await extract_metadata_from_letter(html_content)
        
        # Save metadata to JSON file
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Saved metadata for {subfolder.name}")
        print(f"  Title: {metadata.get('title', 'unknown')}")
        print(f"  Date: {metadata.get('date', 'unknown')}")
        
    except Exception as e:
        print(f"✗ Error processing {subfolder.name}: {e}")
        import traceback
        traceback.print_exc()


async def extract_metadata_for_folder(
    base_folder: Path = Path("public/outputs_gpt-5_2"),
    html_file: str = "html_en.html"
) -> None:
    """
    Extract metadata for all letters in subfolders and save to metadata.json.
    Processes all subfolders in parallel for maximum efficiency.
    
    Args:
        base_folder: Path to the folder containing letter subfolders
        html_file: Name of the HTML file to read from each subfolder (html_de.html or html_en.html)
    """
    base_folder = Path(base_folder)
    
    if not base_folder.exists():
        print(f"Error: Folder {base_folder} does not exist")
        return
    
    # Get all subdirectories
    subfolders = [f for f in base_folder.iterdir() if f.is_dir()]
    
    print(f"Found {len(subfolders)} subfolders to process in parallel")
    
    # Process all subfolders in parallel
    tasks = [process_single_subfolder(subfolder, html_file) for subfolder in subfolders]
    await asyncio.gather(*tasks)


async def main():
    """Main function to run metadata extraction."""
    await extract_metadata_for_folder()


if __name__ == "__main__":
    asyncio.run(main())

