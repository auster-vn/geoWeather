import logging
import httpx
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from ..core.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

async def get_osrm_routes(olat: float, olon: float, dlat: float, dlon: float):
    # OSRM public API (lon, lat format)
    url = f"http://router.project-osrm.org/route/v1/driving/{olon},{olat};{dlon},{dlat}?alternatives=true&geometries=geojson&overview=full"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=10.0)
        if resp.status_code != 200:
            logger.error(f"OSRM returned {resp.status_code}: {resp.text}")
            raise HTTPException(status_code=500, detail="Failed to fetch routes from OSRM")
        data = resp.json()
        if data.get("code") != "Ok":
            raise HTTPException(status_code=400, detail="No route found")
        return data["routes"]

@router.get("/geocode")
async def geocode_address(address: str):
    """
    Geocode an address using Nominatim API.
    """
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": address,
        "format": "json",
        "limit": 1
    }
    headers = {
        "User-Agent": "GeoWeatherApp/1.0"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, params=params, headers=headers, timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                if data and len(data) > 0:
                    return {
                        "status": "success",
                        "lat": float(data[0]["lat"]),
                        "lon": float(data[0]["lon"]),
                        "display_name": data[0]["display_name"]
                    }
        except Exception as e:
            logger.error(f"Geocoding error for {address}: {e}")
            
    raise HTTPException(status_code=404, detail="Location not found")

@router.get("/safe-route")
async def safe_route(olat: float, olon: float, dlat: float, dlon: float, db: AsyncSession = Depends(get_db)):
    """
    Finds the safest route from Origin to Destination by querying OSRM for alternative routes,
    then applying a weather penalty based on precipitation along the route using PostGIS.
    """
    try:
        routes = await get_osrm_routes(olat, olon, dlat, dlon)
    except Exception as e:
        logger.error(f"Error fetching routes: {e}")
        raise HTTPException(status_code=500, detail="Routing service unavailable")
        
    best_route = None
    min_cost = float('inf')
    route_details = []
    
    query = text("""
        WITH route_geom AS (
            SELECT ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326) AS geom
        ),
        nearby_weather AS (
            SELECT 
                wc.precipitation
            FROM cities c
            JOIN weather_current wc ON c.geoname_id = wc.location_id
            JOIN route_geom rg ON ST_DWithin(c.geom::geography, rg.geom::geography, 3000) -- within 3km of the route
        )
        SELECT 
            COALESCE(MAX(precipitation), 0) as max_precip, 
            COALESCE(AVG(precipitation), 0) as avg_precip 
        FROM nearby_weather;
    """)

    for idx, route in enumerate(routes):
        geom_json = json.dumps(route["geometry"])
        try:
            result = await db.execute(query, {"geojson": geom_json})
            row = result.mappings().first()
            
            max_precip = float(row["max_precip"])
            avg_precip = float(row["avg_precip"])
            
            # Penalty logic: Heavy rain adds significant virtual time to the route
            # Let's say 1mm of avg rain adds 300 seconds (5 mins), and max rain adds 120 seconds (2 mins)
            penalty_seconds = (avg_precip * 300) + (max_precip * 120)
            
            # Extra penalty if max_precip > 10mm (Flooding risk)
            if max_precip > 10:
                penalty_seconds += 1800 # Add 30 minutes virtual penalty for high flood risk
                
            total_cost = route["duration"] + penalty_seconds
            
            route_details.append({
                "route_index": idx,
                "duration_normal": route["duration"],
                "distance": route["distance"],
                "penalty": penalty_seconds,
                "total_cost": total_cost,
                "max_precip": max_precip,
                "avg_precip": avg_precip,
                "geometry": route["geometry"]
            })
            
            if total_cost < min_cost:
                min_cost = total_cost
                best_route = route_details[-1]
                
        except Exception as e:
            logger.error(f"Error evaluating route {idx}: {e}")
            
    if not best_route:
        raise HTTPException(status_code=500, detail="Could not evaluate routes")
        
    return {
        "status": "success",
        "best_route": best_route,
        "alternatives": len(routes)
    }
