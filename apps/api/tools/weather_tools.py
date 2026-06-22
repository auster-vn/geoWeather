from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import httpx

logger = logging.getLogger(__name__)

async def get_redis_client():
    """Delegate to the shared Redis client (with timeouts) from core/redis.py."""
    try:
        from apps.api.core.redis import get_redis
        return await get_redis()
    except Exception:
        return None

async def _fetch_with_cache(url: str, params: dict, ttl_seconds: int = 900) -> dict:
    """Fetch data from HTTP or Redis cache."""
    # --- MOCK OPEN-METEO (For local testing only — triggered by MOCK_WEATHER=true) ---
    import os
    if os.environ.get("MOCK_WEATHER", "false").lower() == "true" and "open-meteo.com" in url:
        import math
        from datetime import datetime, timedelta
        import zoneinfo
        
        tz_str = params.get("timezone", "Asia/Bangkok")
        try:
            zone = zoneinfo.ZoneInfo(tz_str)
        except Exception:
            zone = zoneinfo.ZoneInfo("UTC")
            
        now = datetime.now(zone)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        data = {"is_mock": True}
        
        if "air-quality" in url:
            data["current"] = {
                "us_aqi": 42,
                "pm2_5": 12.5,
                "pm10": 20.0,
                "uv_index": 6.5,
                "nitrogen_dioxide": 15.0,
                "ozone": 30.0
            }
            return data
            
        if "current" in params:
            data["current"] = {
                "temperature_2m": 30.5,
                "apparent_temperature": 34.0,
                "relative_humidity_2m": 65,
                "wind_speed_10m": 12.5,
                "wind_direction_10m": 180,
                "precipitation": 0.0,
                "weather_code": 2,
                "cloud_cover": 45,
                "pressure_msl": 1012,
                "visibility": 10000
            }
            
        if "hourly" in params:
            days = int(params.get("forecast_days", 7))
            hourly_time = []
            hourly_precip_prob = []
            hourly_precip = []
            hourly_weather_code = []
            hourly_temp = []
            
            for i in range(24 * days):
                t = today + timedelta(hours=i)
                hourly_time.append(t.strftime("%Y-%m-%dT%H:00"))
                temp = 28 + 5 * math.sin((i - 6) * math.pi / 12)
                hourly_temp.append(round(temp, 1))
                
                if 14 <= t.hour <= 16:
                    hourly_precip_prob.append(60)
                    hourly_precip.append(2.5)
                    hourly_weather_code.append(61)
                else:
                    hourly_precip_prob.append(10)
                    hourly_precip.append(0.0)
                    hourly_weather_code.append(2)
                    
            data["hourly"] = {
                "time": hourly_time,
                "precipitation_probability": hourly_precip_prob,
                "precipitation": hourly_precip,
                "weather_code": hourly_weather_code,
                "temperature_2m": hourly_temp
            }
            
        if "daily" in params:
            days = int(params.get("forecast_days", 7))
            daily_time = []
            daily_sunrise = []
            daily_sunset = []
            daily_precip_sum = []
            daily_precip_hours = []
            daily_weather_code = []
            daily_tmax = []
            daily_tmin = []
            daily_uv = []
            
            for i in range(days):
                d = today + timedelta(days=i)
                date_str = d.strftime("%Y-%m-%d")
                daily_time.append(date_str)
                daily_sunrise.append(f"{date_str}T05:30")
                daily_sunset.append(f"{date_str}T18:15")
                daily_precip_sum.append(7.5)
                daily_precip_hours.append(3.0)
                daily_weather_code.append(61)
                daily_tmax.append(33.0)
                daily_tmin.append(24.0)
                daily_uv.append(9.0)
                
            data["daily"] = {
                "time": daily_time,
                "sunrise": daily_sunrise,
                "sunset": daily_sunset,
                "precipitation_sum": daily_precip_sum,
                "precipitation_hours": daily_precip_hours,
                "weather_code": daily_weather_code,
                "temperature_2m_max": daily_tmax,
                "temperature_2m_min": daily_tmin,
                "uv_index_max": daily_uv
            }
            
        return data
    # --- END MOCK ---

    r_client = await get_redis_client()

    # Create a stable cache key
    sorted_params = dict(sorted(params.items()))
    cache_key = f"weather_cache:{url}:{json.dumps(sorted_params)}"
    
    cached = None
    if r_client:
        try:
            cached = await r_client.get(cache_key)
        except Exception as e:
            logger.warning(f"Failed to get cache key from Redis: {e}")

    if cached:
        logger.info(f"Cache HIT for {cache_key}")
        return json.loads(cached)
        
    logger.info(f"Cache MISS for {cache_key}. Fetching...")
    stale_cache_key = f"{cache_key}:stale"   # Long-lived backup copy
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            headers = {"User-Agent": "GeoWeather/1.0 (contact: phutc04@gmail.com)"}
            r = await client.get(url, params=params, headers=headers)
            
            # Handle rate-limit separately: serve stale cache instead of mock
            if r.status_code == 429:
                logger.warning(f"Open-Meteo 429 (rate limited). Attempting stale cache fallback.")
                if r_client:
                    try:
                        stale = await r_client.get(stale_cache_key)
                        if stale:
                            logger.info("Serving stale cache (rate-limit fallback).")
                            data = json.loads(stale)
                            data["_stale"] = True
                            return data
                    except Exception:
                        pass
                # No stale cache — fall through to mock
                raise Exception(f"HTTP 429: {r.text[:200]}")
            
            r.raise_for_status()
            data = r.json()
            
            if r_client:
                try:
                    # Primary cache (normal TTL)
                    await r_client.setex(cache_key, ttl_seconds, json.dumps(data))
                    # Stale backup: keep for 24 hours as 429 fallback
                    await r_client.setex(stale_cache_key, 86400, json.dumps(data))
                except Exception as e:
                    logger.warning(f"Failed to write cache key to Redis: {e}")
                    
            return data
    except Exception as fetch_err:
        logger.error(f"HTTP fetch failed for {url}: {fetch_err}. Returning fallback mock data.")
        if "open-meteo.com" in url:
            import math
            from datetime import datetime, timedelta
            import zoneinfo
            
            tz_str = params.get("timezone", "Asia/Bangkok")
            try:
                zone = zoneinfo.ZoneInfo(tz_str)
            except Exception:
                zone = zoneinfo.ZoneInfo("UTC")
                
            now = datetime.now(zone)
            today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # is_mock=True: frontend will show a "dữ liệu ước tính" notice
            data = {"is_mock": True}
            
            if "air-quality" in url:
                data["current"] = {
                    "us_aqi": 42,
                    "pm2_5": 12.5,
                    "pm10": 20.0,
                    "uv_index": 6.5,
                    "nitrogen_dioxide": 15.0,
                    "ozone": 30.0
                }
                return data
                
            if "current" in params:
                data["current"] = {
                    "temperature_2m": 30.5,
                    "apparent_temperature": 34.0,
                    "relative_humidity_2m": 65,
                    "wind_speed_10m": 12.5,
                    "wind_direction_10m": 180,
                    "precipitation": 0.0,
                    "weather_code": 2,
                    "cloud_cover": 45,
                    "pressure_msl": 1012,
                    "visibility": 10000
                }
                
            if "hourly" in params:
                days = int(params.get("forecast_days", 7))
                hourly_time = []
                hourly_precip_prob = []
                hourly_precip = []
                hourly_weather_code = []
                hourly_temp = []
                
                for i in range(24 * days):
                    t = today + timedelta(hours=i)
                    hourly_time.append(t.strftime("%Y-%m-%dT%H:00"))
                    temp = 28 + 5 * math.sin((i - 6) * math.pi / 12)
                    hourly_temp.append(round(temp, 1))
                    
                    if 14 <= t.hour <= 16:
                        hourly_precip_prob.append(60)
                        hourly_precip.append(2.5)
                        hourly_weather_code.append(61)
                    else:
                        hourly_precip_prob.append(10)
                        hourly_precip.append(0.0)
                        hourly_weather_code.append(2)
                        
                data["hourly"] = {
                    "time": hourly_time,
                    "precipitation_probability": hourly_precip_prob,
                    "precipitation": hourly_precip,
                    "weather_code": hourly_weather_code,
                    "temperature_2m": hourly_temp
                }
                
            if "daily" in params:
                days = int(params.get("forecast_days", 7))
                daily_time = []
                daily_sunrise = []
                daily_sunset = []
                daily_precip_sum = []
                daily_precip_hours = []
                daily_weather_code = []
                daily_tmax = []
                daily_tmin = []
                daily_uv = []
                
                for i in range(days):
                    d = today + timedelta(days=i)
                    date_str = d.strftime("%Y-%m-%d")
                    daily_time.append(date_str)
                    daily_sunrise.append(f"{date_str}T05:30")
                    daily_sunset.append(f"{date_str}T18:15")
                    daily_precip_sum.append(7.5)
                    daily_precip_hours.append(3.0)
                    daily_weather_code.append(61)
                    daily_tmax.append(33.0)
                    daily_tmin.append(24.0)
                    daily_uv.append(9.0)
                    
                data["daily"] = {
                    "time": daily_time,
                    "sunrise": daily_sunrise,
                    "sunset": daily_sunset,
                    "precipitation_sum": daily_precip_sum,
                    "precipitation_hours": daily_precip_hours,
                    "weather_code": daily_weather_code,
                    "temperature_2m_max": daily_tmax,
                    "temperature_2m_min": daily_tmin,
                    "uv_index_max": daily_uv
                }
                
            return data
        raise fetch_err


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
            "description": "Returns current weather parameters for the nearest city to specified lat/lon coordinates. If the user asked for a specific city name (e.g., 'Hồ Chí Minh') but you decided to use coordinates to search, you MUST pass that name into 'location_name'.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "lat": {"type": "number", "description": "Latitude coordinate"},
                    "lon": {"type": "number", "description": "Longitude coordinate"},
                    "location_name": {
                        "type": "string", 
                        "description": "The name of the location the user asked for (e.g., 'Hồ Chí Minh', 'Hà Nội'). If the user only provided raw coordinates without a name, you MUST pass an empty string ''."
                    }
                },
                "required": ["lat", "lon", "location_name"]
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
                "Returns a 7-day hourly rain and temperature forecast. "
                "Provide city_name OR lat and lon."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "city_name": {"type": "string"},
                    "lat": {"type": "number"},
                    "lon": {"type": "number"},
                    "target_date": {"type": "string"}
                }
            }
        },
        {
            "name": "get_daily_forecast",
            "description": "Returns a 7-day daily forecast summary. Provide city_name OR lat and lon.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "city_name": {"type": "string"},
                    "lat": {"type": "number"},
                    "lon": {"type": "number"}
                }
            }
        },
        {
            "name": "get_air_quality_and_uv",
            "description": "Returns AQI, PM2.5, and UV index. Provide city_name OR lat and lon.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "city_name": {"type": "string"},
                    "lat": {"type": "number"},
                    "lon": {"type": "number"}
                }
            }
        },
        {
            "name": "get_sun_times",
            "description": "Returns sunrise and sunset times. Provide city_name OR lat and lon.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "city_name": {"type": "string"},
                    "lat": {"type": "number"},
                    "lon": {"type": "number"},
                    "target_date": {"type": "string"}
                }
            }
        },
        {
            "name": "get_safe_route",
            "description": (
                "Finds the safest driving route between two locations avoiding heavy rain and bad weather. "
                "Use this when the user asks for directions, routing, or safe routes."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string", "description": "Starting location name (e.g., 'Dĩ An')."},
                    "destination": {"type": "string", "description": "Destination location name (e.g., 'Quận 1')."}
                },
                "required": ["origin", "destination"]
            }
        }
    ]


