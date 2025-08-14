from pathlib import Path

def is_html_content(text):
    # Simple check: contains <html> or starts with <!DOCTYPE html> or has html tag
    t = text.strip().lower()
    return "<html" in t or t.startswith("<!doctype html") or t.startswith("<html")

for file in Path("public/outputs_gpt-5").glob("*/chunks/*text.html"):
    new_file = file.with_name(file.name.replace("text.html", "html").replace("reasoning", "reasoning_in_chunk_extractor"))
    file.rename(new_file)
    print(f"Renamed {file} -> {new_file}")
