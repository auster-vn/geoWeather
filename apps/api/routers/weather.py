import logging
import time
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from shapely.geometry import LineString
from typing import List
from fastapi_cache.decorator import cache

from ..core.database import get_db, get_ts_db
from ..core.telemetry import spatial_query_duration
from ..schemas.weather import WeatherResponse, WeatherRegionStats, RouteWeatherPoint

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/nearest/{lat}/{lon}", response_model=WeatherResponse)
async def get_nearest_weather(lat: float, lon: float, db: AsyncSession = Depends(get_db)):
    """
    Find the nearest city and return its latest weather.
    Uses PostGIS KNN operator `<->` for sub-millisecond search.
    """
    start_time = time.time()
    
    query = text("""
        WITH nearest_city AS (
            SELECT
                c.geoname_id,
                c.city_name,
                c.country_code,
                c.h3_r4,
                c.h3_r7,
                ST_Y(c.geom) AS lat,
                ST_X(c.geom) AS lon,
                ST_Distance(
                    c.geom::geography,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                ) AS distance_meters
            FROM cities c
            ORDER BY c.geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
            LIMIT 1
        )
        SELECT
            nc.*,
            wc.temperature,
            wc.feels_like,
            wc.humidity,
            wc.wind_speed,
            wc.wind_direction,
            wc.precipitation,
            wc.weather_code,
            wc.updated_at AS observed_at
        FROM nearest_city nc
        LEFT JOIN weather_current wc ON wc.location_id = nc.geoname_id;
    """)
    
    try:
        result = await db.execute(query, {"lat": lat, "lon": lon})
        row = result.mappings().first()
        
        spatial_query_duration.labels(query_type="nearest_weather").observe(time.time() - start_time)
        
        if not row:
            raise HTTPException(status_code=404, detail="No nearby cities found.")
            
        data = dict(row)
        if not data.get("h3_r4"):
            import h3
            data["h3_r4"] = h3.latlng_to_cell(lat, lon, 4)
            data["h3_r7"] = h3.latlng_to_cell(lat, lon, 7)
            
        if data.get("temperature") is None:
            logger.info(f"Weather data not found in DB for city {data.get('city_name')}, fetching live fallback...")
            try:
                url = "https://api.open-meteo.com/v1/forecast"
                params = {
                    "latitude": data["lat"],
                    "longitude": data["lon"],
                    "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,wind_direction_10m,surface_pressure,visibility,uv_index,cloud_cover",
                    "timezone": "Asia/Bangkok",
                    "forecast_days": 1,
                }
                from ..tools.weather_tools import _fetch_with_cache
                resp = await _fetch_with_cache(url, params)
                cur = resp.get("current", {})
                
                observed_at_dt = datetime.now(timezone.utc)
                if "time" in cur:
                    try:
                        observed_at_dt = datetime.fromisoformat(cur["time"]).replace(tzinfo=timezone.utc)
                    except Exception:
                        pass
                
                data.update({
                    "temperature": cur.get("temperature_2m"),
                    "feels_like": cur.get("apparent_temperature"),
                    "humidity": cur.get("relative_humidity_2m"),
                    "wind_speed": cur.get("wind_speed_10m"),
                    "wind_direction": cur.get("wind_direction_10m"),
                    "precipitation": cur.get("precipitation"),
                    "weather_code": cur.get("weather_code"),
                    "observed_at": observed_at_dt
                })
                
                # Save/upsert to weather_current table in database to cache it
                try:
                    upsert_query = text("""
                        INSERT INTO weather_current (
                            location_id, temperature, feels_like, humidity, wind_speed, 
                            wind_direction, precipitation, weather_code, pressure, 
                            visibility, uv_index, cloud_cover, updated_at
                        ) VALUES (
                            :location_id, :temperature, :feels_like, :humidity, :wind_speed, 
                            :wind_direction, :precipitation, :weather_code, :pressure, 
                            :visibility, :uv_index, :cloud_cover, :updated_at
                        )
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
                    """)
                    
                    await db.execute(upsert_query, {
                        "location_id": data["geoname_id"],
                        "temperature": cur.get("temperature_2m"),
                        "feels_like": cur.get("apparent_temperature"),
                        "humidity": cur.get("relative_humidity_2m"),
                        "wind_speed": cur.get("wind_speed_10m"),
                        "wind_direction": cur.get("wind_direction_10m"),
                        "precipitation": cur.get("precipitation"),
                        "weather_code": cur.get("weather_code"),
                        "pressure": cur.get("surface_pressure"),
                        "visibility": cur.get("visibility"),
                        "uv_index": cur.get("uv_index"),
                        "cloud_cover": cur.get("cloud_cover"),
                        "updated_at": observed_at_dt
                    })
                    await db.commit()
                    logger.info(f"Successfully cached live weather for city_id {data['geoname_id']} to DB")
                except Exception as db_err:
                    logger.error(f"Failed to cache live weather to DB in fallback: {db_err}")
            except Exception as e:
                logger.error(f"Failed live fetch in /nearest/{lat}/{lon}: {e}")
            
        return data
    except Exception as e:
        logger.error(f"Error in get_nearest_weather: {e}")
        raise HTTPException(status_code=500, detail="Database query failed.")

