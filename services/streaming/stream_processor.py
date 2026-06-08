import os
import asyncio
import json
import logging
import uuid
import numpy as np
from datetime import datetime, timezone
import h3
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer, AvroSerializer
from confluent_kafka.serialization import SerializationContext, MessageField
import redis.asyncio as aioredis
import asyncpg
from pydantic import BaseModel, Field, ValidationError
try:
    import geoweather_core
except ImportError:
    geoweather_core = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("stream_processor")

KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")
SCHEMA_REGISTRY_URL = os.environ.get("SCHEMA_REGISTRY_URL", "http://localhost:8081")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
TIMESCALE_URL = os.environ.get("TIMESCALE_URL", "postgresql://postgres:geoweather_local@localhost:5433/geoweather_ts")
POSTGRES_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:geoweather_local@localhost:5432/geoweather")

RAW_TOPIC = "weather.observations.raw"
ENRICHED_TOPIC = "weather.observations.enriched"
ALERTS_TOPIC = "weather.alerts"

# Helper to format URL for asyncpg
def get_asyncpg_dsn(url: str) -> str:
    # Convert sqlalchemy syntax if needed
    if "postgresql+asyncpg://" in url:
        return url.replace("postgresql+asyncpg://", "postgresql://")
    return url

class WeatherObservationValidator(BaseModel):
    temperature: float = Field(..., ge=-60, le=60)
    humidity: int = Field(..., ge=0, le=100)
    wind_speed: float = Field(..., ge=0, le=300)
    precipitation: float = Field(..., ge=0)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)