# ─── Shared helpers ───────────────────────────────────────────────────────────

async def _reverse_geocode(lat: float, lon: float) -> str:
    """Convert coordinates to a human-readable place name via Nominatim (OSM).
    Returns e.g. 'Phường Đông Hòa, Việt Nam' or falls back to 'Vị trí của bạn'.
    """
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {
        "lat": lat,
        "lon": lon,
        "format": "json",
        "accept-language": "vi",
        "zoom": 14,          # ward/suburb level
        "addressdetails": 1,
    }
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                url, params=params,
                headers={"User-Agent": "GeoWeather/1.0"}
            )
            if resp.status_code == 200:
                data = resp.json()
                addr = data.get("address", {})
                # Priority: suburb/quarter/village → district → city → state
                suburb  = (addr.get("suburb") or addr.get("quarter")
                           or addr.get("village") or addr.get("town"))
                country = addr.get("country", "")
                if suburb:
                    return f"{suburb}, {country}"
                city = (addr.get("city") or addr.get("county")
                        or addr.get("state") or "")
                if city:
                    return f"{city}, {country}"
                return data.get("display_name", "Vị trí của bạn")
    except Exception as e:
        logger.warning(f"Reverse geocoding failed for ({lat},{lon}): {e}")
    return "Vị trí của bạn"


