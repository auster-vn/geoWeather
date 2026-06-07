import asyncio
import os
from google import genai
from google.genai import types

async def main():
    api_key = os.getenv("GEMINI_API_KEY", "AQ.Ab8RN6I1vLRRzuzSVPG1c2JMH8D7Wts5U854XZvxXhDSiOym0A")
    client = genai.Client(api_key=api_key)
    
    # Create dummy tiny webm or just text to test if the method exists
    dummy_audio = b'RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00'
    part = types.Part.from_bytes(data=dummy_audio, mime_type='audio/wav')
    print("Part created successfully:", type(part))
    
    try:
        res = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                part,
                'Transcribe this audio.'
            ]
        )
        print("Response:", res.text)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    asyncio.run(main())
