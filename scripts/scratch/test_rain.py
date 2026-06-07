import asyncio
from apps.api.core.database import PostgresSessionLocal
from apps.api.tools.weather_tools import execute_tool

async def run():
    async with PostgresSessionLocal() as db:
        res = await execute_tool('get_rain_forecast', {'city_name': 'Ho Chi Minh', 'target_date': '2026-06-08'}, db)
        print(res)

asyncio.run(run())
