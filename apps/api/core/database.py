import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from .config import settings

logger = logging.getLogger(__name__)

# Engine for spatial postgres
postgres_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_size=10,
    max_overflow=20
)

# Engine for TimescaleDB
timescale_engine = create_async_engine(
    settings.TIMESCALE_URL,
    echo=False,
    future=True,
    pool_size=10,
    max_overflow=20
)

# Session makers
PostgresSessionLocal = sessionmaker(
    postgres_engine, class_=AsyncSession, expire_on_commit=False
)
TimescaleSessionLocal = sessionmaker(
    timescale_engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db():
    """Dependency to get PostGIS session."""
    async with PostgresSessionLocal() as session:
        yield session

async def get_ts_db():
    """Dependency to get TimescaleDB session."""
    async with TimescaleSessionLocal() as session:
        yield session

async def init_db():
    logger.info("Initializing database connections...")
    
    # Setup TimescaleDB tables programmatically
    async with timescale_engine.begin() as conn:
        logger.info("Creating TimescaleDB hypertables...")
        # Create observations table if not exists
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS weather_observations (
                observation_id UUID NOT NULL,
                location_id INTEGER NOT NULL,
                h3_index_r4 VARCHAR(15),
                h3_index_r7 VARCHAR(15),
                temperature REAL,
                feels_like REAL,
                humidity SMALLINT,
                wind_speed REAL,
                wind_direction SMALLINT,
                precipitation REAL,
                weather_code SMALLINT,
                pressure REAL,
                visibility INTEGER,
                uv_index REAL,
                cloud_cover SMALLINT,
                observed_at TIMESTAMPTZ NOT NULL,
                PRIMARY KEY (location_id, observed_at)
            );
        """))
        
        # Ensure h3 columns exist if table was already created
        await conn.execute(text("ALTER TABLE weather_observations ADD COLUMN IF NOT EXISTS h3_index_r4 VARCHAR(15);"))
        await conn.execute(text("ALTER TABLE weather_observations ADD COLUMN IF NOT EXISTS h3_index_r7 VARCHAR(15);"))
        
        # Check if it's already a hypertable before creating
        result = await conn.execute(text("""
            SELECT * FROM timescaledb_information.hypertables 
            WHERE hypertable_name = 'weather_observations';
        """))
        if not result.first():
            try:
                await conn.execute(text("""
                    SELECT create_hypertable('weather_observations', 'observed_at', 
                        partitioning_column => 'location_id', 
                        number_partitions => 16, 
                        chunk_time_interval => INTERVAL '1 day',
                        migrate_data => true);
                """))
                logger.info("Created weather_observations hypertable.")
            except Exception as e:
                logger.warning(f"Could not create hypertable weather_observations: {e}")

        # Create hourly aggregates table if not exists
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS weather_hourly_agg (
                h3_index_r4 VARCHAR(15) NOT NULL,
                window_start TIMESTAMPTZ NOT NULL,
                window_end TIMESTAMPTZ NOT NULL,
                avg_temperature REAL,
                max_wind_speed REAL,
                total_precip REAL,
                avg_humidity REAL,
                observation_count BIGINT,
                PRIMARY KEY (h3_index_r4, window_start)
            );
        """))

        result_agg = await conn.execute(text("""
            SELECT * FROM timescaledb_information.hypertables 
            WHERE hypertable_name = 'weather_hourly_agg';
        """))
        if not result_agg.first():
            try:
                await conn.execute(text("""
                    SELECT create_hypertable('weather_hourly_agg', 'window_start', 
                        chunk_time_interval => INTERVAL '7 days',
                        migrate_data => true);
                """))
                logger.info("Created weather_hourly_agg hypertable.")
            except Exception as e:
                logger.warning(f"Could not create hypertable weather_hourly_agg: {e}")

async def close_db():
    logger.info("Closing database engines...")
    await postgres_engine.dispose()
    await timescale_engine.dispose()
