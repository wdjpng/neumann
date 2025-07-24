import os
import json
import base64
from openai import OpenAI
import io
import glob
from pdf2image import convert_from_path

client = OpenAI()

def pil_image_to_base64(image, format="JPEG"):
    buffered = io.BytesIO()
    image.save(buffered, format=format)
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def extract_metadata(letter_name, first_page_image, last_page_image):
    first_page_b64 = pil_image_to_base64(first_page_image)
    
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "These are the first and last pages of a letter. Please extract the author, recipient, and date of the letter. Also, provide a two-sentence summary and a suggested, succinct (40-60 characters) title. Please return the information in a json format, with the keys 'author', 'recipient', 'date', 'summary', and 'title'. If any of the information is not available, please use the value 'unknown'. Date should be in the format Month xth, yyyy. For additional context, here some of the reference numnber (the number at the top left), author, recipient, date pairs: Hs 91:676 - John von Neumann an Hermann Weyl  - 01.03.1925\n\nHs 91:677 - John von Neumann an Hermann Weyl  - 25.07.1925\n\nHs 91:678 - John von Neumann an Hermann Weyl  - 27.06.1927\n\nHs 91:679 - John von Neumann an Hermann Weyl  - 30.06.1928\n\nHs 91:680 - John von Neumann an Hermann Weyl  - 16.07.1928\n\nHs 91:681 - John von Neumann an Hermann Weyl  - 19.08.1928\n\nHs 91:682 - John von Neumann an Hermann Weyl  - 15.05.1929\n\nHs 91:683 - John von Neumann an Hermann Weyl  - 22.07.1929\n\nHs 91:684 - John von Neumann an Hermann Weyl  - 24.11.1929\n\nHs 91:685 - John von Neumann an Hermann Weyl  - 05.08.1930\n\nHs 91:686 - John von Neumann an Hermann Weyl  - 11.12.1931\n\nHs 91:687 - John von Neumann an Hermann Weyl  - 1920-1955\n\nHs 975:3327 - John von Neumann an Paul Bernays (1888-1977) - 04.06.1926\n\nHs 975:3328 - John von Neumann an Paul Bernays (1888-1977) - 10.03.1931\n\nHs 975:3329 - John von Neumann an Paul Bernays (1888-1977) - 12.06.1933 " 
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{first_page_b64}"
                    }
                }
            ]
        }
    ]
    
    if first_page_image is not last_page_image:
        last_page_b64 = pil_image_to_base64(last_page_image)
        messages[0]["content"].append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{last_page_b64}"
                }
            }
        )
    
    response = client.chat.completions.create(
        model="o4-mini",
        messages=messages,
        response_format={"type": "json_object"}
    )
    
    return json.loads(response.choices[0].message.content)

def main():
    pdf_directory = "public/samples2/"
    output_metadata_dir = "public/metadata"
    output_metadata_file = os.path.join(output_metadata_dir, "metadata.json")

    if not os.path.exists(output_metadata_dir):
        os.makedirs(output_metadata_dir)

    all_metadata = {}
    
    pdf_files = glob.glob(os.path.join(pdf_directory, "*.pdf"))

    if not pdf_files:
        print(f"No PDF files found in {pdf_directory}")
        return

    for pdf_file in pdf_files:
        letter_name = os.path.splitext(os.path.basename(pdf_file))[0]
        print(f"Processing letter: {letter_name}")
        try:
            images_in_memory = convert_from_path(pdf_file)
            
            if not images_in_memory:
                print(f"Could not extract any pages from {pdf_file}")
                continue
            
            first_page_image = images_in_memory[0]
            last_page_image = images_in_memory[-1]

            metadata = extract_metadata(letter_name, first_page_image, last_page_image)
            all_metadata[letter_name] = {
                "page_count": len(images_in_memory),
                "metadata": metadata
            }
        except Exception as e:
            print(f"Error processing {letter_name}: {e}")
            
    with open(output_metadata_file, "w") as f:
        json.dump(all_metadata, f, indent=4)
    print(f"Metadata saved to {output_metadata_file}")


if __name__ == "__main__":
    main()
