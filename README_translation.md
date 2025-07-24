# German Letter Translation Script

This script translates German letters to English using OpenAI's o3 model with image input/output capabilities.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set your OpenAI API key:
```bash
export OPENAI_API_KEY='your-api-key-here'
```

## Usage

Run the translation script:
```bash
python translate_letters.py
```

## How it works

1. **PDF to Images**: Converts each page of German PDFs to high-resolution images (300 DPI)
2. **Translation**: Sends each page image to OpenAI o3 with the translation prompt
3. **Image Generation**: o3 generates a visually identical English replica with "AI generated" watermark
4. **PDF Assembly**: Combines translated page images back into PDFs with same filenames

## File Structure

- `public/letters_de/` - German letters (input)
- `public/letters_en/` - English translations (output)
- `translate_letters.py` - Main translation script
- `requirements.txt` - Python dependencies

## Translation Prompt

The script uses this prompt for each page:
> Create a 1:1 replica of this letter in English. Copy the handwriting as close as possible. Copy details like a stamp, borders, or holes in the page. The only modification which I would like to make is a small but noticeable watermark with the words "AI generated" written at some prominent point where it does not disturb the rest of the replica.

## Requirements

- OpenAI API key with o3 model access
- Python 3.7+
- PyMuPDF, Pillow, requests libraries