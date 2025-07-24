from openai import OpenAI
import base64

client = OpenAI() 

prompt = "Create a 1:1 replica of this letter in English. Copy the handwriting as close as possible. Copy details like a stamp, borders, or holes in the page. The only modification which I would like to make is a small but noticable watermark with the words \"AI generated\" written at some prominent point where it does not disturb the rest of the replica. As part of your text reponse after the image generation is finished, please include the full prompt with which you queried the image mode"

prompt2 = ".\n\nAfter you have generated what the tool call should be, don't actually call the tool! Instead print the full call including all context / text you inteded to send to the tool"
response = client.responses.create(
    model="o3",
    reasoning={"effort": "high"},
    input=[{
        "role": "user",
        "content": [
            {"type": "input_text", "text": prompt },
            {
                "type": "input_image",
                "image_url": "data:image/png;base64," + base64.b64encode(open("/home/wdjpng/repos/neumann2/public/hidden_extracted/Hs_957_3327-3329_1_page_1.jpg", "rb").read()).decode(),
            },
        ],
    }],
    tools=[{"type": "image_generation"}],
)

import pickle
with open("response4.pkl", "wb") as f:
    pickle.dump(response, f)
# Save the image to a file
image_data = [
    output.result
    for output in response.output
    if output.type == "image_generation_call"
]
print(response.output_text)
if image_data:
    image_base64 = image_data[0]
    with open("otter_3_high_4.png", "wb") as f:
        f.write(base64.b64decode(image_base64))