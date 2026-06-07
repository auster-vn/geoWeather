import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List
from ..core.database import get_db
from ..schemas.weather import CitySearchResponse

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/search", response_model=List[CitySearchResponse])
async def search_cities(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """
    Search cities by name (case-insensitive prefix search).
    """
    query = text("""
        SELECT 
            geoname_id,
            city_name,
            country_code,
            population,
            timezone,
            ST_Y(geom) as latitude,
            ST_X(geom) as longitude
        FROM cities
        WHERE ascii_name ILIKE :q OR city_name ILIKE :q
        ORDER BY population DESC
        LIMIT :limit;
    """)
    
    try:
        result = await db.execute(query, {"q": f"{q}%", "limit": limit})
        rows = result.mappings().all()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Error searching cities: {e}")
        raise HTTPException(status_code=500, detail="Database search failed.")

@router.get("/{geoname_id}", response_model=CitySearchResponse)
async def get_city(geoname_id: int, db: AsyncSession = Depends(get_db)):
    """
    Retrieve details for a single city.
    """
    query = text("""
        SELECT 
            geoname_id,
            city_name,
            country_code,
            population,
            timezone,
            ST_Y(geom) as latitude,
            ST_X(geom) as longitude
        FROM cities
        WHERE geoname_id = :geoname_id;
    """)
    
    try:
        result = await db.execute(query, {"geoname_id": geoname_id})
        row = result.mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="City not found.")
        return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching city: {e}")
        raise HTTPException(status_code=500, detail="Database query failed.")
