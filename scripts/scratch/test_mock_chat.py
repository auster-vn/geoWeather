import asyncio
from apps.api.core.database import PostgresSessionLocal
from apps.api.routers.chat import run_mock_chat

async def run():
    async with PostgresSessionLocal() as db:
        history = [
            {"role": "user", "content": "Dĩ an thì sao"},
            {"role": "model", "content": "Thời tiết..."}
        ]
        # Should detect "Dĩ An" from history!
        async for chunk in run_mock_chat("Khi nào mưa", db, history):
            print(chunk)

asyncio.run(run())
