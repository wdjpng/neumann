from openai import AsyncOpenAI
import os
import base64
import io
from PIL import Image

client = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))

async def get_text_response(prompt, image=None, model="gpt-5", return_reasoning=False, effort="high"):
    response = None

    if image is not None:
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        image_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

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
                    {
                        "type": "input_image",
                        "image_url": f"data:image/png;base64,{image_base64}",
                        "detail": "high"
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
        reasoning = "\n".join(
            "\n".join(s.text if hasattr(s, 'text') else str(s) for s in item.summary)           
            for item in response.output
            if item.type == "reasoning"
        )

        return response.output_text.strip(), reasoning.strip()

    else:
        return response.output_text.strip()
        
    

