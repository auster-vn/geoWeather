from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import httpx
import redis.asyncio as redis

logger = logging.getLogger(__name__)

# Redis Client Singleton
_redis_client = None

async def get_redis_client():
    global _redis_client
    if _redis_client is None:
        from apps.api.core.config import settings
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client

async def _fetch_with_cache(url: str, params: dict, ttl_seconds: int = 900) -> dict:
    """Fetch data from HTTP or Redis cache."""
    r_client = await get_redis_client()
    # Create a stable cache key
    sorted_params = dict(sorted(params.items()))
    cache_key = f"weather_cache:{url}:{json.dumps(sorted_params)}"
    
    cached = await r_client.get(cache_key)
    if cached:
        logger.info(f"Cache HIT for {cache_key}")
        return json.loads(cached)
        
    logger.info(f"Cache MISS for {cache_key}. Fetching...")
    async with httpx.AsyncClient(timeout=12) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        data = r.json()
        await r_client.setex(cache_key, ttl_seconds, json.dumps(data))
        return data

# ─── Tool Definitions ─────────────────────────────────────────────────────────

def weather_tool_definitions() -> List[Dict[str, Any]]:
    return [
        {
            "name": "get_weather_by_city",
            "description": "Finds a city by name and returns its current weather parameters.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "city_name": {
                        "type": "string",
                        "description": "The name of the city, e.g., 'Hanoi' or 'Ho Chi Minh'."
                    }
                },
                "required": ["city_name"]
            }
        },
        {
            "name": "get_weather_by_coords",
            "description": "Returns current weather parameters for the nearest city to specified lat/lon coordinates.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "lat": {"type": "number", "description": "Latitude coordinate"},
                    "lon": {"type": "number", "description": "Longitude coordinate"}
                },
                "required": ["lat", "lon"]
            }
        },
        {
            "name": "compare_cities",
            "description": "Compares current weather details across a list of cities.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "cities": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of city names to compare."
                    }
                },
                "required": ["cities"]
            }
        },
        {
            "name": "get_rain_forecast",
            "description": (
                "Returns a 7-day hourly rain and temperature forecast for a city. "
                "Use this when the user asks WHEN it will rain, rain probability, "
                "or what the temperature/weather will be like at a specific hour."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "city_name": {
                        "type": "string",
                        "description": "City name, e.g. 'Da Nang', 'Hanoi'."
                    },
                    "target_date": {
                        "type": "string",
                        "description": "Optional ISO date string 'YYYY-MM-DD'."
                    }
                },
                "required": ["city_name"]
            }
        },
        {
            "name": "get_daily_forecast",
            "description": (
                "Returns a 7-day daily summary forecast including max/min temperature, UV index, and conditions. "
                "Use this when the user asks for a general forecast for tomorrow, next week, or specific days."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "city_name": {
                        "type": "string",
                        "description": "City name, e.g. 'Ho Chi Minh'."
                    }
                },
                "required": ["city_name"]
            }
        },
        {
            "name": "get_air_quality_and_uv",
            "description": (
                "Returns current Air Quality Index (AQI), PM2.5, PM10, and UV Index for a city. "
                "Use this when the user asks about air quality, pollution, dust, or UV/sun intensity."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "city_name": {
                        "type": "string",
                        "description": "City name, e.g. 'Hanoi'."
                    }
                },
                "required": ["city_name"]
            }
        },
        {
            "name": "get_sun_times",
            "description": (
                "Returns sunrise and sunset times for a city. "
                "Use this when the user asks about dawn, dusk, hoang hon, or binh minh."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "city_name": {
                        "type": "string"
                    },
                    "target_date": {
                        "type": "string"
                    }
                },
                "required": ["city_name"]
            }
        }
    ]


# ─── Shared helpers ───────────────────────────────────────────────────────────

