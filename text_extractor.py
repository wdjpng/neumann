import base64
import os
from openai import OpenAI
import re

def img_to_text(image_path, filename=None):
    """
    Extract text from an image using OpenAI's vision model.
    
    Args:
        image_path (str): Path to the image file
        filename (str, optional): Filename for error messages
        
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
    
    max_retries = 3
    timeout_seconds = 300  # 5 minutes
    display_name = filename or os.path.basename(image_path)
    
    for attempt in range(max_retries):
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
                                "text": "Output html and CSS to resemble the letter you were given as closely as possible in style and formatting. Include all text and equations given in the image, but don't try to complete missing content. Make it pretty, aesthethic, and minimalist while closely fitting the original formatting, font, and style. Also, if a line of text is cut off, do not try to include it in this transcription. Use mathjax for math equations. Make sure that all content you generate is one the Output in the usual format of ```html (actual code)```"
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
                timeout=timeout_seconds
            )
            
            # Extract and return the text
            extracted_text = response.choices[0].message.content
            return extracted_text.strip()
            
        except Exception as e:
            error_msg = str(e).lower()
            # Check if this is a timeout-related error
            if 'timeout' in error_msg or 'timed out' in error_msg:
                if attempt < max_retries - 1:
                    print(f"Timeout on file {display_name}")
                    continue  # Try again
                else:
                    print(f"Timed out on file {display_name}. Giving up...")
                    raise Exception(f"Timeout error on {display_name}: {str(e)}")
            else:
                # For non-timeout errors, raise immediately
                raise Exception(f"Error extracting text from image: {str(e)}")
    
    # This should never be reached due to the loop logic above
    raise Exception(f"Unexpected error in img_to_text for {display_name}")

import os

def convert_chunk_to_html(fname, folder_path):
    print("Beginning extraction of " + fname)
    text = img_to_text(os.path.join(folder_path, fname), filename=fname)
    # check regex and extract
    lines = text.splitlines()
    
    assert lines and lines[0].strip() == "```html" and lines[-1].strip() == "```"
    text = "\n".join(lines[1:-1])
    with open(f"public/html_parts/{fname.replace('.jpg', '.html')}", 'w') as f:
        f.write(text)
    print("Extracted text to", fname.replace('.jpg', '.html'))

# Goes through all images in folder and converts to html
def convert_chunks_to_html(folder_path):
    import concurrent.futures
    fnames = os.listdir(folder_path)
    with concurrent.futures.ThreadPoolExecutor() as executor:
        executor.map(lambda fname: convert_chunk_to_html(fname, folder_path), fnames)

# Unifies all html files of one letter into one html file
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
                            "text": "You will be given multiple html files all attempting to transcribe different parts of one letter in order. Your task is to unite them into one html file. They already contain a lot of formatting, which you should synthesize to one single consistent formatting. Keep the formatting that seems the prettiest and most aesthethic while also being somewhat minimalistic. If it seems like text is duplicate, keep only one copy. Make sure to keep the design of the header, especially if it is pretty. Also make text size and the way equations are displayed uniform in all parts, except possibly in the header where naturally text may be of different sizes. Also if the consensus is that some form of ruled background should be used, use one of the provided patterns, but make sure to have every line of text actually be on the respective horizontal lines in the pattern. Output in the usual format of ```html (actual code)```" + text
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

# Unifies all html files of all letter into one per letter
def unite_chunks(folder_path):  
    for file in os.listdir(folder_path):
        if not file.endswith('page_1_chunk_1.html'): continue
        i = 1
        text = ""
        base_name = file[:file.index("page_1_chunk_1")]
        print("Unifying " + base_name)
      
        counter = 1
        while os.path.exists(f"{folder_path}/{base_name}page_{i}_chunk_1.html"):
            j = 1
            while os.path.exists(f"{folder_path}/{base_name}page_{i}_chunk_{j}.html"):
                with open(f"{folder_path}/{base_name}page_{i}_chunk_{j}.html", 'r') as f:
                    text += "Html file number " + str(counter) + ":\n" + f.read() + "\n\n"
                counter += 1
                j+=1

            i += 1
        print("Loaded " + str(counter) + " chunks")
        with open(f"public/html_de/{base_name}.html", 'w') as f:
            f.write(unite_html(text))

def translate_html_to_english(text):
  
    client = OpenAI()
    response = client.chat.completions.create(
        model="o3",  
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "You will be given an html file. Your task is to translate it to english. Preserve the original's linguistic style. Output in the usual format of ```html (actual code)``" + text
                    }
                ]
            }
        ]
    )
    return response.choices[0].message.content.strip()[7:-3].strip()


convert_chunk_to_html("Hs_91_676-687-pages-3_page_1_chunk_1.jpg", "public/chunks")
# convert_chunks_to_html("public/chunks")
# unite_chunks("public/html_parts")

# for file in os.listdir("public/html_de"):
#     with open(f"public/html_de/{file}", 'r') as f:
#         text = f.read()
#     with open(f"public/html_en/{file}", 'w') as f:
#         f.write(translate_html_to_english(text))