class WeatherStreamProcessor:
    def __init__(self):
        self.sr_client = SchemaRegistryClient({"url": SCHEMA_REGISTRY_URL})
        
        # Load Avro schema
        schema_path = os.path.join(
            os.path.dirname(__file__), "schemas", "weather_observation.avsc"
        )
        with open(schema_path, "r") as f:
            self.schema_str = f.read()

        # Serializer / Deserializer
        self.deserializer = AvroDeserializer(self.sr_client, self.schema_str)
        self.serializer = AvroSerializer(self.sr_client, self.schema_str, to_dict=lambda val, ctx: val)
        
        self.consumer = None
        self.producer = None
        self.redis = None
        self.pg_conn = None
        self.ts_conn = None

        # In-memory window aggregates & anomaly historical states
        # { h3_cell: [temperatures] }
        self.agg_windows = {}
        # { location_id: [temperatures] } (for Z-score rolling window)
        self.location_history = {}

    async def start(self):
        logger.info("Starting stream processor...")
        
        # Consumers & Producers
        self.consumer = AIOKafkaConsumer(
            RAW_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP,
            group_id="weather-processor-group",
            auto_offset_reset="latest"
        )
        await self.consumer.start()

        self.producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
        await self.producer.start()

        # Redis Connection
        self.redis = aioredis.from_url(REDIS_URL, decode_responses=True)
        await self.redis.ping()

        # DB Connections
        await self.ensure_db_connections()

        logger.info("Connections initialized. Processing messages...")

    async def ensure_db_connections(self):
        """Ensure pg_conn and ts_conn are open; reconnect if closed."""
        pg_dsn = get_asyncpg_dsn(POSTGRES_URL)
        ts_dsn = get_asyncpg_dsn(TIMESCALE_URL)

        # Check/reconnect Postgres
        if self.pg_conn is None or self.pg_conn.is_closed():
            logger.info("Reconnecting to Postgres...")
            try:
                self.pg_conn = await asyncpg.connect(pg_dsn)
                logger.info("Postgres reconnected.")
            except Exception as e:
                logger.error(f"Failed to reconnect to Postgres: {e}")
                raise

        # Check/reconnect TimescaleDB
        if self.ts_conn is None or self.ts_conn.is_closed():
            logger.info("Reconnecting to TimescaleDB...")
            try:
                self.ts_conn = await asyncpg.connect(ts_dsn)
                logger.info("TimescaleDB reconnected.")
            except Exception as e:
                logger.error(f"Failed to reconnect to TimescaleDB: {e}")
                raise

    async def stop(self):
        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()
        if self.redis:
            await self.redis.close()
        if self.pg_conn and not self.pg_conn.is_closed():
            await self.pg_conn.close()
        if self.ts_conn and not self.ts_conn.is_closed():
            await self.ts_conn.close()
        logger.info("Processor stopped.")

    async def process_message(self, raw_bytes: bytes):
        ctx = SerializationContext(RAW_TOPIC, MessageField.VALUE)
        # Deserialize from raw Avro
        record = self.deserializer(raw_bytes, ctx)
        if not record:
            return

        lat = record["latitude"]
        lon = record["longitude"]
        loc_id = record["location_id"]
        temp = record["temperature"]

        # 0. Data Quality / Anomaly Validation
        try:
            WeatherObservationValidator(
                temperature=temp,
                humidity=record["humidity"],
                wind_speed=record["wind_speed"],
                precipitation=record["precipitation"],
                latitude=lat,
                longitude=lon
            )
        except ValidationError as e:
            logger.warning(f"Data Quality Error for location {loc_id}: {e}. Skipping anomalous record.")
            return

        # Parse observed_at datetime / timestamp
        raw_observed = record["observed_at"]
        if isinstance(raw_observed, datetime):
            observed_at_dt = raw_observed.replace(tzinfo=timezone.utc) if raw_observed.tzinfo is None else raw_observed
        else:
            observed_at_dt = datetime.fromtimestamp(raw_observed / 1000, tz=timezone.utc)
        observed_at_ms = int(observed_at_dt.timestamp() * 1000)

        # 1. H3 Index enrichment
        h3_r4 = h3.latlng_to_cell(lat, lon, 4)
        h3_r7 = h3.latlng_to_cell(lat, lon, 7)
        record["h3_index_r4"] = h3_r4
        record["h3_index_r7"] = h3_r7

        # 2. Produce enriched record to Kafka enriched topic
        enrich_ctx = SerializationContext(ENRICHED_TOPIC, MessageField.VALUE)
        serialized_enrich = self.serializer(record, enrich_ctx)
        await self.producer.send_and_wait(ENRICHED_TOPIC, serialized_enrich)

        # 3. Update weather_current (Postgres cache) in-place
        await self.pg_conn.execute("""
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
            loc_id, temp, record["feels_like"], record["humidity"], record["wind_speed"],
            record["wind_direction"], record["precipitation"], record["weather_code"], record["pressure"],
            record["visibility"], record["uv_index"], record["cloud_cover"], observed_at_dt
        )

        # 4. Insert raw observation to TimescaleDB hypertable
        await self.ts_conn.execute("""
            INSERT INTO weather_observations (
                observation_id, location_id, h3_index_r4, h3_index_r7, temperature, feels_like, humidity, 
                wind_speed, wind_direction, precipitation, weather_code, 
                pressure, visibility, uv_index, cloud_cover, observed_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
            ON CONFLICT (location_id, observed_at) DO NOTHING;
        """,
            uuid.UUID(record["observation_id"]), loc_id, h3_r4, h3_r7, temp, record["feels_like"], record["humidity"],
            record["wind_speed"], record["wind_direction"], record["precipitation"], record["weather_code"],
            record["pressure"], record["visibility"], record["uv_index"], record["cloud_cover"], observed_at_dt
        )

        # 5. Tumbling hourly window aggregation per H3 resolution 4 cell
        # For demo purposes, we will update the aggregates table and publish to Redis in real-time
        # representing a sliding window aggregation.
        now_dt = datetime.utcnow()
        window_start = now_dt.replace(minute=0, second=0, microsecond=0)
        window_end = window_start.replace(hour=window_start.hour + 1) if window_start.hour < 23 else window_start.replace(day=window_start.day + 1, hour=0)
        
        # Query timescale for hourly aggregates of this H3 cell
        # First, let's update TimescaleDB hourly aggregates hypertable
        agg = await self.ts_conn.fetchrow("""
            SELECT 
                AVG(temperature) as avg_temp,
                MAX(wind_speed) as max_wind,
                SUM(precipitation) as total_precip,
                AVG(CAST(humidity AS FLOAT)) as avg_hum,
                COUNT(*) as obs_count
            FROM weather_observations
            WHERE h3_index_r4 = $1
              AND observed_at >= $2;
        """, h3_r4, window_start.replace(tzinfo=timezone.utc))

        if agg and agg["avg_temp"] is not None:
            # Write to Timescale hourly aggregates
            await self.ts_conn.execute("""
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
                h3_r4, window_start.replace(tzinfo=timezone.utc), window_end.replace(tzinfo=timezone.utc),
                float(agg["avg_temp"]), float(agg["max_wind"] or 0), float(agg["total_precip"] or 0),
                float(agg["avg_hum"]), int(agg["obs_count"])
            )

            # Publish to Redis Pub/Sub to trigger Websocket updates
            redis_msg = {
                "h3_index_r4": h3_r4,
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "avg_temperature": round(float(agg["avg_temp"]), 1),
                "max_wind_speed": round(float(agg["max_wind"] or 0), 1),
                "total_precip": round(float(agg["total_precip"] or 0), 1),
                "avg_humidity": round(float(agg["avg_hum"]), 1),
                "observation_count": int(agg["obs_count"])
            }
            await self.redis.publish(f"weather:h3:{h3_r4}", json.dumps(redis_msg))

        # 6. Z-score temperature anomaly detection
        if temp is not None:
            hist = self.location_history.setdefault(loc_id, [])
            hist.append(temp)
            # Keep history to last 20 readings (representing rolling window)
            if len(hist) > 20:
                hist.pop(0)

            if len(hist) >= 5:
                if geoweather_core:
                    is_anomaly, mean, std, zscore = geoweather_core.detect_anomaly_last(hist, 3.0)
                else:
                    hist_only = hist[:-1]
                    mean = float(np.mean(hist_only))
                    std = float(np.std(hist_only))
                    zscore = abs(temp - mean) / std if std > 0 else 0.0
                    is_anomaly = std > 0.1 and zscore > 3.0

                if is_anomaly:
                    # Anomaly alert triggered!
                    alert = {
                        "alert_id": str(uuid.uuid4()),
                        "location_id": loc_id,
                        "city_name": record["city_name"],
                        "temperature": temp,
                        "expected_mean": mean,
                        "expected_std": std,
                        "zscore": zscore,
                        "observed_at": record["observed_at"]
                    }
                    logger.warning(f"⚠️ TEMPERATURE ANOMALY DETECTED for {record['city_name']}: {temp}°C (expected mean: {mean:.1f}°C, z-score: {zscore:.1f})")
                    await self.producer.send(ALERTS_TOPIC, json.dumps(alert).encode('utf-8'))

    async def run(self):
        await self.start()
        try:
            async for msg in self.consumer:
                try:
                    # Ensure DB connections are alive before processing
                    await self.ensure_db_connections()
                    await self.process_message(msg.value)
                except (asyncpg.exceptions.InterfaceError, OSError) as e:
                    logger.error(f"DB connection lost: {e}. Will reconnect on next message.")
                    # Force close so ensure_db_connections() will reconnect
                    try:
                        if self.pg_conn and not self.pg_conn.is_closed():
                            await self.pg_conn.close()
                    except Exception:
                        pass
                    try:
                        if self.ts_conn and not self.ts_conn.is_closed():
                            await self.ts_conn.close()
                    except Exception:
                        pass
                    self.pg_conn = None
                    self.ts_conn = None
                    await asyncio.sleep(5)
                except Exception:
                    logger.exception("Error processing stream record")
        finally:
            await self.stop()

if __name__ == "__main__":
    processor = WeatherStreamProcessor()
    asyncio.run(processor.run())
