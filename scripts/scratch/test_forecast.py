import asyncio
from apps.api.tools.weather_tools import _fetch_open_meteo_forecast

async def run():
    res = await _fetch_open_meteo_forecast(10.82, 106.63)
    print("HOURLY KEYS:", res["hourly"].keys())
    print("DAILY KEYS:", res["daily"].keys())
    print("DAILY UV:", res["daily"]["uv_index_max"])
    print("DAILY SUNRISE:", res["daily"]["sunrise"])
    print("DAILY SUNSET:", res["daily"]["sunset"])

asyncio.run(run())
