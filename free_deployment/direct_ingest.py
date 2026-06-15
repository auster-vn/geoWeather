import os
import asyncio
import uuid
import logging
from datetime import datetime, timezone, timedelta
import h3
import httpx
import asyncpg
import numpy as np
import json
import redis.asyncio as aioredis

logger = logging.getLogger("direct_ingest")

db_semaphore = asyncio.Semaphore(10)

# Read configurations from environment variables
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:geoweather_local@localhost:5432/geoweather")
TIMESCALE_URL = os.environ.get("TIMESCALE_URL", os.environ.get("DATABASE_URL"))  # Default to DATABASE_URL if separate Timescale DB is not used
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

OPEN_METEO_BATCH_URL = "https://api.open-meteo.com/v1/forecast"
WEATHER_VARIABLES = [
    "temperature_2m",
    "apparent_temperature",
    "relative_humidity_2m",
    "wind_speed_10m",
    "wind_direction_10m",
    "precipitation",
    "weather_code",
    "surface_pressure",
    "visibility",
    "uv_index",
    "cloud_cover",
]

# Helper function to convert DB URL for asyncpg
def get_asyncpg_dsn(url: str) -> str:
    if "postgresql+asyncpg://" in url:
        return url.replace("postgresql+asyncpg://", "postgresql://")
    return url

async def fetch_batch_weather(locations: list, client: httpx.AsyncClient) -> list:
    """Fetch current weather for up to 100 coordinates from Open-Meteo."""
    if not locations:
        return []
    
    latitudes = [str(loc["lat"]) for loc in locations]
    longitudes = [str(loc["lon"]) for loc in locations]
    
    params = {
        "latitude": ",".join(latitudes),
        "longitude": ",".join(longitudes),
        "current": ",".join(WEATHER_VARIABLES),
        "wind_speed_unit": "ms",
        "timezone": "auto",
    }
    
    try:
        response = await client.get(OPEN_METEO_BATCH_URL, params=params, timeout=20.0)
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else [data]
    except Exception as e:
        logger.error(f"Failed to fetch batch weather from Open-Meteo: {e}")
        return []

def validate_observation(temp, humidity, wind_speed, precipitation, lat, lon) -> bool:
    """Data quality validation similar to stream processor."""
    try:
        if not (-60 <= temp <= 60):
            return False
        if not (0 <= humidity <= 100):
            return False
        if not (0 <= wind_speed <= 300):
            return False
        if precipitation < 0:
            return False
        if not (-90 <= lat <= 90):
            return False
        if not (-180 <= lon <= 180):
            return False
        return True
    except Exception:
        return False

async def detect_anomaly(conn_ts: asyncpg.Connection, location_id: int, temp: float) -> tuple:
    """Stateless Z-score temperature anomaly detection using database history."""
    try:
        # Fetch the last 19 observations for this city to form a 20-sample window with the current one
        rows = await conn_ts.fetch("""
            SELECT temperature FROM weather_observations 
            WHERE location_id = $1 
            ORDER BY observed_at DESC 
            LIMIT 19;
        """, location_id)
        
        hist = [r["temperature"] for r in rows if r["temperature"] is not None]
        if len(hist) < 5:
            return False, 0.0, 0.0, 0.0
            
        mean = float(np.mean(hist))
        std = float(np.std(hist))
        zscore = abs(temp - mean) / std if std > 0 else 0.0
        is_anomaly = std > 0.1 and zscore > 3.0
        
        return is_anomaly, mean, std, zscore
    except Exception as e:
        logger.warning(f"Error checking anomaly for location {location_id}: {e}")
        return False, 0.0, 0.0, 0.0