async def _resolve_city(city_name: str, db: AsyncSession) -> Optional[Dict[str, Any]]:
    """Look up a city's coordinates and metadata from the PostGIS DB."""
    import unicodedata
    
    def remove_diacritics(text_val: str) -> str:
        normalized = unicodedata.normalize('NFKD', text_val)
        cleaned = "".join([c for c in normalized if not unicodedata.combining(c)])
        return cleaned.replace('Đ', 'D').replace('đ', 'd')

    normalized_name = remove_diacritics(city_name).strip().lower()
    
    # Map common aliases
    if normalized_name in ["sai gon", "sg", "hcm", "hcmc"]:
        city_name = "Ho Chi Minh"
    elif normalized_name == "hn":
        city_name = "Hanoi"

    q = text("""
        SELECT geoname_id, city_name, country_code,
               ST_Y(geom) AS lat, ST_X(geom) AS lon, timezone
        FROM cities
        WHERE ascii_name ILIKE '%' || :name || '%' OR city_name ILIKE '%' || :name || '%'
        ORDER BY population DESC
        LIMIT 1;
    """)
    res = await db.execute(q, {"name": city_name})
    row = res.mappings().first()
    return dict(row) if row else None


async def _fetch_open_meteo_forecast(lat: float, lon: float, tz: str = "Asia/Bangkok") -> Dict[str, Any]:
    """
    Call Open-Meteo /v1/forecast API.
    Returns hourly precipitation + weather code and daily sunrise/sunset.
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "precipitation_probability,precipitation,weather_code,temperature_2m",
        "daily": "sunrise,sunset,precipitation_sum,precipitation_hours,weather_code,temperature_2m_max,temperature_2m_min,uv_index_max",
        "forecast_days": 7,
        "timezone": tz or "Asia/Bangkok",
    }
    return await _fetch_with_cache(url, params)


def _wmo_desc(code: int) -> str:
    """Convert WMO weather code to a short Vietnamese description."""
    if code == 0:              return "trời quang"
    if code in (1, 2, 3):     return "có mây"
    if code in (45, 48):      return "sương mù"
    if code in (51, 53):      return "mưa phùn nhẹ"
    if code == 55:             return "mưa phùn dày"
    if code in (61, 63):      return "mưa vừa"
    if code == 65:             return "mưa to"
    if code in (71, 73, 75, 77): return "tuyết rơi"
    if code in (80, 81, 82):  return "mưa rào"
    if code in (85, 86):      return "mưa tuyết"
    if code in (95, 96, 99):  return "có dông sét"
    return "không xác định"


# ─── Tool Executor ────────────────────────────────────────────────────────────

async def execute_tool(name: str, arguments: Dict[str, Any], db: AsyncSession) -> Dict[str, Any]:
    logger.info(f"Executing tool '{name}' with args: {arguments}")

    # ── get_weather_by_city ────────────────────────────────────────────────────
    if name == "get_weather_by_city":
        city_name = arguments.get("city_name")
        city = await _resolve_city(city_name, db)
        if not city:
            return {"error": f"City '{city_name}' not found in database."}

        # Try cached weather from DB first
        weather_query = text("""
            SELECT wc.*, c.city_name, c.country_code
            FROM weather_current wc
            JOIN cities c ON c.geoname_id = wc.location_id
            WHERE wc.location_id = :loc_id;
        """)
        w_res = await db.execute(weather_query, {"loc_id": city["geoname_id"]})
        weather = w_res.mappings().first()

        if weather:
            return dict(weather)

        # ── Fallback: fetch live from Open-Meteo ──────────────────────────────
        logger.info(f"No cached weather for {city['city_name']}, fetching live from Open-Meteo...")
        try:
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": city["lat"],
                "longitude": city["lon"],
                "current": (
                    "temperature_2m,relative_humidity_2m,apparent_temperature,"
                    "precipitation,weather_code,wind_speed_10m,wind_direction_10m,"
                    "cloud_cover,pressure_msl,visibility"
                ),
                "timezone": city.get("timezone") or "Asia/Bangkok",
                "forecast_days": 1,
            }
            data = await _fetch_with_cache(url, params)

            cur = data.get("current", {})
            return {
                "city_name": city["city_name"],
                "country_code": city["country_code"],
                "lat": city["lat"],
                "lon": city["lon"],
                "temperature": cur.get("temperature_2m"),
                "feels_like": cur.get("apparent_temperature"),
                "humidity": cur.get("relative_humidity_2m"),
                "wind_speed": cur.get("wind_speed_10m"),
                "wind_direction": cur.get("wind_direction_10m"),
                "precipitation": cur.get("precipitation"),
                "condition": _wmo_desc(cur.get("weather_code", 0)),
                "cloud_cover": f"{cur.get('cloud_cover', 0)}%",
                "pressure": cur.get("pressure_msl"),
                "visibility": f"{cur.get('visibility', 0)}m",
                "source": "open-meteo-live",
            }
        except Exception as e:
            logger.error(f"Open-Meteo live fetch failed for {city['city_name']}: {e}")
            return {
                "city": city["city_name"],
                "country": city["country_code"],
                "lat": city["lat"],
                "lon": city["lon"],
                "note": "No cached weather data and live fetch failed.",
            }

    # ── get_weather_by_coords ─────────────────────────────────────────────────
    elif name == "get_weather_by_coords":
        lat = arguments.get("lat")
        lon = arguments.get("lon")
        query = text("""
            WITH nearest_city AS (
                SELECT geoname_id, city_name, country_code
                FROM cities
                ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
                LIMIT 1
            )
            SELECT nc.*, wc.temperature, wc.feels_like, wc.humidity,
                   wc.wind_speed, wc.weather_code
            FROM nearest_city nc
            LEFT JOIN weather_current wc ON wc.location_id = nc.geoname_id;
        """)
        result = await db.execute(query, {"lat": lat, "lon": lon})
        row = result.mappings().first()
        if not row:
            return {"error": "No near weather station found."}
        return dict(row)

    # ── compare_cities ────────────────────────────────────────────────────────
    elif name == "compare_cities":
        cities = arguments.get("cities", [])
        results = []
        for city_name in cities:
            res = await execute_tool("get_weather_by_city", {"city_name": city_name}, db)
            if "error" not in res:
                results.append(res)
        return {"comparisons": results}

    # ── get_rain_forecast ─────────────────────────────────────────────────────
    elif name == "get_rain_forecast":
        city_name   = arguments.get("city_name")
        target_date = arguments.get("target_date")  # optional "YYYY-MM-DD"

        city = await _resolve_city(city_name, db)
        if not city:
            return {"error": f"City '{city_name}' not found."}

        try:
            data = await _fetch_open_meteo_forecast(
                city["lat"], city["lon"], city.get("timezone", "Asia/Bangkok")
            )
        except Exception as e:
            return {"error": f"Failed to fetch forecast from Open-Meteo: {e}"}

        times  = data["hourly"]["time"]
        probs  = data["hourly"]["precipitation_probability"]
        precip = data["hourly"]["precipitation"]
        codes  = data["hourly"]["weather_code"]
        temps  = data["hourly"]["temperature_2m"]

        # Build filtered hourly list
        hourly = []
        for i, t in enumerate(times):
            if target_date and not t.startswith(target_date):
                continue
            hourly.append({
                "time": t,
                "hour": t[11:16],
                "temperature": temps[i],
                "precip_prob_pct": probs[i],
                "precipitation_mm": precip[i],
                "condition": _wmo_desc(codes[i]),
            })

        # Without date filter: keep next 72 hours (3 days)
        if not target_date:
            hourly = hourly[:72]

        # Smart summary: find first "likely rain" and first "clearing" window
        RAIN_PROB_THRESHOLD = 40  # % — considered likely rain
        first_rain  = next((h for h in hourly if h["precip_prob_pct"] >= RAIN_PROB_THRESHOLD), None)
        first_clear = None
        for idx in range(len(hourly) - 2):
            if all(hourly[idx + j]["precip_prob_pct"] < RAIN_PROB_THRESHOLD for j in range(3)):
                first_clear = hourly[idx]
                break

        # Daily summary
        daily_dates  = data["daily"]["time"]
        daily_precip = data["daily"]["precipitation_sum"]
        daily_hours  = data["daily"]["precipitation_hours"]
        daily_codes  = data["daily"]["weather_code"]
        daily = []
        for i, d in enumerate(daily_dates):
            if target_date and d != target_date:
                continue
            daily.append({
                "date": d,
                "total_rain_mm": daily_precip[i],
                "rain_hours": daily_hours[i],
                "condition": _wmo_desc(daily_codes[i]),
            })

        return {
            "city": city["city_name"],
            "lat": city["lat"],
            "lon": city["lon"],
            "target_date": target_date,
            "summary": {
                "first_likely_rain": first_rain,
                "first_clear_after_rain": first_clear,
            },
            "daily_summary": daily,
            "hourly_forecast": hourly,
        }

    # ── get_daily_forecast ────────────────────────────────────────────────────
    elif name == "get_daily_forecast":
        city_name = arguments.get("city_name")
        city = await _resolve_city(city_name, db)
        if not city:
            return {"error": f"City '{city_name}' not found."}

        try:
            data = await _fetch_open_meteo_forecast(
                city["lat"], city["lon"], city.get("timezone", "Asia/Bangkok")
            )
        except Exception as e:
            return {"error": f"Failed to fetch forecast from Open-Meteo: {e}"}

        daily_dates = data["daily"]["time"]
        daily_tmax = data["daily"]["temperature_2m_max"]
        daily_tmin = data["daily"]["temperature_2m_min"]
        daily_uv = data["daily"]["uv_index_max"]
        daily_codes = data["daily"]["weather_code"]
        daily_rain = data["daily"]["precipitation_sum"]

        daily = []
        for i, d in enumerate(daily_dates):
            daily.append({
                "date": d,
                "temp_max": daily_tmax[i],
                "temp_min": daily_tmin[i],
                "uv_index_max": daily_uv[i],
                "total_rain_mm": daily_rain[i],
                "condition": _wmo_desc(daily_codes[i]),
            })

        return {
            "city": city["city_name"],
            "lat": city["lat"],
            "lon": city["lon"],
            "daily_forecast": daily,
        }

    # ── get_air_quality_and_uv ────────────────────────────────────────────────
    elif name == "get_air_quality_and_uv":
        city_name = arguments.get("city_name")
        city = await _resolve_city(city_name, db)
        if not city:
            return {"error": f"City '{city_name}' not found."}

        try:
            url = "https://air-quality-api.open-meteo.com/v1/air-quality"
            params = {
                "latitude": city["lat"],
                "longitude": city["lon"],
                "current": "european_aqi,us_aqi,pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone,uv_index",
                "timezone": city.get("timezone", "Asia/Bangkok")
            }
            data = await _fetch_with_cache(url, params)

            cur = data.get("current", {})
            return {
                "city": city["city_name"],
                "lat": city["lat"],
                "lon": city["lon"],
                "aqi": cur.get("us_aqi"),
                "pm2_5": cur.get("pm2_5"),
                "pm10": cur.get("pm10"),
                "uv_index": cur.get("uv_index"),
                "nitrogen_dioxide": cur.get("nitrogen_dioxide"),
                "ozone": cur.get("ozone"),
                "note": "US AQI: 0-50 Good, 51-100 Moderate, 101-150 Unhealthy for Sensitive Groups, 151-200 Unhealthy, 201-300 Very Unhealthy, 301+ Hazardous. UV: 0-2 Low, 3-5 Mod, 6-7 High, 8-10 V.High, 11+ Extreme."
            }
        except Exception as e:
            logger.error(f"Air quality fetch failed: {e}")
            return {"error": f"Air quality fetch failed: {e}"}

    # ── get_sun_times ──────────────────────────────────────────────────────────
    elif name == "get_sun_times":
        city_name   = arguments.get("city_name")
        target_date = arguments.get("target_date")

        city = await _resolve_city(city_name, db)
        if not city:
            return {"error": f"City '{city_name}' not found."}

        try:
            data = await _fetch_open_meteo_forecast(
                city["lat"], city["lon"], city.get("timezone", "Asia/Bangkok")
            )
        except Exception as e:
            return {"error": f"Failed to fetch sun times from Open-Meteo: {e}"}

        daily_dates   = data["daily"]["time"]
        daily_sunrise = data["daily"]["sunrise"]
        daily_sunset  = data["daily"]["sunset"]

        sun_schedule = []
        for i, d in enumerate(daily_dates):
            if target_date and d != target_date:
                continue
            sunrise_str = daily_sunrise[i]   # "2026-06-05T05:14"
            sunset_str  = daily_sunset[i]    # "2026-06-05T18:35"
            sunrise_hm  = sunrise_str[11:16]  # "05:14"
            sunset_hm   = sunset_str[11:16]   # "18:35"
            daylight = round(
                (datetime.fromisoformat(sunset_str) - datetime.fromisoformat(sunrise_str)).seconds / 3600, 2
            )
            sun_schedule.append({
                "date": d,
                "sunrise": sunrise_hm,
                "sunset": sunset_hm,
                "daylight_hours": daylight,
            })

        return {
            "city": city["city_name"],
            "lat": city["lat"],
            "lon": city["lon"],
            "timezone": city.get("timezone", "Asia/Bangkok"),
            "sun_schedule": sun_schedule,
        }

    return {"error": f"Unknown tool: {name}"}
