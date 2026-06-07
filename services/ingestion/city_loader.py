import os
import zipfile
import io
import httpx
import logging
import h3
from typing import List, Dict, Any, Generator
import asyncpg

logger = logging.getLogger(__name__)

GEONAMES_URL = "https://download.geonames.org/export/dump/cities15000.zip"
DB_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:geoweather_local@localhost:5432/geoweather")

# Helper function to convert DB URL for asyncpg if needed
def get_asyncpg_dsn(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://")
    return url

async def download_and_parse_cities() -> List[tuple]:
    logger.info(f"Downloading GeoNames from {GEONAMES_URL}...")
    async with httpx.AsyncClient() as client:
        response = await client.get(GEONAMES_URL, timeout=60.0)
        response.raise_for_status()
        
    logger.info("Unzipping and parsing GeoNames...")
    zip_file = zipfile.ZipFile(io.BytesIO(response.content))
    txt_filename = [name for name in zip_file.namelist() if name.endswith('.txt')][0]
    
    cities = []
    with zip_file.open(txt_filename) as f:
        for line in io.TextIOWrapper(f, encoding='utf-8'):
            parts = line.strip().split('\t')
            if len(parts) < 19:
                continue
                
            try:
                geoname_id = int(parts[0])
                city_name = parts[1]
                ascii_name = parts[2]
                lat = float(parts[4])
                lon = float(parts[5])
                country_code = parts[8]
                admin1_code = parts[10]
                admin2_code = parts[11]
                population = int(parts[14]) if parts[14] else 0
                timezone = parts[17]
                
                # Calculate H3 indexes programmatically in Python
                h3_r4 = h3.latlng_to_cell(lat, lon, 4)
                h3_r7 = h3.latlng_to_cell(lat, lon, 7)
                
                # WKT geometry for PostGIS ST_GeomFromText
                geom_wkt = f"SRID=4326;POINT({lon} {lat})"
                
                cities.append((
                    geoname_id,
                    city_name,
                    ascii_name,
                    country_code,
                    admin1_code,
                    admin2_code,
                    population,
                    timezone,
                    geom_wkt,
                    h3_r4,
                    h3_r7
                ))
            except Exception as e:
                # Skip invalid lines
                continue
                
    logger.info(f"Parsed {len(cities)} cities successfully.")
    return cities

async def seed_cities():
    cities = await download_and_parse_cities()
    if not cities:
        logger.error("No cities parsed, aborting seed.")
        return

    dsn = get_asyncpg_dsn(DB_URL)
    conn = await asyncpg.connect(dsn)
    try:
        logger.info("Truncating cities table...")
        await conn.execute("TRUNCATE TABLE cities CASCADE;")
        
        logger.info("Inserting cities into database...")
        # We can use COPY or executemany. Executemany is highly optimized in asyncpg.
        # But we need ST_GeomFromText for WKT. To make it extremely simple and fast, we can first insert into
        # a temp table or use normal COPY for text fields and cast, or write custom SQL.
        # Let's insert via standard COPY by inserting geom as a geometry directly.
        # Actually, let's create a temporary table, copy to it, and then insert into cities casting the WKT.
        await conn.execute("""
            CREATE TEMP TABLE temp_cities (
                geoname_id INTEGER,
                city_name VARCHAR(200),
                ascii_name VARCHAR(200),
                country_code CHAR(2),
                admin1_code VARCHAR(20),
                admin2_code VARCHAR(80),
                population INTEGER,
                timezone VARCHAR(40),
                geom_wkt TEXT,
                h3_r4 VARCHAR(15),
                h3_r7 VARCHAR(15)
            );
        """)
        
        # COPY records
        await conn.copy_records_to_table('temp_cities', records=cities)
        
        # Insert into final table
        await conn.execute("""
            INSERT INTO cities (geoname_id, city_name, ascii_name, country_code, admin1_code, admin2_code, population, timezone, geom, h3_r4, h3_r7)
            SELECT geoname_id, city_name, ascii_name, country_code, admin1_code, admin2_code, population, timezone, ST_GeomFromText(geom_wkt), h3_r4, h3_r7
            FROM temp_cities;
        """)
        
        logger.info("Cities seeding completed successfully.")
    except Exception as e:
        logger.error(f"Error seeding cities: {e}")
        raise e
    finally:
        await conn.close()

def load_cities_from_db() -> Generator[List[Dict[str, Any]], None, None]:
    """
    Sync method to load cities from DB in batches of 100.
    Used by the Kafka producer to fetch cities to query from weather API.
    """
    import psycopg2
    from psycopg2.extras import RealDictCursor
    
    # Convert asyncpg connection string to psycopg2
    sync_dsn = DB_URL.replace("postgresql+asyncpg://", "postgresql://")
    
    conn = psycopg2.connect(sync_dsn, cursor_factory=RealDictCursor)
    try:
        with conn.cursor() as cur:
            # Query top cities (e.g. population > 50000 or capitals) to reduce API load
            # We want to poll weather for these cities
            cur.execute("""
                SELECT geoname_id, city_name, country_code, ST_Y(geom) as lat, ST_X(geom) as lon 
                FROM cities 
                WHERE population > 100000
                ORDER BY population DESC;
            """)
            
            batch = []
            for row in cur:
                batch.append(dict(row))
                if len(batch) == 100:
                    yield batch
                    batch = []
            if batch:
                yield batch
    finally:
        conn.close()

if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed_cities())
