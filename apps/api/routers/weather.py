import logging
import time
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
@cache(expire=300)
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
        logger.error(f"Error fetching forecast: {e}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Failed to fetch forecast from Open-Meteo.")