async def _process_location_weather_with_conns(
    city: dict, 
    weather_data: dict, 
    conn_pg: asyncpg.Connection, 
    conn_ts: asyncpg.Connection, 
    redis_client: aioredis.Redis
):
    """Process a single location's weather, update the DBs, and publish updates."""
    current = weather_data.get("current", {})
    if not current:
        return
        
    temp = current.get("temperature_2m")
    humidity = current.get("relative_humidity_2m")
    wind_speed = current.get("wind_speed_10m")
    precipitation = current.get("precipitation")
    lat = float(city["lat"])
    lon = float(city["lon"])
    loc_id = int(city["geoname_id"])
    
    if temp is None or humidity is None or wind_speed is None or precipitation is None:
        logger.warning(f"Skipping empty observation for city: {city['city_name']}")
        return
        
    # 1. Data quality check
    if not validate_observation(temp, humidity, wind_speed, precipitation, lat, lon):
        logger.warning(f"Data Quality validation failed for city {city['city_name']}. Skipping anomalous record.")
        return
        
    # Parse observation time
    observed_at_dt = datetime.now(timezone.utc)
    if "time" in current:
        try:
            observed_at_dt = datetime.fromisoformat(current["time"]).replace(tzinfo=timezone.utc)
        except Exception:
            pass
            
    # 2. Compute H3 indexes
    h3_r4 = h3.latlng_to_cell(lat, lon, 4)
    h3_r7 = h3.latlng_to_cell(lat, lon, 7)
    
    # 3. Anomaly detection (Z-score)
    is_anomaly, mean, std, zscore = await detect_anomaly(conn_ts, loc_id, temp)
    if is_anomaly:
        alert = {
            "alert_id": str(uuid.uuid4()),
            "location_id": loc_id,
            "city_name": city["city_name"],
            "temperature": temp,
            "expected_mean": mean,
            "expected_std": std,
            "zscore": zscore,
            "observed_at": observed_at_dt.isoformat()
        }
        logger.warning(f"⚠️ ANOMALY DETECTED for {city['city_name']}: {temp}°C (expected mean: {mean:.1f}°C, z-score: {zscore:.1f})")
        # Publish alert to Redis Pub/Sub channel
        await redis_client.publish("weather:alerts", json.dumps(alert))
        
    # 4. Upsert weather_current (Postgres cache)
    await conn_pg.execute("""
        INSERT INTO weather_current (
            location_id, temperature, feels_like, humidity, wind_speed, 
            wind_direction, precipitation, weather_code, pressure, 
            visibility, uv_index, cloud_cover, updated_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        ON CONFLICT (location_id) DO UPDATE SET
            temperature = EXCLUDED.temperature,
            feels_like = EXCLUDED.feels_like,
            humidity = EXCLUDED.humidity,
            wind_speed = EXCLUDED.wind_speed,
            wind_direction = EXCLUDED.wind_direction,
            precipitation = EXCLUDED.precipitation,
            weather_code = EXCLUDED.weather_code,
            pressure = EXCLUDED.pressure,
            visibility = EXCLUDED.visibility,
            uv_index = EXCLUDED.uv_index,
            cloud_cover = EXCLUDED.cloud_cover,
            updated_at = EXCLUDED.updated_at;
    """, 
        loc_id, temp, current.get("apparent_temperature"), humidity, wind_speed,
        current.get("wind_direction_10m"), precipitation, current.get("weather_code"), current.get("surface_pressure"),
        current.get("visibility"), current.get("uv_index"), current.get("cloud_cover"), observed_at_dt
    )
    
    # 5. Insert raw observation to TimescaleDB/Postgres historical table
    await conn_ts.execute("""
        INSERT INTO weather_observations (
            observation_id, location_id, h3_index_r4, h3_index_r7, temperature, feels_like, humidity, 
            wind_speed, wind_direction, precipitation, weather_code, 
            pressure, visibility, uv_index, cloud_cover, observed_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
        ON CONFLICT (location_id, observed_at) DO NOTHING;
    """,
        uuid.uuid4(), loc_id, h3_r4, h3_r7, temp, current.get("apparent_temperature"), humidity,
        wind_speed, current.get("wind_direction_10m"), precipitation, current.get("weather_code"),
        current.get("surface_pressure"), current.get("visibility"), current.get("uv_index"), current.get("cloud_cover"), observed_at_dt
    )
    
    # 6. Tumbling hourly window aggregation per H3 resolution 4 cell
    window_start = datetime.utcnow().replace(minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
    window_end = window_start + timedelta(hours=1)
    
    agg = await conn_ts.fetchrow("""
        SELECT 
            AVG(temperature) as avg_temp,
            MAX(wind_speed) as max_wind,
            SUM(precipitation) as total_precip,
            AVG(CAST(humidity AS FLOAT)) as avg_hum,
            COUNT(*) as obs_count
        FROM weather_observations
        WHERE h3_index_r4 = $1
          AND observed_at >= $2;
    """, h3_r4, window_start)
    
    if agg and agg["avg_temp"] is not None:
        await conn_ts.execute("""
            INSERT INTO weather_hourly_agg (
                h3_index_r4, window_start, window_end, avg_temperature, 
                max_wind_speed, total_precip, avg_humidity, observation_count
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (h3_index_r4, window_start) DO UPDATE SET
                avg_temperature = EXCLUDED.avg_temperature,
                max_wind_speed = EXCLUDED.max_wind_speed,
                total_precip = EXCLUDED.total_precip,
                avg_humidity = EXCLUDED.avg_humidity,
                observation_count = EXCLUDED.observation_count;
        """,
            h3_r4, window_start, window_end,
            float(agg["avg_temp"]), float(agg["max_wind"] or 0.0), float(agg["total_precip"] or 0.0),
            float(agg["avg_hum"]), int(agg["obs_count"])
        )
        
        # 7. Publish to Redis Pub/Sub for WebSockets UI update
        redis_msg = {
            "h3_index_r4": h3_r4,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "avg_temperature": round(float(agg["avg_temp"]), 1),
            "max_wind_speed": round(float(agg["max_wind"] or 0.0), 1),
            "total_precip": round(float(agg["total_precip"] or 0.0), 1),
            "avg_humidity": round(float(agg["avg_hum"]), 1),
            "observation_count": int(agg["obs_count"])
        }
        await redis_client.publish(f"weather:h3:{h3_r4}", json.dumps(redis_msg))

async def process_location_weather(
    city: dict,
    weather_data: dict,
    pool_pg: asyncpg.Pool,
    pool_ts: asyncpg.Pool,
    redis_client: aioredis.Redis
):
    """Acquires connections from the pools and processes the weather data."""
    async with db_semaphore:
        async with pool_pg.acquire() as conn_pg:
            if pool_ts != pool_pg:
                async with pool_ts.acquire() as conn_ts:
                    await _process_location_weather_with_conns(
                        city, weather_data, conn_pg, conn_ts, redis_client
                    )
            else:
                await _process_location_weather_with_conns(
                    city, weather_data, conn_pg, conn_pg, redis_client
                )

async def run_ingestion():
    """Main function to run the batch ingestion cycle."""
    logger.info("Initializing direct database and cache connections...")
    pg_dsn = get_asyncpg_dsn(DATABASE_URL)
    ts_dsn = get_asyncpg_dsn(TIMESCALE_URL)
    
    # Use create_pool instead of connect to support concurrent queries
    # Reduce pool size to avoid Supabase connection limits (15 max)
    pool_pg = await asyncpg.create_pool(pg_dsn, min_size=1, max_size=4, statement_cache_size=0)
    pool_ts = await asyncpg.create_pool(ts_dsn, min_size=1, max_size=4, statement_cache_size=0) if TIMESCALE_URL != DATABASE_URL else pool_pg
    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    
    try:
        # Load active cities from DB (population > 100k to restrict API limits)
        logger.info("Loading cities list from PostgreSQL...")
        async with pool_pg.acquire() as conn:
            rows = await conn.fetch("""
                SELECT geoname_id, city_name, country_code, ST_Y(geom) as lat, ST_X(geom) as lon 
                FROM cities 
                WHERE population > 100000 OR country_code = 'VN'
                ORDER BY CASE WHEN country_code = 'VN' THEN 1 ELSE 2 END, population DESC;
            """)
        
        cities = [dict(r) for r in rows]
        logger.info(f"Loaded {len(cities)} cities to poll.")
        if not cities:
            logger.warning("No cities found in database. Please run migrations and seed data.")
            return
            
        # Group cities into batches of 100
        batch_size = 100
        batches = [cities[i:i + batch_size] for i in range(0, len(cities), batch_size)]
        
        logger.info(f"Processing weather updates in {len(batches)} batches...")
        async with httpx.AsyncClient() as http_client:
            for idx, batch in enumerate(batches):
                logger.info(f"Polling batch {idx+1}/{len(batches)} containing {len(batch)} cities...")
                results = await fetch_batch_weather(batch, http_client)
                
                # Update database for all cities in this batch concurrently using the connection pools
                tasks = []
                for city_info, weather_info in zip(batch, results):
                    tasks.append(
                        process_location_weather(
                            city_info, weather_info, pool_pg, pool_ts, redis_client
                        )
                    )
                await asyncio.gather(*tasks)
                # Sleep briefly between batches to prevent hitting Open-Meteo 429 Rate Limits
                await asyncio.sleep(0.5)
                
        logger.info("Direct weather sync cycle completed successfully.")
        
    except Exception as e:
        logger.error(f"Error during direct weather ingestion: {e}", exc_info=True)
    finally:
        await pool_pg.close()
        if TIMESCALE_URL != DATABASE_URL:
            await pool_ts.close()
        await redis_client.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    asyncio.run(run_ingestion())
