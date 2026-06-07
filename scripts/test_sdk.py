import sys
import asyncio
sys.path.insert(0, "/app")

from google import genai
from google.genai import types

async def test_google_genai():
    print("Testing google-genai SDK auth ASYNC")
    client = genai.Client(api_key="REDACTED_GEMINI_API_KEY")
    
    try:
        chat = client.aio.chats.create(
            model="gemini-2.5-flash",
            history=[],
            config=types.GenerateContentConfig(
                system_instruction="Hello System",
            )
        )
        response_stream = await chat.send_message_stream("Hello")
        async for chunk in response_stream:
            print("Chunk:", chunk.text)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    asyncio.run(test_google_genai())
