<div align="center">
  <img src="apps/web/public/globe.svg" width="100" height="100" alt="GeoWeather Logo" />
  <h1>GeoWeather Intelligence Platform</h1>
  <p>
    <strong>A high-performance, real-time spatial weather analytics platform built with Rust, Go, FastAPI, and Next.js.</strong>
  </p>

  [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
  [![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
  [![Next.js](https://img.shields.io/badge/Next.js-black?style=flat&logo=next.js&logoColor=white)](https://nextjs.org/)
  [![Rust](https://img.shields.io/badge/Rust-000000?style=flat&logo=rust&logoColor=white)](https://www.rust-lang.org/)
  [![Uber H3](https://img.shields.io/badge/Uber_H3-GeoSpatial-blue?style=flat)](https://h3geo.org/)
</div>

---

<div align="center">
  <img src="screenshots/dashboard.png" alt="GeoWeather Platform Dashboard" width="100%" />
</div>

## 📌 Overview

**GeoWeather Intelligence Platform** is an enterprise-grade geospatial weather monitoring and analytics solution. It aggregates real-time meteorological data across vast geographic areas using **Uber's H3 Hexagonal Grid System**, processes streaming observations with **Bytewax/Kafka**, and visualizes massive datasets via a highly optimized **Next.js (React) / MapLibre** frontend.

Additionally, the platform features a deeply integrated **AI Weather Assistant** powered by **Gemini 2.5 Flash**, capable of understanding natural language queries, executing geospatial function calling, and providing Voice-to-Text meteorological analysis natively in the browser.

## 🚀 Key Features

- **Real-time Geospatial Mapping:** Millions of data points clustered and rendered seamlessly using H3 hierarchical geospatial indexing and MapLibre GL.
- **AI-Powered Weather Assistant:** Context-aware chatbot supporting Native Voice Queries (Web Speech API / AudioContext) with intelligent data extraction.
- **Streaming Telemetry Analytics:** High-throughput event ingestion gateway (Go) and stream processing (Bytewax) for anomaly detection.
- **Rust Compute Core:** High-performance computational engine for crunching complex geospatial polygons and real-time aggregations.
- **Microservices Architecture:** Strictly typed, fully asynchronous microservices communicating via Redis Pub/Sub and Apache Kafka.

## 🏗️ Architecture & Technology Stack

The platform is designed around a modern **Monorepo** structure managed by **Turborepo** and **UV**, ensuring blazing fast dependency resolution and build times.

| Component | Technology | Description |
| :--- | :--- | :--- |
| **Frontend WebApp** | Next.js 15, React 19, MapLibre | High-performance GIS dashboard with WebSocket real-time updates. |
| **Core API Backend** | FastAPI, Python 3.12, SQLAlchemy | Asynchronous API gateway handling AI orchestration and DB queries. |
| **Ingestion Service** | Bytewax, Apache Kafka | Distributed stream processing for weather telemetry. |
| **Geospatial Core** | Rust, PyO3 | Low-level optimization for H3 hexagonal grid aggregations. |
| **Edge Gateway** | Go (Golang) | Ultra-low latency edge server for proxying IoT weather devices. |
| **Database Layer** | PostgreSQL, PostGIS, TimescaleDB | Specialized time-series and spatial data storage. |

## 📂 Repository Structure

```text
geoWeather/
├── apps/
│   ├── web/                # Next.js 15 Frontend GIS Dashboard
│   ├── api/                # FastAPI Backend & AI Orchestrator
│   └── gateway/            # Go Edge Gateway for device ingestion
├── services/
│   ├── ingestion/          # Bytewax / Kafka Streaming Analytics
│   └── ...
├── packages/
│   ├── core-rs/            # Rust compute engine (PyO3)
│   └── shared-types/       # Shared TypeScript / Python schemas
├── infra/                  # Docker Compose, PostgreSQL init scripts
└── README.md               # You are here
```

## 🛠️ Getting Started

### Prerequisites
- Docker & Docker Compose
- Node.js >= 20.0
- Python >= 3.12 & [UV Package Manager](https://github.com/astral-sh/uv)
- Rust Toolchain (Optional, for core modifications)

### 1. Infrastructure Setup

Start the background services (PostgreSQL + PostGIS, Redis, Kafka) using Docker Compose:

```bash
docker-compose up -d
```

### 2. Backend API Initialization

The backend uses `uv` for lightning-fast environment setup.

```bash
cd apps/api
uv sync
uv run uvicorn main:app --reload --port 8000
```

### 3. Frontend Web Dashboard

Launch the Next.js application:

```bash
cd apps/web
npm install
npm run dev
```

Visit `http://localhost:3000` to access the interactive map and AI Assistant.

## 🤝 Contributing
Contributions, issues, and feature requests are welcome! Feel free to check the [issues page](https://github.com/auster-vn/geoWeather/issues).

## 📄 License
This project is licensed under the MIT License - see the LICENSE file for details.
