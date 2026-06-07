import asyncio
import sys
import os

sys.path.insert(0, "/app")
from apps.api.tools.weather_tools import execute_tool

async def test_tools():
    from apps.api.core.database import PostgresSessionLocal
    
    print("Testing tools...")
    async with PostgresSessionLocal() as db:
        # 1. get_daily_forecast
        print("Testing get_daily_forecast for Ha Noi...")
        daily = await execute_tool("get_daily_forecast", {"city_name": "Ha Noi"}, db)
        print(daily.keys() if isinstance(daily, dict) else daily)
        if "error" in daily:
            print("ERROR:", daily["error"])
        else:
            print("SUCCESS! Daily forecast returned.")

        # 2. get_air_quality_and_uv
        print("Testing get_air_quality_and_uv for Da Nang...")
        aqi = await execute_tool("get_air_quality_and_uv", {"city_name": "Da Nang"}, db)
        print(aqi.keys() if isinstance(aqi, dict) else aqi)
        if "error" in aqi:
            print("ERROR:", aqi["error"])
        else:
            print("SUCCESS! AQI and UV returned.")

if __name__ == "__main__":
    asyncio.run(test_tools())
