from openai import AsyncOpenAI
import os
import base64
import io
from PIL import Image
from typing import List

client = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))

async def get_text_response(prompt, image=None, image_list: List[Image.Image] = None, model="gpt-5", return_reasoning=False, effort="high"):
    response = None

    if image_list is not None and image is not None:
        raise ValueError("Only one of image or image_list can be provided")
    
    if image is not None: image_list = [image]
    
    if image_list is not None:
        image_base64_list = []
        for image in image_list:
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            image_base64_list.append(base64.b64encode(buffered.getvalue()).decode('utf-8'))

        response = await client.responses.create(
            model=model,
            input=[
                {
                "role": "user",
                "content": [
                    {
                    "type": "input_text",
                    "text": prompt
                    },
                    *[
                        {
                            "type": "input_image",
                            "image_url": f"data:image/png;base64,{image_base64}",
                            "detail": "high"
                        } for image_base64 in image_base64_list
                    ]
                ]
                }
            ],
            text={
                "format": {
                "type": "text"
                },
                "verbosity": "medium"
            },
            reasoning={
                "effort": effort,
                "summary": "detailed"
            },
            tools=[]
        )

    else:
        response = await client.responses.create(
                model=model,
                input=[
                    {
                    "role": "user",
                    "content": [
                        {
                        "type": "input_text",
                        "text": prompt
                        }
                    ]
                    }
                ],
                text={
                    "format": {
                    "type": "text"
                    },
                    "verbosity": "medium"
                },
                reasoning={
                    "effort": effort,
                    "summary": "detailed"
                },
                tools=[]
            )
    
    if return_reasoning:
        reasoning = "\n\n".join(
            "\n".join(s.text if hasattr(s, 'text') else str(s) for s in item.summary)
            for item in response.output
            if item.type == "reasoning"
        )

        return response.output_text.strip(), reasoning.strip()

    else:
        return response.output_text.strip()
        
    