async def _resolve_city(city_name: str, db: AsyncSession) -> Optional[Dict[str, Any]]:
    """Look up a city's coordinates and metadata from the PostGIS DB."""
    import unicodedata
    
    def remove_diacritics(text_val: str) -> str:
        normalized = unicodedata.normalize('NFKD', text_val)
        cleaned = "".join([c for c in normalized if not unicodedata.combining(c)])
        return cleaned.replace('Đ', 'D').replace('đ', 'd')

    normalized_name = remove_diacritics(city_name).strip().lower()
    
    # Map common aliases
    if normalized_name in ["sai gon", "sg", "hcm", "hcmc", "ho chi minh"]:
        city_name = "Ho Chi Minh"
    elif normalized_name in ["hn", "ha noi"]:
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
    # TTL = 6 hours: forecast changes slowly, caching aggressively reduces API calls
    return await _fetch_with_cache(url, params, ttl_seconds=21600)


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


# ─── Hourly Forecast ────────────────────────────────────────────────────────────
async def get_hourly_forecast(city_name: str, target_time: str, db: AsyncSession) -> Dict[str, Any]:
    """
    Get the weather forecast for a specific hour of the current day.
    target_time format: "HH:00" (e.g., "14:00")
    """
    city = await _resolve_city(city_name, db)
    if not city:
        return {"error": f"City '{city_name}' not found."}
        
    data = await _fetch_open_meteo_forecast(city["lat"], city["lon"])
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    
    if not times:
        return {"error": "No hourly data available from Open-Meteo."}
        
    import zoneinfo
    from datetime import datetime
    tz = zoneinfo.ZoneInfo("Asia/Bangkok")
    today_str = datetime.now(tz).strftime("%Y-%m-%d")
    target_dt = f"{today_str}T{target_time}"
    
    try:
        idx = times.index(target_dt)
        return {
            "city_name": city["city_name"],
            "time": target_dt,
            "temperature": hourly["temperature_2m"][idx],
            "precipitation": hourly["precipitation"][idx],
            "precip_prob_pct": hourly["precipitation_probability"][idx],
            "condition": _wmo_desc(hourly["weather_code"][idx])
        }
    except ValueError:
        return {"error": "Không tìm thấy dữ liệu dự báo cho khung giờ này."}

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
            SELECT wc.*, c.city_name, c.country_code,
                   ST_Y(c.geom) AS lat, ST_X(c.geom) AS lon
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
                SELECT geoname_id, city_name, country_code, ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lon
                FROM cities
                ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
                LIMIT 1
            )
            SELECT nc.*, wc.temperature, wc.feels_like, wc.humidity,
                   wc.wind_speed, wc.weather_code, wc.precipitation,
                   wc.pressure, wc.visibility, wc.uv_index, wc.cloud_cover
            FROM nearest_city nc
            LEFT JOIN weather_current wc ON wc.location_id = nc.geoname_id;
        """)
        result = await db.execute(query, {"lat": lat, "lon": lon})
        row = result.mappings().first()
        if not row:
            return {"error": "No near weather station found."}

        row_dict = dict(row)

        location_name = arguments.get("location_name")
        if location_name:
            # If the LLM passed the original search name, use it
            place_name = location_name
        else:
            # Otherwise, reverse-geocode the user's exact coordinates → suburb/ward level name
            place_name = await _reverse_geocode(lat, lon)
        row_dict["place_name"] = place_name

        if row_dict.get("temperature") is None:
            # Fallback live fetch
            try:
                url = "https://api.open-meteo.com/v1/forecast"
                params = {
                    "latitude": row_dict["lat"],
                    "longitude": row_dict["lon"],
                    "current": (
                        "temperature_2m,relative_humidity_2m,apparent_temperature,"
                        "precipitation,weather_code,wind_speed_10m,wind_direction_10m,"
                        "surface_pressure,visibility,uv_index,cloud_cover"
                    ),
                    "timezone": "Asia/Bangkok",
                    "forecast_days": 1,
                }
                data = await _fetch_with_cache(url, params)
                cur = data.get("current", {})
                row_dict.update({
                    "temperature": cur.get("temperature_2m"),
                    "feels_like": cur.get("apparent_temperature"),
                    "humidity": cur.get("relative_humidity_2m"),
                    "wind_speed": cur.get("wind_speed_10m"),
                    "precipitation": cur.get("precipitation"),
                    "condition": _wmo_desc(cur.get("weather_code", 0)),
                    "pressure": cur.get("surface_pressure"),
                    "visibility": cur.get("visibility"),
                    "uv_index": cur.get("uv_index"),
                    "cloud_cover": cur.get("cloud_cover")
                })
            except Exception as e:
                logger.error(f"Failed live fetch in get_weather_by_coords: {e}")
        else:
            row_dict["condition"] = _wmo_desc(row_dict.get("weather_code", 0))

        return row_dict

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
        lat         = arguments.get("lat")
        lon         = arguments.get("lon")
        target_date = arguments.get("target_date")

        if lat is not None and lon is not None:
            timezone = "Asia/Bangkok"
        else:
            city = await _resolve_city(city_name, db)
            if not city:
                return {"error": f"City '{city_name}' not found."}
            lat = city["lat"]
            lon = city["lon"]
            timezone = city.get("timezone", "Asia/Bangkok")

        try:
            data = await _fetch_open_meteo_forecast(lat, lon, timezone)
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
            "city": city_name if city_name else f"{lat},{lon}",
            "lat": lat,
            "lon": lon,
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
        lat       = arguments.get("lat")
        lon       = arguments.get("lon")
        
        if lat is not None and lon is not None:
            timezone = "Asia/Bangkok"
        else:
            city = await _resolve_city(city_name, db)
            if not city:
                return {"error": f"City '{city_name}' not found."}
            lat = city["lat"]
            lon = city["lon"]
            timezone = city.get("timezone", "Asia/Bangkok")

        try:
            data = await _fetch_open_meteo_forecast(lat, lon, timezone)
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
            "city": city["city_name"] if 'city' in locals() and city else f"{lat},{lon}",
            "lat": lat,
            "lon": lon,
            "daily_forecast": daily,
        }

    # ── get_air_quality_and_uv ────────────────────────────────────────────────
    # ── get_air_quality_and_uv ────────────────────────────────────────────────
    elif name == "get_air_quality_and_uv":
        city_name = arguments.get("city_name")
        lat       = arguments.get("lat")
        lon       = arguments.get("lon")

        if lat is not None and lon is not None:
            timezone = "Asia/Bangkok"
        else:
            city = await _resolve_city(city_name, db)
            if not city:
                return {"error": f"City '{city_name}' not found."}
            lat = city["lat"]
            lon = city["lon"]
            timezone = city.get("timezone", "Asia/Bangkok")

        try:
            url = "https://air-quality-api.open-meteo.com/v1/air-quality"
            params = {
                "latitude": lat,
                "longitude": lon,
                "current": "european_aqi,us_aqi,pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone,uv_index",
                "timezone": timezone
            }
            data = await _fetch_with_cache(url, params)

            cur = data.get("current", {})
            return {
                "city": city["city_name"] if 'city' in locals() and city else f"{lat},{lon}",
                "lat": lat,
                "lon": lon,
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

    # ── get_sun_times ─────────────────────────────────────────────────────────
    elif name == "get_sun_times":
        city_name   = arguments.get("city_name")
        lat         = arguments.get("lat")
        lon         = arguments.get("lon")
        target_date = arguments.get("target_date")

        if lat is not None and lon is not None:
            timezone = "Asia/Bangkok"
        else:
            city = await _resolve_city(city_name, db)
            if not city:
                return {"error": f"City '{city_name}' not found."}
            lat = city["lat"]
            lon = city["lon"]
            timezone = city.get("timezone", "Asia/Bangkok")

        try:
            data = await _fetch_open_meteo_forecast(lat, lon, timezone)
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
            "city": city["city_name"] if 'city' in locals() and city else f"{lat},{lon}",
            "lat": lat,
            "lon": lon,
            "timezone": city.get("timezone", "Asia/Bangkok") if 'city' in locals() and city else "Asia/Bangkok",
            "sun_schedule": sun_schedule,
        }

    # ── get_hourly_forecast ───────────────────────────────────────────────────
    elif name == "get_hourly_forecast":
        city_name = arguments.get("city_name")
        target_time = arguments.get("target_time")
        return await get_hourly_forecast(city_name, target_time, db)

    # ── get_safe_route ────────────────────────────────────────────────────────
    elif name == "get_safe_route":
        origin = arguments.get("origin")
        dest = arguments.get("destination")
        
        async def geocode_loc(loc_name: str):
            url = "https://nominatim.openstreetmap.org/search"
            # Try with Ho Chi Minh suffix first for better local results
            params = {"q": f"{loc_name}, Ho Chi Minh", "format": "json", "limit": 1}
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, params=params, headers={"User-Agent": "GeoWeather/1.0"})
                if resp.status_code == 200 and resp.json():
                    return float(resp.json()[0]["lat"]), float(resp.json()[0]["lon"])
            # Fallback to exact search
            params = {"q": loc_name, "format": "json", "limit": 1}
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, params=params, headers={"User-Agent": "GeoWeather/1.0"})
                if resp.status_code == 200 and resp.json():
                    return float(resp.json()[0]["lat"]), float(resp.json()[0]["lon"])
            return None
            
        ocoords = await geocode_loc(origin)
        dcoords = await geocode_loc(dest)
        
        if not ocoords or not dcoords:
            return {"error": f"Không thể lấy tọa độ cho {origin} hoặc {dest}"}
            
        olat, olon = ocoords
        dlat, dlon = dcoords
        
        from apps.api.routers.routing import safe_route
        try:
            route_resp = await safe_route(olat, olon, dlat, dlon, db)
            best_route = route_resp["best_route"]
            return {
                "origin": origin,
                "destination": dest,
                "origin_coords": ocoords,
                "dest_coords": dcoords,
                "duration_minutes": round(best_route["duration_normal"] / 60),
                "distance_km": round(best_route["distance"] / 1000, 1),
                "max_precipitation_mm": best_route["max_precip"],
                "weather_penalty_minutes": round(best_route["penalty"] / 60),
                "route_command_tag": f"[ROUTE:{olat},{olon},{dlat},{dlon}]"
            }
        except Exception as e:
            return {"error": str(e)}

    return {"error": f"Unknown tool: {name}"}
