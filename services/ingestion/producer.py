import os
import asyncio
import uuid
from datetime import datetime
import logging
import httpx
from typing import List, Dict, Any

from aiokafka import AIOKafkaProducer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer

from .weather_client import fetch_batch_weather
from .city_loader import load_cities_from_db

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")
SCHEMA_REGISTRY_URL = os.environ.get("SCHEMA_REGISTRY_URL", "http://localhost:8081")
TOPIC = "weather.observations.raw"

class WeatherProducer:
    def __init__(self):
        self.sr_client = SchemaRegistryClient({"url": SCHEMA_REGISTRY_URL})
        # Load schema string
        schema_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "services", "streaming", "schemas", "weather_observation.avsc"
        )
        with open(schema_path, "r") as f:
            self.schema_str = f.read()

        # Confluent Schema Registry serializer (uses fastavro or confluent-kafka under the hood)
        # Note: aiokafka takes bytes, so we will use the serializer to produce bytes
        self.serializer = AvroSerializer(
            self.sr_client,
            self.schema_str,
            to_dict=lambda val, ctx: val
        )
        self.producer = None
        self.http_client = None

    async def start(self):
        logger.info(f"Starting AIOKafkaProducer to {KAFKA_BOOTSTRAP}...")
        self.producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            compression_type="lz4",
            linger_ms=10,
        )
        await self.producer.start()
        self.http_client = httpx.AsyncClient()
        logger.info("Producer started.")

    async def stop(self):
        if self.producer:
            await self.producer.stop()
        if self.http_client:
            await self.http_client.aclose()
        logger.info("Producer stopped.")

    def map_weather_to_avro(self, city: Dict[str, Any], weather_data: Dict[str, Any]) -> Dict[str, Any]:
        current = weather_data.get("current", {})
        
        # Parse time to timestamp mills
        # Open-Meteo current.time is in ISO format local to the location, e.g. "2026-06-05T09:00"
        # Since timezone="auto", let's parse it. If timezone is not available, default to now.
        observed_time_ms = int(datetime.utcnow().timestamp() * 1000)
        if "time" in current:
            try:
                # Open-Meteo returns time as ISO string, e.g. "2026-06-05T09:00"
                dt = datetime.fromisoformat(current["time"])
                observed_time_ms = int(dt.timestamp() * 1000)
            except Exception:
                pass

        return {
            "observation_id": str(uuid.uuid4()),
            "location_id": int(city["geoname_id"]),
            "city_name": str(city["city_name"]),
            "country_code": str(city["country_code"]),
            "latitude": float(city["lat"]),
            "longitude": float(city["lon"]),
            "h3_index_r4": None,
            "h3_index_r7": None,
            "observed_at": observed_time_ms,
            "temperature": float(current["temperature_2m"]) if "temperature_2m" in current else None,
            "feels_like": float(current["apparent_temperature"]) if "apparent_temperature" in current else None,
            "humidity": int(current["relative_humidity_2m"]) if "relative_humidity_2m" in current else None,
            "wind_speed": float(current["wind_speed_10m"]) if "wind_speed_10m" in current else None,
            "wind_direction": int(current["wind_direction_10m"]) if "wind_direction_10m" in current else None,
            "precipitation": float(current["precipitation"]) if "precipitation" in current else None,
            "weather_code": int(current["weather_code"]) if "weather_code" in current else None,
            "pressure": float(current["surface_pressure"]) if "surface_pressure" in current else None,
            "visibility": int(current["visibility"]) if "visibility" in current else None,
            "uv_index": float(current["uv_index"]) if "uv_index" in current else None,
            "cloud_cover": int(current["cloud_cover"]) if "cloud_cover" in current else None,
            "schema_version": 1
        }

    async def produce_all_cities(self):
        """
        Poll cities and produce observations.
        """
        semaphore = asyncio.Semaphore(15)  # Max 15 concurrent calls
        
        async def fetch_and_produce(city_batch: List[Dict[str, Any]]):
            async with semaphore:
                # Open-Meteo returns array of results
                results = await fetch_batch_weather(city_batch, self.http_client)
                if not results:
                    return
                
                for idx, weather_data in enumerate(results):
                    if idx >= len(city_batch):
                        break
                    city = city_batch[idx]
                    try:
                        record = self.map_weather_to_avro(city, weather_data)
                        
                        # Serialize using Confluent AvroSerializer
                        # Confluent AvroSerializer requires subject name and values.
                        # Since it's confluent_kafka AvroSerializer, it takes value and SerializationContext
                        from confluent_kafka.serialization import SerializationContext, MessageField
                        ctx = SerializationContext(TOPIC, MessageField.VALUE)
                        serialized_value = self.serializer(record, ctx)
                        
                        await self.producer.send(TOPIC, value=serialized_value)
                    except Exception as e:
                        logger.error(f"Failed to produce weather record for {city['city_name']}: {e}")

        # Fetch batches of 100 cities from database
        batches = list(load_cities_from_db())
        logger.info(f"Fetched {len(batches)} batches of cities to poll.")
        
        tasks = [fetch_and_produce(batch) for batch in batches]
        await asyncio.gather(*tasks)
        logger.info("Successfully completed weather ingestion cycle.")

async def run_once():
    producer = WeatherProducer()
    await producer.start()
    try:
        await producer.produce_all_cities()
    finally:
        await producer.stop()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_once())
