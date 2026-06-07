# GeoWeather Intelligence Platform

GeoWeather is a highly scalable, real-time geospatial weather intelligence platform. It ingests, processes, and visualizes large-scale meteorological data mapped to geospatial indexes, combining high-performance data streaming with natural language AI interfaces.

## 1. Overview and Core Concepts

The platform is designed to provide hyper-local weather insights. Instead of traditional point-based weather tracking, GeoWeather utilizes **Uber's H3 Hexagonal Hierarchical Spatial Index** to map weather data continuously across regions. 

Key capabilities include:
- **Spatial Weather Visualization:** Rendering dynamic, color-coded H3 grid overlays on MapLibre GL based on real-time and historical weather parameters.
- **AI-Powered Natural Language Interface:** Integrating with LLMs (Google Gemini) to allow users to ask complex weather queries (e.g., "Will it rain in District 1 tomorrow?") and receive data-backed responses with location context.
- **High-Throughput Time-Series Storage:** Aggregating continuous streams of weather data into TimescaleDB for efficient historical lookups and forecasting.

## 2. Architecture & Technology Stack

The project adopts a modern microservices architecture housed within a Polyglot Monorepo.

### 2.1 Backend & Compute
- **FastAPI (Python):** Serves as the primary backend for querying weather data and handling the LLM chat orchestration.
- **Rust (PyO3 & Maturin):** A native Rust extension (`packages/core-rs`) is embedded within the Python backend to handle CPU-bound geospatial math and complex grid processing at bare-metal speeds.
- **Go API Gateway:** A high-concurrency Go-based gateway layer to handle request routing and rate limiting.

### 2.2 Streaming & Data Ingestion
- **Kafka & Schema Registry:** Acts as the central nervous system for continuous, high-volume weather data ingestion.
- **Python Ingestion Services:** Asynchronous workers that periodically fetch external meteorological APIs (e.g., Open-Meteo) and publish strictly-typed Avro events to Kafka.
- **Bytewax:** A Python-based stream processing framework to aggregate real-time Kafka streams before persisting them.

### 2.3 Storage & Infrastructure
- **TimescaleDB:** An extension of PostgreSQL optimized for fast ingest and complex queries over time-series data.
- **PostGIS:** Manages geographic objects and spatial queries.
- **Redis:** Serves as a fast, in-memory cache layer for frequent geographic lookups.
- **MinIO:** S3-compatible object storage for static assets.
- **Docker & Docker Compose:** Containerizes the entire infrastructure for local development and deployment.

### 2.4 Frontend
- **Next.js & React:** A responsive web dashboard.
- **MapLibre GL & deck.gl:** Renders the map tiles and the interactive H3 hexagon overlays smoothly on the GPU.
- **Recharts:** Powers the interactive 48-hour forecast and historical time-series charts.

## 3. Monorepo Structure

The repository is managed using **Turborepo** for build orchestration, **UV** for Python workspaces, and **NPM Workspaces** for JavaScript/TypeScript packages.

```text
geoWeather/
├── apps/                 # User-facing applications
│   ├── web/              # Next.js Frontend Dashboard
│   ├── api/              # FastAPI Backend (Python)
│   └── gateway/          # Go API Gateway
├── services/             # Background processing & data ingestion
│   ├── ingestion/        # API data fetchers and Kafka producers
│   └── streaming/        # Bytewax stream processors
├── packages/             # Shared libraries across the monorepo
│   └── core-rs/          # Rust library for fast geospatial calculations
├── infra/                # Infrastructure configurations (K8s, Terraform, Docker SQL)
├── scripts/              # Development scripts, testing, and scratchpads
├── turbo.json            # Turborepo build pipeline configuration
├── package.json          # Node.js workspace definitions
└── pyproject.toml        # UV Python workspace definitions
```

## 4. Getting Started

### Prerequisites
- **Docker** and **Docker Compose**
- **Node.js** (v20+)
- **UV** (Python package manager)
- **Rust toolchain** (cargo/rustc) - for building the core extension

### Running the Infrastructure

Start all required databases and message brokers:
```bash
docker-compose up -d postgres timescaledb redis kafka schema-registry minio
```

### Building the Project

The monorepo uses Turborepo to orchestrate builds. To install Node dependencies and build the entire stack:
```bash
npm install
npx turbo run build
```

To run the API and Web interface locally via Docker:
```bash
docker-compose build api web
docker-compose up -d api web
```

## 5. Development Guidelines

- **Python Services:** Managed via `uv`. The root `pyproject.toml` defines a workspace containing `apps/api` and `services/ingestion`. Use `uv sync` to resolve dependencies.
- **Rust Core:** Any changes made in `packages/core-rs` require a rebuild of the Python bindings using `maturin build --release`.
- **Environment Variables:** Each application directory contains an `.env.example` file detailing required configurations (such as database URLs and GEMINI_API_KEY). Ensure these are replicated to `.env` files locally.

## 6. License

Proprietary. All rights reserved.
