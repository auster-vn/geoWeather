# 🌍 GeoWeather Intelligence Platform
### End-to-End Real-Time GIS & Weather Analytics System

> **Mục tiêu:** Xây dựng một production-grade platform hiển thị dữ liệu thời tiết thực tế trên bản đồ GIS tương tác, với streaming pipeline, spatial analytics, và AI-powered insights. Dự án này trình bày đầy đủ kỹ năng của một **Senior AI/Data Engineer** — từ ingestion, streaming, SQL/spatial, containerization đến CI/CD.

---

## 📋 Mục lục

1. [Tổng quan dự án](#1-tổng-quan-dự-án)
2. [System Architecture](#2-system-architecture)
3. [Tech Stack & Lý do chọn](#3-tech-stack--lý-do-chọn)
4. [Data Sources & Schema](#4-data-sources--schema)
5. [Phase 1 — Core Map & API](#5-phase-1--core-map--api)
6. [Phase 2 — Streaming Pipeline](#6-phase-2--streaming-pipeline)
7. [Phase 3 — Advanced GIS & AI](#7-phase-3--advanced-gis--ai)
8. [Phase 4 — Production & DevOps](#8-phase-4--production--devops)
9. [Cấu trúc Monorepo](#9-cấu-trúc-monorepo)
10. [Database Design](#10-database-design)
11. [CI/CD Pipeline](#11-cicd-pipeline)
12. [Monitoring & Observability](#12-monitoring--observability)
13. [Prompts cho AI Agent](#13-prompts-cho-ai-agent)
14. [CV Talking Points](#14-cv-talking-points)

---

## 1. Tổng quan dự án

**GeoWeather Intelligence Platform** là một hệ thống full-stack cho phép:

- **Real-time weather visualization** trên bản đồ thế giới (100,000+ địa điểm)
- **Streaming pipeline** ingest → process → serve với latency < 2 giây
- **Spatial analytics**: heatmap nhiệt độ, hexagon binning, isotherm contours, route weather
- **Historical time-series**: biểu đồ xu hướng thời tiết theo địa điểm
- **AI chatbot**: hỏi thời tiết bằng ngôn ngữ tự nhiên (Vietnamese & English)
- **Self-hosted tile server**: vector tiles từ PostGIS, không phụ thuộc third-party

### Điểm nổi bật với Hiring Manager

| Khía cạnh | Bằng chứng |
|---|---|
| **Data pipeline end-to-end** | Kafka → Flink → TimescaleDB → WebSocket → Browser |
| **Spatial / GIS depth** | PostGIS ST_functions, H3 hexagons, Deck.gl 3D layers, Martin tile server |
| **Modern streaming** | Apache Kafka + Flink SQL windowed aggregation |
| **Production mindset** | Docker multi-stage, K8s Helm, Terraform, GitHub Actions |
| **AI integration** | RAG-based weather chatbot với Claude API |
| **Observability** | Prometheus metrics, Grafana dashboards, Loki log aggregation |

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          EXTERNAL DATA SOURCES                          │
│  Open-Meteo API │ OpenWeatherMap API │ NOAA GFS │ GADM Boundaries (GeoJSON)│
└──────────┬──────────────────┬──────────────────┬────────────────────────┘
           │                  │                  │
           ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         INGESTION LAYER                                 │
│                                                                         │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐  │
│  │  Weather Poller  │    │  GeoJSON Loader  │    │  Historical Sync │  │
│  │  (APScheduler)   │    │  (One-time ETL)  │    │  (Backfill job)  │  │
│  │  Every 10 mins   │    │  Cities/Borders  │    │  90 days history │  │
│  └────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘  │
└───────────┼──────────────────────┼─────────────────────────┼───────────┘
            │                      │                          │
            ▼                      ▼                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      MESSAGE STREAMING LAYER                            │
│                                                                         │
│   Apache Kafka                                                          │
│   ├── Topic: weather.observations.raw      (raw readings, Avro)        │
│   ├── Topic: weather.observations.enriched (+ H3 index, + region)     │
│   ├── Topic: weather.alerts                (threshold violations)      │
│   └── Topic: weather.aggregates.hourly     (Flink output)             │
│                                                                         │
│   Schema Registry (Confluent-compatible)                                │
└──────────────┬──────────────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      STREAM PROCESSING LAYER                            │
│                                                                         │
│   Apache Flink (PyFlink + Flink SQL)                                   │
│   ├── Job 1: Enrich — join raw weather with city metadata (PostGIS)    │
│   ├── Job 2: Aggregate — 1h/6h/24h tumbling windows per H3 cell       │
│   ├── Job 3: Anomaly detect — z-score per location rolling 7-day      │
│   └── Job 4: Route weather — interpolate weather along polyline       │
│                                                                         │
│   State Backend: RocksDB    Checkpointing: S3 / MinIO                  │
└──────────────┬──────────────────────────────────────────────────────────┘
               │
    ┌──────────┼──────────┐
    ▼          ▼          ▼
┌──────┐  ┌──────────┐  ┌──────┐
│  PG  │  │Timescale │  │Redis │
│ +GIS │  │   DB     │  │Cache │
│ geo  │  │time-     │  │+ pub/│
│ data │  │series    │  │ sub  │
└──────┘  └──────────┘  └──────┘
    │          │          │
    └──────────┼──────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         API LAYER                                       │
│                                                                         │
│   FastAPI (Python 3.12, async)                                         │
│   ├── REST   /api/v1/weather/{lat}/{lon}                               │
│   ├── REST   /api/v1/weather/region/{h3_index}                        │
│   ├── REST   /api/v1/weather/route  (POST polyline)                    │
│   ├── WebSocket  /ws/live/{location_id}                                │
│   ├── SSE   /api/v1/stream/global-updates                             │
│   ├── GraphQL  /graphql  (Strawberry, async resolvers)                 │
│   └── Tiles  /tiles/{z}/{x}/{y}.mvt  (proxy → Martin)                 │
│                                                                         │
│   Middleware: JWT auth, rate limiting (slowapi), CORS, GZip            │
└──────────────┬──────────────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        FRONTEND LAYER                                   │
│                                                                         │
│   Next.js 15 (App Router, React Server Components)                     │
│   ├── MapLibre GL JS — base map + custom layers                        │
│   ├── Deck.gl — HexagonLayer, HeatmapLayer, ColumnLayer, PathLayer     │
│   ├── H3-js — client-side hexagon resolution switch                    │
│   ├── TanStack Query — server state, stale-while-revalidate            │
│   ├── Zustand — UI state (selected location, active layers)            │
│   ├── Recharts — time-series charts in side panel                      │
│   └── AI Chatbot — Claude API streaming responses                      │
│                                                                         │
│   Deployment: Vercel (preview) + K8s (production)                      │
└─────────────────────────────────────────────────────────────────────────┘
```

### Data Flow Sequence (Happy Path)

```
1. APScheduler trigger (T+0:00)
   → Fetch 50,000 cities from Open-Meteo (batch API, 1 request)
   → Produce Avro records to Kafka topic: weather.observations.raw

2. Flink Job 1 — Enrich (T+0:05s)
   → Consume raw topic
   → Async lookup PostGIS: ST_Within(point, region_geometry)
   → Add H3 index (resolution 4) to each record
   → Produce to: weather.observations.enriched

3. Flink Job 2 — Aggregate (T+0:05s, 1-hour tumbling window)
   → GROUP BY h3_index, window_start
   → AVG(temp), MAX(wind_speed), SUM(precipitation)
   → Sink to TimescaleDB hypertable: weather_hourly_agg
   → Produce to: weather.aggregates.hourly

4. FastAPI WebSocket consumer
   → Subscribe Redis pub/sub channel (Flink → Redis sink)
   → Push delta updates to connected browsers

5. Browser (T+0:02s after step 1 completes)
   → Receives WebSocket message: {h3_index, avg_temp, ...}
   → Deck.gl HexagonLayer re-renders affected cells
```

---

## 3. Tech Stack & Lý do chọn

### Frontend

| Tool | Version | Lý do chọn |
|---|---|---|
| **Next.js** | 15 | App Router, RSC, streaming SSR, image optimization |
| **MapLibre GL JS** | 4.x | Open-source Mapbox alternative, WebGL, custom layers, self-hostable tiles |
| **Deck.gl** | 9.x | GPU-accelerated large dataset visualization (100k+ points smooth) |
| **H3-js** | 4.x | Uber's hexagonal grid system, multi-resolution spatial indexing |
| **TanStack Query** | 5.x | Async state, caching, background refetch, optimistic updates |
| **Zustand** | 5.x | Lightweight state, no boilerplate, works với RSC |
| **Recharts** | 2.x | Composable charts cho time-series panel |
| **TypeScript** | 5.x | Type safety, IDE support, API contract |

### Backend

| Tool | Version | Lý do chọn |
|---|---|---|
| **FastAPI** | 0.115+ | Async-first, auto OpenAPI docs, Pydantic v2, native WebSocket |
| **Pydantic v2** | 2.x | 5–20x faster validation vs v1, Rust core |
| **SQLAlchemy** | 2.x | Async ORM, GeoAlchemy2 cho spatial types |
| **GeoAlchemy2** | 0.15+ | SQLAlchemy extension cho PostGIS geometry types |
| **GeoPandas** | 1.x | Spatial dataframe operations, CRS transforms |
| **Shapely** | 2.x | Geometry operations (buffer, intersection, distance) |
| **h3-py** | 4.x | H3 hexagon encoding/decoding server-side |
| **Strawberry** | 0.24+ | Code-first GraphQL, async resolvers, DataLoader |
| **httpx** | 0.27+ | Async HTTP client cho weather API calls |
| **APScheduler** | 4.x | Async job scheduler cho polling |

### Data Pipeline

| Tool | Version | Lý do chọn |
|---|---|---|
| **Apache Kafka** | 3.7 | Distributed log, durable, replay-able, industry standard |
| **Confluent Schema Registry** | 7.x | Avro schema evolution, backward/forward compatibility |
| **Apache Flink** | 1.19 | Stateful stream processing, exactly-once semantics, Flink SQL |
| **PyFlink** | 1.19 | Python API cho Flink jobs |
| **fastavro** | 1.x | Fast Avro serialization/deserialization |

### Databases

| Tool | Version | Lý do chọn |
|---|---|---|
| **PostgreSQL** | 16 | Foundation, JSONB, full-text search |
| **PostGIS** | 3.4 | Spatial extension — ST_Within, ST_Distance, spatial indices (GIST) |
| **TimescaleDB** | 2.x | Time-series hypertables, continuous aggregates, retention policies |
| **Redis** | 7.x | Cache, pub/sub channel cho real-time, sorted sets cho leaderboards |
| **MinIO** | RELEASE.2024 | S3-compatible object store, Flink checkpoint backend |

### Tile Server

| Tool | Version | Lý do chọn |
|---|---|---|
| **Martin** | 0.14 | Rust-based, PostGIS → MVT tiles, cực nhanh, self-hosted |
| **PMTiles** | 3.x | Serverless tile format, host trên S3/CloudFront |

### Infrastructure

| Tool | Version | Lý do chọn |
|---|---|---|
| **Docker** | 26+ | Containerization, multi-stage builds |
| **Docker Compose** | v2 | Local development orchestration |
| **Kubernetes** | 1.30 | Production orchestration, HPA, rolling deploys |
| **Helm** | 3.x | K8s package manager, templating |
| **Terraform** | 1.9 | IaC cho GCP/AWS resources |
| **GitHub Actions** | — | CI/CD, matrix builds, environment protection |

### Observability

| Tool | Version | Lý do chọn |
|---|---|---|
| **Prometheus** | 2.x | Metrics scraping, alerting rules |
| **Grafana** | 11.x | Dashboards, Explore, alerting UI |
| **Loki** | 3.x | Log aggregation, LogQL |
| **Tempo** | 2.x | Distributed tracing (OpenTelemetry) |
| **OpenTelemetry** | 1.x | Auto-instrumentation FastAPI, Kafka, Flink |

---

## 4. Data Sources & Schema

### Weather Data — Open-Meteo (Free, No Key Required)

```python
# services/ingestion/weather_client.py
import httpx
from typing import AsyncGenerator

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

async def fetch_batch_weather(
    locations: list[dict],  # [{"lat": 10.7, "lon": 106.7}, ...]
    client: httpx.AsyncClient,
) -> list[dict]:
    """
    Open-Meteo batch API: up to 100 locations per request.
    Returns current weather for all locations in one HTTP call.
    """
    params = {
        "latitude": ",".join(str(loc["lat"]) for loc in locations),
        "longitude": ",".join(str(loc["lon"]) for loc in locations),
        "current": ",".join(WEATHER_VARIABLES),
        "wind_speed_unit": "ms",
        "timezone": "auto",
    }
    response = await client.get(OPEN_METEO_BATCH_URL, params=params)
    response.raise_for_status()
    return response.json()
```

### Avro Schema — Weather Observation

```json
{
  "namespace": "geoweather.observations",
  "type": "record",
  "name": "WeatherObservation",
  "fields": [
    {"name": "observation_id", "type": "string"},
    {"name": "location_id",    "type": "int"},
    {"name": "city_name",      "type": "string"},
    {"name": "country_code",   "type": "string"},
    {"name": "latitude",       "type": "double"},
    {"name": "longitude",      "type": "double"},
    {"name": "h3_index_r4",    "type": "string"},
    {"name": "h3_index_r7",    "type": "string"},
    {"name": "observed_at",    "type": {"type": "long", "logicalType": "timestamp-millis"}},
    {"name": "temperature",    "type": ["null", "float"], "default": null},
    {"name": "feels_like",     "type": ["null", "float"], "default": null},
    {"name": "humidity",       "type": ["null", "int"],   "default": null},
    {"name": "wind_speed",     "type": ["null", "float"], "default": null},
    {"name": "wind_direction", "type": ["null", "int"],   "default": null},
    {"name": "precipitation",  "type": ["null", "float"], "default": null},
    {"name": "weather_code",   "type": ["null", "int"],   "default": null},
    {"name": "pressure",       "type": ["null", "float"], "default": null},
    {"name": "visibility",     "type": ["null", "int"],   "default": null},
    {"name": "uv_index",       "type": ["null", "float"], "default": null},
    {"name": "cloud_cover",    "type": ["null", "int"],   "default": null},
    {"name": "schema_version", "type": "int", "default": 1}
  ]
}
```

### Địa điểm — GeoNames World Cities Dataset

```sql
-- 47,000+ cities với population > 500
-- Download: https://download.geonames.org/export/dump/cities500.zip
-- Load một lần vào PostGIS

CREATE TABLE cities (
    geoname_id   INTEGER PRIMARY KEY,
    city_name    VARCHAR(200) NOT NULL,
    ascii_name   VARCHAR(200),
    country_code CHAR(2),
    admin1_code  VARCHAR(20),
    population   INTEGER,
    timezone     VARCHAR(40),
    geom         GEOMETRY(POINT, 4326)
);

CREATE INDEX cities_geom_gist ON cities USING GIST(geom);
CREATE INDEX cities_country_idx ON cities(country_code);
```

---

## 5. Phase 1 — Core Map & API

### 5.1 Backend: FastAPI Application Structure

```python
# apps/api/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address

from .routers import weather, locations, tiles, websocket, graphql_router
from .core.database import init_db, close_db
from .core.redis import init_redis, close_redis
from .core.telemetry import setup_telemetry

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await init_redis()
    setup_telemetry(app)
    yield
    await close_db()
    await close_redis()

app = FastAPI(
    title="GeoWeather API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(CORSMiddleware, allow_origins=["*"])

app.include_router(weather.router,    prefix="/api/v1/weather")
app.include_router(locations.router,  prefix="/api/v1/locations")
app.include_router(tiles.router,      prefix="/tiles")
app.include_router(websocket.router,  prefix="/ws")
app.include_router(graphql_router,    prefix="/graphql")
```

### 5.2 Spatial Query — Nearest Weather by Coordinates

```python
# apps/api/routers/weather.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from ..core.database import get_db
from ..schemas.weather import WeatherResponse

router = APIRouter()

@router.get("/{lat}/{lon}", response_model=WeatherResponse)
async def get_weather_by_coords(
    lat: float,
    lon: float,
    db: AsyncSession = Depends(get_db),
):
    """
    Find nearest city and return latest weather reading.
    Uses PostGIS ST_DWithin + KNN spatial index for sub-millisecond lookup.
    """
    query = text("""
        WITH nearest_city AS (
            SELECT
                c.geoname_id,
                c.city_name,
                c.country_code,
                ST_Distance(
                    c.geom::geography,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                ) AS distance_meters
            FROM cities c
            WHERE ST_DWithin(
                c.geom::geography,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                200000  -- 200km radius
            )
            ORDER BY c.geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
            LIMIT 1
        )
        SELECT
            nc.*,
            wo.temperature,
            wo.feels_like,
            wo.humidity,
            wo.wind_speed,
            wo.wind_direction,
            wo.precipitation,
            wo.weather_code,
            wo.observed_at
        FROM nearest_city nc
        JOIN weather_observations wo ON wo.location_id = nc.geoname_id
        WHERE wo.observed_at = (
            SELECT MAX(observed_at)
            FROM weather_observations
            WHERE location_id = nc.geoname_id
        )
    """)
    result = await db.execute(query, {"lat": lat, "lon": lon})
    row = result.mappings().first()
    return WeatherResponse(**row)
```

### 5.3 Frontend: Map Component

```typescript
// apps/web/components/map/WeatherMap.tsx
'use client'

import { useRef, useEffect, useCallback } from 'react'
import maplibregl from 'maplibre-gl'
import { DeckGL } from '@deck.gl/react'
import { HeatmapLayer, HexagonLayer } from '@deck.gl/aggregation-layers'
import { ScatterplotLayer } from '@deck.gl/layers'
import { useWeatherStore } from '@/store/weather'
import { useGlobalWeather } from '@/hooks/useGlobalWeather'

export function WeatherMap() {
  const mapRef = useRef<maplibregl.Map | null>(null)
  const { activeLayer, resolution } = useWeatherStore()
  const { data: weatherPoints } = useGlobalWeather()

  const layers = useMemo(() => {
    if (!weatherPoints) return []

    switch (activeLayer) {
      case 'heatmap':
        return [new HeatmapLayer({
          id: 'temperature-heatmap',
          data: weatherPoints,
          getPosition: d => [d.longitude, d.latitude],
          getWeight: d => d.temperature + 40, // normalize to positive
          radiusPixels: 60,
          intensity: 1,
          threshold: 0.05,
          colorRange: [
            [0, 0, 255, 0],
            [0, 128, 255, 128],
            [0, 255, 128, 200],
            [255, 255, 0, 220],
            [255, 128, 0, 240],
            [255, 0, 0, 255],
          ],
        })]

      case 'hexagon':
        return [new HexagonLayer({
          id: 'temperature-hexagon',
          data: weatherPoints,
          getPosition: d => [d.longitude, d.latitude],
          getElevationWeight: d => d.wind_speed,
          getColorWeight: d => d.temperature,
          radius: resolution === 'high' ? 30000 : 80000,
          elevationScale: 500,
          extruded: true,
          pickable: true,
          colorRange: TEMPERATURE_COLOR_RANGE,
        })]

      default:
        return [new ScatterplotLayer({
          id: 'weather-points',
          data: weatherPoints,
          getPosition: d => [d.longitude, d.latitude],
          getFillColor: d => temperatureToColor(d.temperature),
          getRadius: 8000,
          radiusMinPixels: 3,
          radiusMaxPixels: 12,
          pickable: true,
          onHover: ({ object }) => object && showWeatherPopup(object),
        })]
    }
  }, [weatherPoints, activeLayer, resolution])

  return (
    <DeckGL
      initialViewState={{
        latitude: 20,
        longitude: 0,
        zoom: 2,
        pitch: activeLayer === 'hexagon' ? 45 : 0,
      }}
      controller={{ touchRotate: true, keyboard: true }}
      layers={layers}
    >
      <maplibregl.Map
        style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
        ref={mapRef}
      />
    </DeckGL>
  )
}
```

---

## 6. Phase 2 — Streaming Pipeline

### 6.1 Kafka Producer

```python
# services/ingestion/producer.py
import asyncio
from aiokafka import AIOKafkaProducer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
from .weather_client import fetch_batch_weather
from .city_loader import load_cities_in_batches

KAFKA_BOOTSTRAP = "kafka:9092"
SCHEMA_REGISTRY_URL = "http://schema-registry:8081"
TOPIC = "weather.observations.raw"

class WeatherProducer:
    def __init__(self):
        sr_client = SchemaRegistryClient({"url": SCHEMA_REGISTRY_URL})
        self.serializer = AvroSerializer(
            sr_client,
            schema_str=open("schemas/weather_observation.avsc").read(),
        )

    async def start(self):
        self.producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_serializer=self.serializer,
            compression_type="lz4",
            linger_ms=10,        # micro-batch for throughput
            batch_size=65536,
        )
        await self.producer.start()

    async def produce_all_cities(self):
        """
        Poll all 47k cities in batches of 100 (API limit).
        Produces ~470 HTTP calls, ~47,000 Kafka messages.
        Completes in ~30s with async concurrency.
        """
        semaphore = asyncio.Semaphore(20)  # max 20 concurrent requests

        async def fetch_and_produce(batch: list[dict]):
            async with semaphore:
                readings = await fetch_batch_weather(batch, self.http_client)
                for reading in readings:
                    await self.producer.send(TOPIC, value=reading)

        batches = list(load_cities_in_batches(batch_size=100))
        await asyncio.gather(*[fetch_and_produce(b) for b in batches])
        print(f"Produced {len(batches) * 100} observations")
```

### 6.2 Flink Stream Processing Jobs

```python
# services/streaming/jobs/enrich_job.py
"""
Flink Job 1: Enrich raw observations with H3 index and region info.
Reads from: weather.observations.raw
Writes to:  weather.observations.enriched
"""
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import KafkaSource, KafkaSink
from pyflink.common.typeinfo import Types
import h3

env = StreamExecutionEnvironment.get_execution_environment()
env.set_parallelism(4)
env.enable_checkpointing(30_000)  # checkpoint every 30s

source = (KafkaSource.builder()
    .set_bootstrap_servers("kafka:9092")
    .set_topics("weather.observations.raw")
    .set_group_id("flink-enrich-consumer")
    .set_starting_offsets(OffsetsInitializer.latest())
    .set_value_only_deserializer(AvroDeserializationSchema(WeatherObservation))
    .build())

def enrich_with_h3(observation: dict) -> dict:
    lat, lon = observation["latitude"], observation["longitude"]
    observation["h3_index_r4"] = h3.latlng_to_cell(lat, lon, 4)   # ~288km avg edge
    observation["h3_index_r7"] = h3.latlng_to_cell(lat, lon, 7)   # ~5.6km avg edge
    return observation

stream = (env
    .from_source(source, WatermarkStrategy.no_watermarks(), "kafka-raw")
    .map(enrich_with_h3, output_type=Types.MAP(Types.STRING(), Types.PICKLED_BYTE_ARRAY()))
    .sink_to(kafka_enriched_sink))

env.execute("weather-enrich-job")
```

```sql
-- services/streaming/jobs/aggregate_job.sql
-- Flink SQL Job 2: 1-hour tumbling window aggregation per H3 cell

CREATE TABLE weather_enriched (
    observation_id  STRING,
    h3_index_r4     STRING,
    h3_index_r7     STRING,
    country_code    STRING,
    temperature     FLOAT,
    wind_speed      FLOAT,
    precipitation   FLOAT,
    humidity        INT,
    observed_at     TIMESTAMP(3),
    WATERMARK FOR observed_at AS observed_at - INTERVAL '1' MINUTE
) WITH (
    'connector' = 'kafka',
    'topic'     = 'weather.observations.enriched',
    'format'    = 'avro-confluent',
    'avro-confluent.url' = 'http://schema-registry:8081'
);

CREATE TABLE weather_hourly_agg (
    h3_index_r4       STRING,
    window_start      TIMESTAMP(3),
    window_end        TIMESTAMP(3),
    avg_temperature   FLOAT,
    max_wind_speed    FLOAT,
    total_precip      FLOAT,
    avg_humidity      FLOAT,
    observation_count BIGINT,
    PRIMARY KEY (h3_index_r4, window_start) NOT ENFORCED
) WITH (
    'connector' = 'jdbc',
    'url'       = 'jdbc:postgresql://timescaledb:5432/geoweather',
    'table-name'= 'weather_hourly_agg'
);

-- 1-hour tumbling window
INSERT INTO weather_hourly_agg
SELECT
    h3_index_r4,
    TUMBLE_START(observed_at, INTERVAL '1' HOUR) AS window_start,
    TUMBLE_END(observed_at,   INTERVAL '1' HOUR) AS window_end,
    AVG(temperature)   AS avg_temperature,
    MAX(wind_speed)    AS max_wind_speed,
    SUM(precipitation) AS total_precip,
    AVG(humidity)      AS avg_humidity,
    COUNT(*)           AS observation_count
FROM TABLE(
    TUMBLE(TABLE weather_enriched, DESCRIPTOR(observed_at), INTERVAL '1' HOUR)
)
GROUP BY h3_index_r4, TUMBLE_START(observed_at, INTERVAL '1' HOUR), TUMBLE_END(observed_at, INTERVAL '1' HOUR);
```

### 6.3 WebSocket Real-time Push

```python
# apps/api/routers/websocket.py
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..core.redis import get_redis

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.subscriptions: dict[str, set[WebSocket]] = {}

    async def subscribe(self, ws: WebSocket, h3_cells: list[str]):
        await ws.accept()
        for cell in h3_cells:
            self.subscriptions.setdefault(cell, set()).add(ws)

    async def broadcast_update(self, h3_index: str, data: dict):
        dead = set()
        for ws in self.subscriptions.get(h3_index, set()):
            try:
                await ws.send_json(data)
            except:
                dead.add(ws)
        self.subscriptions[h3_index] -= dead

manager = ConnectionManager()

@router.websocket("/weather/{h3_index}")
async def weather_stream(websocket: WebSocket, h3_index: str):
    """
    Client subscribes to a specific H3 cell.
    Receives push when Flink produces new aggregate for that cell.
    """
    await manager.subscribe(websocket, [h3_index])
    redis = await get_redis()

    # Also listen on parent cells (zoom-out support)
    import h3
    parent_cells = [h3.cell_to_parent(h3_index, r) for r in [4, 3, 2]]
    await manager.subscribe(websocket, parent_cells)

    try:
        # Keep connection alive, wait for client pings
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass

async def redis_listener():
    """Background task: listen to Redis pub/sub, broadcast to WebSocket clients."""
    redis = await get_redis()
    pubsub = redis.pubsub()
    await pubsub.psubscribe("weather:h3:*")

    async for message in pubsub.listen():
        if message["type"] == "pmessage":
            h3_index = message["channel"].decode().split(":")[-1]
            data = json.loads(message["data"])
            await manager.broadcast_update(h3_index, data)
```

---

## 7. Phase 3 — Advanced GIS & AI

### 7.1 Route Weather API

```python
# apps/api/routers/weather.py (thêm endpoint)

from shapely.geometry import LineString
import geopandas as gpd
from pyproj import Geod

@router.post("/route")
async def get_route_weather(
    polyline: list[tuple[float, float]],  # [(lat, lon), ...]
    interval_km: float = 50.0,
    db: AsyncSession = Depends(get_db),
):
    """
    Given a route (list of coordinates), return weather at regular intervals.
    Uses ST_LineInterpolatePoints for spatial interpolation.
    
    Example use case: Ho Chi Minh → Hà Nội road trip weather check.
    """
    line = LineString([(lon, lat) for lat, lon in polyline])
    geod = Geod(ellps="WGS84")
    total_length = geod.geometry_length(line) / 1000  # meters → km
    n_points = max(2, int(total_length / interval_km))

    query = text("""
        WITH route AS (
            SELECT ST_GeomFromText(:wkt, 4326) AS geom
        ),
        sample_points AS (
            SELECT 
                generate_series(0, :n_points) AS idx,
                ST_LineInterpolatePoint(route.geom, generate_series(0, :n_points)::float / :n_points) AS pt
            FROM route
        )
        SELECT
            sp.idx,
            ST_Y(sp.pt) AS latitude,
            ST_X(sp.pt) AS longitude,
            wo.temperature,
            wo.weather_code,
            wo.wind_speed,
            wo.precipitation
        FROM sample_points sp
        CROSS JOIN LATERAL (
            SELECT wo.*
            FROM weather_observations wo
            JOIN cities c ON c.geoname_id = wo.location_id
            ORDER BY c.geom <-> sp.pt
            LIMIT 1
        ) wo
        ORDER BY sp.idx
    """)
    result = await db.execute(query, {
        "wkt": line.wkt,
        "n_points": n_points,
    })
    return result.mappings().all()
```

### 7.2 TimescaleDB Continuous Aggregates

```sql
-- Hypertable for raw observations
SELECT create_hypertable('weather_observations', 'observed_at',
    chunk_time_interval => INTERVAL '1 day');

-- Continuous aggregate: hourly stats per location
CREATE MATERIALIZED VIEW weather_hourly_stats
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', observed_at) AS bucket,
    location_id,
    AVG(temperature)   AS avg_temp,
    MIN(temperature)   AS min_temp,
    MAX(temperature)   AS max_temp,
    AVG(humidity)      AS avg_humidity,
    SUM(precipitation) AS total_precip,
    MAX(wind_speed)    AS max_wind,
    COUNT(*)           AS readings
FROM weather_observations
GROUP BY bucket, location_id
WITH NO DATA;

-- Auto-refresh policy
SELECT add_continuous_aggregate_policy('weather_hourly_stats',
    start_offset => INTERVAL '2 hours',
    end_offset   => INTERVAL '10 minutes',
    schedule_interval => INTERVAL '10 minutes');

-- Data retention: keep raw 7 days, hourly 1 year, daily forever
SELECT add_retention_policy('weather_observations', INTERVAL '7 days');

-- Compression: auto-compress chunks older than 1 day (up to 95% size reduction)
ALTER TABLE weather_observations SET (
    timescaledb.compress,
    timescaledb.compress_orderby = 'observed_at DESC',
    timescaledb.compress_segmentby = 'location_id'
);
SELECT add_compression_policy('weather_observations', INTERVAL '1 day');
```

### 7.3 AI Weather Chatbot

```python
# apps/api/routers/chat.py
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import anthropic
from ..tools.weather_tools import weather_tool_definitions, execute_tool

router = APIRouter()
client = anthropic.AsyncAnthropic()

SYSTEM_PROMPT = """
Bạn là GeoWeather Assistant, trợ lý thời tiết thông minh tích hợp với hệ thống GIS.

Bạn có quyền truy cập các công cụ:
- get_weather(lat, lon): lấy thời tiết hiện tại tại tọa độ
- get_weather_by_city(city_name): tìm thành phố và trả về thời tiết
- get_weather_forecast(lat, lon, days): dự báo N ngày tới
- get_route_weather(origin, destination): thời tiết dọc tuyến đường
- compare_cities(city_list): so sánh thời tiết nhiều thành phố
- get_regional_stats(country_code): thống kê thời tiết theo quốc gia

Trả lời bằng ngôn ngữ của người dùng (Tiếng Việt hoặc English).
Khi cần hiển thị dữ liệu địa lý, thêm tag [MAP:lat,lon,zoom] để frontend render.
"""

@router.post("/stream")
async def chat_stream(message: str, history: list[dict]):
    async def generate():
        messages = history + [{"role": "user", "content": message}]

        async with client.messages.stream(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=weather_tool_definitions(),
            messages=messages,
        ) as stream:
            async for event in stream:
                if event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        yield f"data: {json.dumps({'type': 'text', 'content': event.delta.text})}\n\n"

                elif event.type == "content_block_stop":
                    # Check if we need to execute a tool
                    pass

                elif event.type == "message_delta":
                    if event.delta.stop_reason == "tool_use":
                        tool_results = await execute_tool(stream.current_message)
                        yield f"data: {json.dumps({'type': 'tool_result', 'data': tool_results})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

### 7.4 Anomaly Detection với Flink

```python
# services/streaming/jobs/anomaly_job.py
"""
Flink Job 3: Z-score based anomaly detection.
Detects temperatures deviating > 3 sigma from rolling 7-day baseline.
Produces alerts to: weather.alerts topic.
"""

def compute_zscore(value: float, mean: float, std: float) -> float:
    if std == 0:
        return 0
    return abs(value - mean) / std

class AnomalyDetector(MapFunction):
    def __init__(self):
        self.state: ValueState = None  # (rolling_mean, rolling_std, count)

    def open(self, runtime_context):
        descriptor = ValueStateDescriptor("rolling_stats", Types.PICKLED_BYTE_ARRAY())
        self.state = runtime_context.get_state(descriptor)

    def map(self, observation: dict) -> dict | None:
        stats = self.state.value() or {"mean": observation["temperature"], "std": 5.0, "count": 1}

        zscore = compute_zscore(observation["temperature"], stats["mean"], stats["std"])

        # Welford's online algorithm for streaming mean/variance
        n = stats["count"] + 1
        delta = observation["temperature"] - stats["mean"]
        new_mean = stats["mean"] + delta / n
        delta2 = observation["temperature"] - new_mean
        new_m2 = stats.get("m2", 0) + delta * delta2
        new_std = (new_m2 / n) ** 0.5 if n > 1 else 5.0

        self.state.update({"mean": new_mean, "std": new_std, "m2": new_m2, "count": n})

        if zscore > 3.0:
            return {
                "alert_type": "temperature_anomaly",
                "location_id": observation["location_id"],
                "city_name": observation["city_name"],
                "temperature": observation["temperature"],
                "expected_range": f"{new_mean-2*new_std:.1f}°C — {new_mean+2*new_std:.1f}°C",
                "zscore": zscore,
                "observed_at": observation["observed_at"],
            }
        return None
```

---

## 8. Phase 4 — Production & DevOps

### 8.1 Docker Multi-Stage Build

```dockerfile
# apps/api/Dockerfile
FROM python:3.12-slim AS base
WORKDIR /app
RUN apt-get update && apt-get install -y \
    libgdal-dev libgeos-dev libproj-dev \
    && rm -rf /var/lib/apt/lists/*

# Dependencies layer (cached separately)
FROM base AS deps
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev

# Development
FROM deps AS dev
RUN uv sync --frozen
CMD ["uvicorn", "main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]

# Production — minimal image
FROM base AS prod
COPY --from=deps /app/.venv /app/.venv
COPY . .
ENV PATH="/app/.venv/bin:$PATH"
RUN adduser --disabled-password --no-create-home appuser
USER appuser
EXPOSE 8000
CMD ["uvicorn", "main:app", "--workers", "4", "--host", "0.0.0.0", "--port", "8000"]
```

### 8.2 Docker Compose (Local Dev)

```yaml
# docker-compose.yml
version: "3.9"

services:
  postgres:
    image: postgis/postgis:16-3.4
    environment:
      POSTGRES_DB: geoweather
      POSTGRES_PASSWORD: geoweather_local
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./infra/docker/init-db.sql:/docker-entrypoint-initdb.d/01-init.sql
    ports: ["5432:5432"]
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "postgres"]

  timescaledb:
    image: timescale/timescaledb-ha:pg16
    environment:
      POSTGRES_DB: geoweather_ts
      POSTGRES_PASSWORD: geoweather_local
    volumes:
      - timescale_data:/var/lib/postgresql/data
    ports: ["5433:5432"]

  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru
    ports: ["6379:6379"]

  kafka:
    image: confluentinc/cp-kafka:7.7.0
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka:9093
      CLUSTER_ID: "MkU3OEVBNTcwNTJENDM2Qk"
    ports: ["9092:9092"]

  schema-registry:
    image: confluentinc/cp-schema-registry:7.7.0
    environment:
      SCHEMA_REGISTRY_KAFKASTORE_BOOTSTRAP_SERVERS: PLAINTEXT://kafka:9092
      SCHEMA_REGISTRY_HOST_NAME: schema-registry
    ports: ["8081:8081"]
    depends_on: [kafka]

  flink-jobmanager:
    image: flink:1.19-python3
    command: jobmanager
    environment:
      FLINK_PROPERTIES: |
        jobmanager.rpc.address: flink-jobmanager
        state.backend: rocksdb
        s3.endpoint: http://minio:9000
    ports: ["8082:8081"]
    volumes:
      - ./services/streaming:/opt/flink/userjobs

  flink-taskmanager:
    image: flink:1.19-python3
    command: taskmanager
    environment:
      FLINK_PROPERTIES: |
        jobmanager.rpc.address: flink-jobmanager
        taskmanager.numberOfTaskSlots: 4
    depends_on: [flink-jobmanager]

  martin:
    image: urbica/martin:latest
    environment:
      DATABASE_URL: postgresql://postgres:geoweather_local@postgres:5432/geoweather
    ports: ["3000:3000"]
    depends_on: [postgres]

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minio
      MINIO_ROOT_PASSWORD: minio_password
    ports: ["9000:9000", "9001:9001"]
    volumes:
      - minio_data:/data

  api:
    build:
      context: ./apps/api
      target: dev
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:geoweather_local@postgres/geoweather
      TIMESCALE_URL: postgresql+asyncpg://postgres:geoweather_local@timescaledb/geoweather_ts
      REDIS_URL: redis://redis:6379/0
      KAFKA_BOOTSTRAP: kafka:9092
      SCHEMA_REGISTRY_URL: http://schema-registry:8081
    ports: ["8000:8000"]
    volumes:
      - ./apps/api:/app
    depends_on: [postgres, redis, kafka]

  web:
    build: ./apps/web
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
      NEXT_PUBLIC_MAPLIBRE_STYLE: https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json
    ports: ["3001:3000"]
    volumes:
      - ./apps/web:/app
      - /app/node_modules
      - /app/.next

volumes:
  postgres_data:
  timescale_data:
  minio_data:
```

### 8.3 Kubernetes Helm Chart

```yaml
# infra/k8s/geoweather/values.yaml

global:
  imageRegistry: ghcr.io/your-username/geoweather
  imageTag: latest

api:
  replicaCount: 3
  image:
    repository: api
  resources:
    requests: {cpu: "250m", memory: "512Mi"}
    limits:   {cpu: "1000m", memory: "1Gi"}
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 10
    targetCPUUtilizationPercentage: 70
  livenessProbe:
    httpGet: {path: /health, port: 8000}
    initialDelaySeconds: 10
  readinessProbe:
    httpGet: {path: /ready, port: 8000}

ingestion:
  replicaCount: 1
  image:
    repository: ingestion
  schedule: "*/10 * * * *"   # CronJob every 10 minutes
  resources:
    requests: {cpu: "100m", memory: "256Mi"}

martin:
  replicaCount: 2
  image:
    repository: urbica/martin
    tag: latest
  resources:
    requests: {cpu: "100m", memory: "128Mi"}
    limits:   {cpu: "500m", memory: "256Mi"}
```

### 8.4 Terraform — GCP Infrastructure

```hcl
# infra/terraform/main.tf

terraform {
  required_providers {
    google = { source = "hashicorp/google", version = "~> 5.0" }
  }
  backend "gcs" {
    bucket = "geoweather-tf-state"
    prefix = "terraform/state"
  }
}

# GKE Cluster
resource "google_container_cluster" "primary" {
  name     = "geoweather-cluster"
  location = "asia-southeast1"

  initial_node_count = 1
  remove_default_node_pool = true

  network_policy {
    enabled  = true
    provider = "CALICO"
  }
}

resource "google_container_node_pool" "standard" {
  name       = "standard-pool"
  cluster    = google_container_cluster.primary.name
  location   = google_container_cluster.primary.location
  node_count = 3

  node_config {
    machine_type = "n2-standard-4"  # 4 vCPU, 16GB
    oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    preemptible  = true              # 60-80% cheaper for non-prod
  }

  autoscaling {
    min_node_count = 2
    max_node_count = 10
  }
}

# Cloud SQL — PostgreSQL + PostGIS
resource "google_sql_database_instance" "postgres" {
  name             = "geoweather-postgres"
  database_version = "POSTGRES_16"
  region           = "asia-southeast1"

  settings {
    tier = "db-custom-2-7680"  # 2 vCPU, 7.5GB

    database_flags {
      name  = "max_connections"
      value = "200"
    }

    backup_configuration {
      enabled            = true
      binary_log_enabled = false
      start_time         = "02:00"
    }

    ip_configuration {
      ipv4_enabled = false
      private_network = google_compute_network.vpc.id
    }
  }
}

# Redis — Memorystore
resource "google_redis_instance" "cache" {
  name           = "geoweather-redis"
  tier           = "STANDARD_HA"
  memory_size_gb = 2
  region         = "asia-southeast1"
  redis_version  = "REDIS_7_0"
}
```

---

## 9. Cấu trúc Monorepo

```
geoweather/
│
├── apps/
│   ├── web/                          # Next.js 15 frontend
│   │   ├── app/
│   │   │   ├── (map)/page.tsx        # Main map view
│   │   │   ├── dashboard/page.tsx    # Analytics dashboard
│   │   │   └── layout.tsx
│   │   ├── components/
│   │   │   ├── map/
│   │   │   │   ├── WeatherMap.tsx    # Main Deck.gl + MapLibre
│   │   │   │   ├── LayerControl.tsx  # Switch heatmap/hexagon/scatter
│   │   │   │   ├── WeatherPopup.tsx  # Click popup
│   │   │   │   └── RouteDrawer.tsx   # Draw route for weather check
│   │   │   ├── panels/
│   │   │   │   ├── WeatherDetail.tsx # Side panel, time-series chart
│   │   │   │   └── ChatPanel.tsx     # AI assistant
│   │   │   └── ui/                   # shadcn/ui components
│   │   ├── hooks/
│   │   │   ├── useGlobalWeather.ts   # TanStack Query, 10min refetch
│   │   │   ├── useWeatherWS.ts       # WebSocket hook
│   │   │   └── useRouteWeather.ts    # Route weather API
│   │   ├── store/
│   │   │   └── weather.ts            # Zustand store
│   │   └── lib/
│   │       ├── color-scales.ts       # Temperature → color mapping
│   │       └── weather-codes.ts      # WMO weather code → description
│   │
│   └── api/                          # FastAPI backend
│       ├── main.py
│       ├── routers/
│       │   ├── weather.py
│       │   ├── locations.py
│       │   ├── tiles.py
│       │   ├── websocket.py
│       │   ├── chat.py
│       │   └── graphql_router.py
│       ├── core/
│       │   ├── database.py           # SQLAlchemy async engine
│       │   ├── redis.py              # aioredis pool
│       │   ├── telemetry.py          # OpenTelemetry setup
│       │   └── config.py             # Pydantic Settings
│       ├── models/                   # SQLAlchemy ORM + GeoAlchemy2
│       ├── schemas/                  # Pydantic v2 schemas
│       └── tools/                    # Claude tool definitions
│
├── services/
│   ├── ingestion/                    # Weather data poller
│   │   ├── main.py                   # APScheduler entry point
│   │   ├── weather_client.py         # Open-Meteo async client
│   │   ├── city_loader.py            # GeoNames city dataset
│   │   └── producer.py               # Kafka Avro producer
│   │
│   └── streaming/                    # Flink jobs
│       ├── jobs/
│       │   ├── enrich_job.py         # Add H3 index
│       │   ├── aggregate_job.sql     # Flink SQL windowed agg
│       │   └── anomaly_job.py        # Z-score anomaly detection
│       └── schemas/
│           └── weather_observation.avsc
│
├── infra/
│   ├── docker/
│   │   ├── init-db.sql               # PostGIS setup, extensions
│   │   └── nginx.conf                # Nginx reverse proxy
│   ├── k8s/
│   │   └── geoweather/               # Helm chart
│   │       ├── Chart.yaml
│   │       ├── values.yaml
│   │       └── templates/
│   └── terraform/
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
│
├── .github/
│   └── workflows/
│       ├── ci.yml                    # Test + lint + build
│       ├── cd-staging.yml            # Deploy to staging on PR merge
│       └── cd-production.yml         # Deploy to prod on release tag
│
├── docker-compose.yml
├── docker-compose.override.yml       # Local dev overrides
├── pyproject.toml                    # Python workspace (uv)
├── package.json                      # Node workspace (pnpm)
├── turbo.json                        # Turborepo build cache
└── README.md
```

---

## 10. Database Design

### PostGIS — Spatial Master Data

```sql
-- Extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS h3;           -- pg_h3 extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Cities (loaded from GeoNames)
CREATE TABLE cities (
    geoname_id      INTEGER PRIMARY KEY,
    city_name       VARCHAR(200) NOT NULL,
    ascii_name      VARCHAR(200),
    country_code    CHAR(2) NOT NULL,
    admin1_code     VARCHAR(20),
    admin2_code     VARCHAR(80),
    population      INTEGER DEFAULT 0,
    timezone        VARCHAR(40),
    geom            GEOMETRY(POINT, 4326) NOT NULL,
    h3_r4           TEXT GENERATED ALWAYS AS (h3_lat_lng_to_cell(ST_Y(geom), ST_X(geom), 4)::text) STORED,
    h3_r7           TEXT GENERATED ALWAYS AS (h3_lat_lng_to_cell(ST_Y(geom), ST_X(geom), 7)::text) STORED,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX cities_geom_gist   ON cities USING GIST(geom);
CREATE INDEX cities_h3_r4_idx   ON cities(h3_r4);
CREATE INDEX cities_country_idx ON cities(country_code);

-- Country/region boundaries (loaded from GADM)
CREATE TABLE regions (
    id           SERIAL PRIMARY KEY,
    region_code  VARCHAR(10) UNIQUE NOT NULL,
    region_name  VARCHAR(200) NOT NULL,
    country_code CHAR(2),
    level        INT,  -- 0=country, 1=state, 2=district
    geom         GEOMETRY(MULTIPOLYGON, 4326) NOT NULL,
    bbox         GEOMETRY(POLYGON, 4326) GENERATED ALWAYS AS (ST_Envelope(geom)) STORED
);

CREATE INDEX regions_geom_gist ON regions USING GIST(geom);

-- Latest weather (fast lookup, updated in-place)
CREATE TABLE weather_current (
    location_id     INTEGER PRIMARY KEY REFERENCES cities(geoname_id),
    temperature     REAL,
    feels_like      REAL,
    humidity        SMALLINT,
    wind_speed      REAL,
    wind_direction  SMALLINT,
    precipitation   REAL,
    weather_code    SMALLINT,
    pressure        REAL,
    visibility      INTEGER,
    uv_index        REAL,
    cloud_cover     SMALLINT,
    updated_at      TIMESTAMPTZ NOT NULL
);

CREATE INDEX weather_current_updated_idx ON weather_current(updated_at);
```

### TimescaleDB — Time-Series Observations

```sql
-- Raw observations hypertable
CREATE TABLE weather_observations (
    observation_id  UUID DEFAULT gen_random_uuid(),
    location_id     INTEGER NOT NULL,
    temperature     REAL,
    feels_like      REAL,
    humidity        SMALLINT,
    wind_speed      REAL,
    wind_direction  SMALLINT,
    precipitation   REAL,
    weather_code    SMALLINT,
    pressure        REAL,
    visibility      INTEGER,
    uv_index        REAL,
    cloud_cover     SMALLINT,
    observed_at     TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (location_id, observed_at)
);

SELECT create_hypertable('weather_observations', 'observed_at',
    partitioning_column => 'location_id',
    number_partitions   => 16,
    chunk_time_interval => INTERVAL '1 day');

-- Flink aggregate output
CREATE TABLE weather_hourly_agg (
    h3_index_r4       TEXT NOT NULL,
    window_start      TIMESTAMPTZ NOT NULL,
    window_end        TIMESTAMPTZ NOT NULL,
    avg_temperature   REAL,
    max_wind_speed    REAL,
    total_precip      REAL,
    avg_humidity      REAL,
    observation_count INTEGER,
    PRIMARY KEY (h3_index_r4, window_start)
);

SELECT create_hypertable('weather_hourly_agg', 'window_start',
    chunk_time_interval => INTERVAL '7 days');

-- Useful query: temperature trend for a city over last 7 days
SELECT
    time_bucket('1 hour', observed_at) AS hour,
    AVG(temperature)  AS avg_temp,
    MIN(temperature)  AS min_temp,
    MAX(temperature)  AS max_temp
FROM weather_observations
WHERE location_id = 1566083  -- Ho Chi Minh City
  AND observed_at > NOW() - INTERVAL '7 days'
GROUP BY hour
ORDER BY hour;
```

---

## 11. CI/CD Pipeline

### GitHub Actions — CI (Test + Lint + Build)

```yaml
# .github/workflows/ci.yml
name: CI

on:
  pull_request:
    branches: [main, develop]
  push:
    branches: [main]

jobs:
  test-api:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgis/postgis:16-3.4
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_DB: geoweather_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
      redis:
        image: redis:7-alpine
        options: --health-cmd "redis-cli ping"

    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v3
        with:
          version: "latest"

      - name: Install dependencies
        working-directory: apps/api
        run: uv sync --frozen

      - name: Lint (ruff)
        run: uv run ruff check apps/api services/

      - name: Type check (mypy)
        run: uv run mypy apps/api --ignore-missing-imports

      - name: Run tests
        working-directory: apps/api
        run: uv run pytest tests/ -v --cov=. --cov-report=xml
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:test@localhost/geoweather_test
          REDIS_URL: redis://localhost:6379/0

      - uses: codecov/codecov-action@v4

  test-web:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with: { node-version: "22", cache: "pnpm" }
      - run: pnpm install --frozen-lockfile
      - run: pnpm --filter web run type-check
      - run: pnpm --filter web run test
      - run: pnpm --filter web run build

  build-images:
    needs: [test-api, test-web]
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    permissions:
      contents: read
      packages: write

    strategy:
      matrix:
        service: [api, web, ingestion]

    steps:
      - uses: actions/checkout@v4

      - uses: docker/setup-buildx-action@v3

      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - uses: docker/build-push-action@v6
        with:
          context: apps/${{ matrix.service }}
          target: prod
          push: true
          tags: ghcr.io/${{ github.repository }}/${{ matrix.service }}:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          platforms: linux/amd64,linux/arm64
```

### GitHub Actions — CD (Deploy Staging)

```yaml
# .github/workflows/cd-staging.yml
name: Deploy Staging

on:
  push:
    branches: [main]

environment:
  name: staging
  url: https://staging.geoweather.app

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}

      - uses: google-github-actions/get-gke-credentials@v2
        with:
          cluster_name: geoweather-cluster
          location: asia-southeast1

      - name: Deploy with Helm
        run: |
          helm upgrade --install geoweather infra/k8s/geoweather \
            --namespace staging \
            --create-namespace \
            --set global.imageTag=${{ github.sha }} \
            --set api.replicaCount=2 \
            --wait \
            --timeout 5m

      - name: Run smoke tests
        run: |
          API_URL=https://api-staging.geoweather.app
          curl -f "$API_URL/health"
          curl -f "$API_URL/api/v1/weather/10.7769/106.7009"

      - name: Notify Slack
        uses: slackapi/slack-github-action@v2
        with:
          payload: |
            {"text": "✅ Staging deploy successful: ${{ github.sha }}"}
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK }}
```

---

## 12. Monitoring & Observability

### Prometheus — Custom Metrics

```python
# apps/api/core/metrics.py
from prometheus_client import Counter, Histogram, Gauge

weather_requests_total = Counter(
    "geoweather_requests_total",
    "Total weather API requests",
    labelnames=["endpoint", "method", "status_code"],
)

weather_request_duration = Histogram(
    "geoweather_request_duration_seconds",
    "Request duration in seconds",
    labelnames=["endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

kafka_messages_produced = Counter(
    "geoweather_kafka_produced_total",
    "Total Kafka messages produced",
    labelnames=["topic"],
)

active_websocket_connections = Gauge(
    "geoweather_websocket_connections",
    "Number of active WebSocket connections",
)

spatial_query_duration = Histogram(
    "geoweather_spatial_query_seconds",
    "PostGIS spatial query duration",
    labelnames=["query_type"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5],
)
```

### Grafana Dashboard Panels

```
Dashboard: GeoWeather Operations

Row 1 — API Health
├── Request rate (req/s)         [time series]
├── Error rate (4xx, 5xx %)      [stat]
├── P50 / P95 / P99 latency      [time series]
└── Active WebSocket connections [gauge]

Row 2 — Data Pipeline
├── Kafka consumer lag           [time series, per topic]
├── Flink job status             [table]
├── Messages processed/min       [time series]
└── Last ingestion timestamp     [stat]

Row 3 — Spatial Performance
├── Spatial query duration P95   [time series]
├── PostGIS query types          [bar chart]
├── Redis cache hit rate         [gauge]
└── TimescaleDB chunk count      [stat]

Row 4 — Business Metrics
├── Cities with fresh data (< 30min) [gauge]
├── Anomalies detected today     [stat]
├── Coverage map (heatmap)       [geomap panel]
└── Top 10 most queried cities   [table]
```

---

## 13. Prompts cho AI Agent

Khi dùng AI coding assistant (Claude, Cursor, Copilot) để build project này, dùng các prompt sau:

```
# Tạo FastAPI endpoint
"Tạo một FastAPI async endpoint GET /api/v1/weather/region/{h3_index} 
nhận H3 index string, query TimescaleDB lấy aggregated stats trong 
24h qua, trả về Pydantic schema WeatherRegionStats. Dùng SQLAlchemy 2.0 
async session, có error handling và logging."

# Tạo Flink job
"Viết PyFlink streaming job đọc từ Kafka topic 'weather.observations.raw', 
deserialize Avro với schema weather_observation.avsc, thêm H3 index r7 
dùng h3-py library, rồi sink vào Kafka topic 'weather.observations.enriched'. 
Parallelism 4, checkpointing mỗi 30 giây, state backend RocksDB."

# Tạo React component
"Tạo React hook useWeatherWebSocket(h3Index: string) dùng native WebSocket 
API, connect tới ws://localhost:8000/ws/weather/{h3Index}, tự reconnect 
khi disconnect với exponential backoff, trả về {data, status, error}. 
Dùng TypeScript, cleanup khi unmount."

# Tạo PostGIS query
"Viết SQL query dùng PostGIS lấy tất cả cities trong bán kính 500km 
từ điểm (lat=10.77, lon=106.70), kèm current weather, sort theo distance, 
limit 100. Dùng ST_DWithin với geography type để tính đúng khoảng cách 
trên ellipsoid, có spatial index hint."
```

---

## 14. CV Talking Points

### Mô tả project cho CV/LinkedIn

> **GeoWeather Intelligence Platform** — Personal Project
> 
> Built an end-to-end real-time weather analytics platform combining GIS visualization with streaming data engineering. Ingests weather data for 47,000+ cities worldwide via a Kafka-based pipeline, processes with Apache Flink stream processing (windowed aggregations, anomaly detection), and visualizes on an interactive 3D map using MapLibre GL + Deck.gl with Uber H3 hexagon spatial indexing. Self-hosted vector tile server (Martin/PostGIS) eliminates third-party tile dependencies. Integrated AI chatbot with Claude API for natural language weather queries. Full DevOps: Docker multi-stage builds, Kubernetes (Helm), Terraform IaC, and GitHub Actions CI/CD with automated testing and staging deploys.

### Câu hỏi phỏng vấn và trả lời

**Q: "Tại sao dùng Kafka thay vì chỉ poll API và insert thẳng DB?"**
> A: Kafka decouples producers và consumers, cho phép replay data khi một consumer bị lỗi, cho phép nhiều consumers độc lập (Flink, WebSocket service, analytics) đọc cùng stream mà không ảnh hưởng nhau. Nếu Flink chết, khi restart nó có thể đọc lại từ committed offset, không mất data. Schema Registry đảm bảo backward compatibility khi schema thay đổi.

**Q: "PostGIS vs ElasticSearch cho spatial search?"**
> A: PostGIS tốt hơn khi: data ở PostgreSQL, cần join spatial với relational data (cities + weather), cần complex SQL aggregations. ES tốt hơn khi: cần full-text search kết hợp geo, cần sub-10ms response cho read-heavy workload, scale ra nhiều nodes. Với dự án này, PostGIS đủ vì ta query với spatial index (KNN với `<->` operator) cho millisecond response, và cần join nhiều tables.

**Q: "TimescaleDB vs InfluxDB cho time-series?"**
> A: Chọn TimescaleDB vì: vẫn là PostgreSQL (cùng connection pool, cùng ORM, cùng backup strategy), hỗ trợ SQL đầy đủ (JOIN với spatial data từ PostGIS), continuous aggregates tự động recompute. InfluxDB có query language riêng (Flux/InfluxQL), không thể JOIN với relational data.

**Q: "H3 hexagon dùng để làm gì, tại sao không dùng lat/lon trực tiếp?"**
> A: H3 spatial indexing cho phép: (1) nhóm nhiều cities trong cùng ô hexagon để aggregate weather (ít renders hơn khi zoom out), (2) query "tất cả cells trong vùng X" bằng bitwise operation thay vì polygon intersection, (3) multi-resolution — cùng data point có index ở resolution 4 (vùng rộng) và resolution 7 (chi tiết), cho phép zoom-based rendering. Deck.gl HexagonLayer cũng render H3 grid cực nhanh trên GPU.

**Q: "Làm thế nào đảm bảo real-time data là 'real-time'?"**
> A: Multi-level pipeline: Kafka consumer lag monitored (alert nếu lag > 1000 messages), Flink watermark cho phép xử lý out-of-order events trong 1-minute window, Redis pub/sub cho WebSocket push có sub-100ms latency, browser nhận update qua WebSocket trong ~2s sau khi weather poller produce vào Kafka.

---

## Checklist Hoàn thành

### Phase 1 — Core
- [ ] PostGIS setup + load GeoNames cities data
- [ ] FastAPI với spatial weather endpoints
- [ ] MapLibre GL map với weather scatter layer
- [ ] Cơ bản CI với GitHub Actions

### Phase 2 — Streaming
- [ ] Kafka + Schema Registry setup
- [ ] Weather ingestion service (APScheduler + producer)
- [ ] Flink enrich job (H3 index)
- [ ] Flink aggregate job (Flink SQL windowed)
- [ ] WebSocket real-time push
- [ ] TimescaleDB hypertables + continuous aggregates

### Phase 3 — Advanced
- [ ] Deck.gl HexagonLayer + HeatmapLayer
- [ ] Route weather API (PostGIS ST_LineInterpolatePoint)
- [ ] AI chatbot (Claude API streaming + tool use)
- [ ] Anomaly detection (Flink z-score)
- [ ] Martin tile server cho self-hosted vector tiles

### Phase 4 — Production
- [ ] Docker multi-stage builds (dev + prod targets)
- [ ] Kubernetes Helm chart
- [ ] Terraform GCP infra
- [ ] Full CI/CD pipeline (test → build → staging → prod)
- [ ] Prometheus + Grafana monitoring
- [ ] Loki + Tempo observability

---

*Document version: 1.0 | Last updated: 2026-06-05*
*Stack versions should be verified against latest releases before implementation.*
