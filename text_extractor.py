import base64
import os
from openai import OpenAI
import re

def img_to_text(image_path):
    """
    Extract text from an image using OpenAI's vision model.
    
    Args:
        image_path (str): Path to the image file
        
    Returns:
        str: Extracted text from the image
    """
    # Initialize OpenAI client
    client = OpenAI()
    
    # Check if image file exists
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")
    
    # Read and encode the image
    with open(image_path, "rb") as image_file:
        image_data = base64.b64encode(image_file.read()).decode('utf-8')
    
    # Determine the image format
    _, ext = os.path.splitext(image_path.lower())
    if ext in ['.jpg', '.jpeg']:
        image_format = "jpeg"
    elif ext == '.png':
        image_format = "png"
    elif ext == '.gif':
        image_format = "gif"
    elif ext == '.webp':
        image_format = "webp"
    else:
        image_format = "jpeg"  # Default fallback
    
    try:
        # Send request to OpenAI's vision model
        response = client.chat.completions.create(
            model="o3",  
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": " Output html and CSS to resemble the letter you were given as closely as possible in style and formatting. Include all text and equations given in the image, but don't try to complete missing content. Also, if a line of text is cut off, do not try to include it in this transcription. Make it minimalist, pretty and aesthethic. Use mathjax for math equations. Output in the usual format of ```html (actual code)``"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/{image_format};base64,{image_data}"
                            }
                        }
                    ]
                }
            ],
        )
        
        # Extract and return the text
        extracted_text = response.choices[0].message.content
        
        return extracted_text.strip()
        
    except Exception as e:
        raise Exception(f"Error extracting text from image: {str(e)}")

import os

def extract_texts_from_folder(folder_path):

    for fname in os.listdir(folder_path):
        print("Extracting text from", fname)
        text = img_to_text(os.path.join(folder_path, fname))
        # check regex and extract
        lines = text.splitlines()
        assert lines and lines[0].strip() == "```html" and lines[-1].strip() == "```"
        text = "\n".join(lines[1:-1])
        
        with open(f"public/html/{fname.replace('.jpg', '.html')}", 'w') as f:
            f.write(text)
        
        print("Extracted text to", fname.replace('.jpg', '.html'))

def unite_html(text):
    try:
        # Send request to OpenAI's vision model
        client = OpenAI()
        response = client.chat.completions.create(
            model="o3",  
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "You will be given multiple html files all attempting to transcribe different parts of one letter in order. Your task is to unite them into one html file. They already contain a lot of formatting, which you should synthesize to one single consistent formatting. Keep the formatting that seems the prettiest and most aesthethic while also being somewhat minimalistic. If it seems like text is duplicate, keep only one copy. Output in the usual format of ```html (actual code)``" + text
                        },
                    ]
                }
            ],
        )
        
        # Extract and return the text
        extracted_text = response.choices[0].message.content
        assert extracted_text.strip().startswith("```html") and extracted_text.strip().endswith("```")
        return extracted_text.strip()[7:-3].strip()
        
    except Exception as e:
        raise Exception(f"Error extracting text from image: {str(e)}")
def unite_all_html_files(folder_path):
    for file in os.listdir(folder_path):
        if not file.endswith('page_1_chunk_1.html'): continue

        i = 1
        text = ""
        base_name = file[:file.index("page_1_chunk_1")]
        while os.path.exists(f"{folder_path}/page_{i}chuk_1.html"):
            j = 1
            while os.path.exists(f"{folder_path}/page_{i}chuk_{j}.html"):
                with open(f"{folder_path}/page_{i}chuk_{j}.html", 'r') as f:
                    text += "Html file number " + str(i+j-1) + ":\n" + f.read() + "\n\n"
                j+=1

            i += 1
        
        with open(f"public/html/{base_name}.html", 'w') as f:
            f.write(unite_html(text))

unite_all_html_files("public/html_parts")


import sys
if len(sys.argv) < 2:
    print("Usage: python text_extractor.py <input_image_file>")
    sys.exit(1)

extract_texts_from_folder(sys.argv[1])

