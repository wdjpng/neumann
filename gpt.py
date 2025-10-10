from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
import os
import base64
import io
from PIL import Image
from typing import List


async def get_text_response(prompt, image=None, image_list: List[Image.Image] = None, model="gpt-5", return_reasoning=False, effort="medium"):
    response = None
    
    if image_list is not None and image is not None:
        raise ValueError("Only one of image or image_list can be provided")
    
    if image is not None: image_list = [image]
    
    # Handle Claude model
    if model == "claude":
        # Check if images are provided - Claude doesn't support images yet
        if image_list is not None:
            raise ValueError("Image attachments are not currently supported with Claude model")
        
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            print("ERROR: ANTHROPIC_API_KEY environment variable is not set!")
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set")
        
        try:
            client = AsyncAnthropic(api_key=api_key, timeout=600)
            
            print(f"Calling Claude API with model: claude-sonnet-4-5")
            response = await client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=10000,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            print(f"Claude API call successful, response length: {len(response.content[0].text)}")
            return response.content[0].text
        except Exception as e:
            print(f"ERROR calling Claude API:")
            print(f"  Exception type: {type(e).__name__}")
            print(f"  Exception message: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    
    client = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'), timeout=600)
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
        
    