@router.post("/route", response_model=List[RouteWeatherPoint])
async def get_route_weather(
    polyline: List[List[float]],  # [[lat, lon], [lat, lon], ...]
    interval_km: float = 50.0,
    db: AsyncSession = Depends(get_db)
):
    """
    Interpolates weather conditions along a route at regular distance intervals.
    Uses PostGIS ST_LineInterpolatePoint.
    """
    if len(polyline) < 2:
        raise HTTPException(status_code=400, detail="Route must have at least 2 points.")
        
    start_time = time.time()
    try:
        # shapely uses (lon, lat)
        line = LineString([(pt[1], pt[0]) for pt in polyline])
        
        # Determine number of sampling points
        # For simplicity in local dev, let's sample between 5 to 20 points
        n_points = max(3, min(25, int(line.length * 111 / interval_km))) # 1 degree lat ~ 111km
        
        query = text("""
            WITH route AS (
                SELECT ST_GeomFromText(:wkt, 4326) AS geom
            ),
            sample_points AS (
                SELECT 
                    idx,
                    ST_LineInterpolatePoint(route.geom, idx::float / :n_points) AS pt
                FROM route, generate_series(0, :n_points) AS idx
            )
            SELECT
                sp.idx,
                ST_Y(sp.pt) AS latitude,
                ST_X(sp.pt) AS longitude,
                wc.temperature,
                wc.weather_code,
                wc.wind_speed,
                wc.precipitation
            FROM sample_points sp
            CROSS JOIN LATERAL (
                SELECT wc.*
                FROM weather_current wc
                JOIN cities c ON c.geoname_id = wc.location_id
                ORDER BY c.geom <-> sp.pt
                LIMIT 1
            ) wc
            ORDER BY sp.idx;
        """)
        
        result = await db.execute(query, {
            "wkt": line.wkt,
            "n_points": n_points
        })
        
        spatial_query_duration.labels(query_type="route_weather").observe(time.time() - start_time)
        return [dict(r) for r in result.mappings().all()]
    except Exception as e:
        logger.error(f"Error in route weather calculation: {e}")
        raise HTTPException(status_code=500, detail="Route spatial processing failed.")

@router.get("/region/{h3_index}", response_model=List[WeatherRegionStats])
async def get_region_weather_stats(h3_index: str, ts_db: AsyncSession = Depends(get_ts_db)):
    """
    Retrieves historical weather aggregates for the specified H3 cell from TimescaleDB
    for the last 24 hours.
    """
    query = text("""
        SELECT 
            h3_index_r4,
            window_start,
            window_end,
            avg_temperature,
            max_wind_speed,
            total_precip,
            avg_humidity,
            observation_count
        FROM weather_hourly_agg
        WHERE h3_index_r4 = :h3_index
          AND window_start >= NOW() - INTERVAL '24 hours'
        ORDER BY window_start ASC;
    """)
    
    try:
        result = await ts_db.execute(query, {"h3_index": h3_index})
        rows = result.mappings().all()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Error in get_region_weather_stats: {e}")
        raise HTTPException(status_code=500, detail="TimescaleDB query failed.")

@router.get("/all")
@cache(expire=15)
async def get_all_weather(db: AsyncSession = Depends(get_db)):
    """
    Returns current weather parameters for all cities.
    Used for GIS overlays (Scatterplot, Heatmap, Hexagon).
    """
    query = text("""
        SELECT 
            c.geoname_id,
            c.city_name,
            c.country_code,
            ST_Y(c.geom) AS latitude,
            ST_X(c.geom) AS longitude,
            c.h3_r4,
            c.h3_r7,
            wc.temperature,
            wc.wind_speed,
            wc.precipitation,
            wc.humidity,
            wc.weather_code
        FROM cities c
        JOIN weather_current wc ON wc.location_id = c.geoname_id;
    """)
    try:
        result = await db.execute(query)
        rows = result.mappings().all()
        
        # Calculate h3 indexes if missing
        import h3
        processed_rows = []
        for r in rows:
            data = dict(r)
            if not data.get("h3_r4"):
                data["h3_r4"] = h3.latlng_to_cell(data["latitude"], data["longitude"], 4)
                data["h3_r7"] = h3.latlng_to_cell(data["latitude"], data["longitude"], 7)
            processed_rows.append(data)
            
        return processed_rows
    except Exception as e:
        logger.error(f"Error in get_all_weather: {e}")
        raise HTTPException(status_code=500, detail="Database query failed.")

sync_lock = asyncio.Lock()

@router.post("/sync")
async def trigger_sync(background_tasks: BackgroundTasks):
    """
    Trigger the weather data ingestion cycle in the background.
    Uses a lock to prevent concurrent ingestion runs.
    """
    if sync_lock.locked():
        raise HTTPException(status_code=409, detail="Sync is already in progress.")
        
    async def run_sync():
        async with sync_lock:
            try:
                logger.info("Starting background sync ingestion...")
                from services.ingestion.producer import run_once
                await run_once()
                logger.info("Background sync ingestion completed successfully.")
            except Exception as e:
                logger.error(f"Error during background sync ingestion: {e}")
                
    background_tasks.add_task(run_sync)
    return {"status": "success", "message": "Sync started in background."}

@router.get("/sync/status")
async def get_sync_status():
    """
    Check if a sync ingestion task is currently running.
    """
    return {"is_syncing": sync_lock.locked()}

@router.get("/forecast/{lat}/{lon}")
@cache(expire=900)
async def get_forecast(lat: float, lon: float):
    """
    Fetch 7-day detailed forecast from Open-Meteo for the dashboard.
    """
    from ..tools.weather_tools import _fetch_open_meteo_forecast
    try:
        data = await _fetch_open_meteo_forecast(lat, lon, tz="Asia/Bangkok")
        return data
    except Exception as e:
        logger.exception("Error fetching forecast")
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Open-Meteo API is currently unavailable (502 Bad Gateway). Please try again later.")
