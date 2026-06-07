# 🌟 GeoWeather Intelligence Platform

**Role:** Senior AI / Data Engineer  
**Type:** Real-Time GIS & Weather Analytics System  
**Link/Demo:** [Insert Link Here]

## 📝 Overview
**GeoWeather** is an end-to-end, production-grade GIS (Geographic Information System) platform that visualizes real-time weather data on an interactive 3D WebGL map. The project demonstrates a complete data lifecycle from ingestion and streaming to spatial analytics and AI-powered natural language queries.

This platform allows users to query complex weather information using natural language (e.g., *"Thời tiết Hồ Chí Minh chiều nay"*), resolving location entities instantly and visualizing the data spatially on the map.

## 🛠️ Technologies & Skills Showcased

### 1. Data Engineering & Streaming
- **Apache Kafka & Confluent Schema Registry**: Designed a robust event-streaming architecture to ingest continuous weather updates.
- **Python (FastAPI & Asyncio)**: Built a high-performance backend capable of non-blocking data ingestion and stream processing.
- **Redis**: Implemented caching layers for rapid data retrieval and reduced database load.

### 2. Spatial Analytics & Database (GIS)
- **PostgreSQL + PostGIS**: Stored and indexed over 53,000 administrative boundaries (provinces, districts, communes) in Vietnam for rapid geospatial queries (`ST_Distance`, `ST_Intersects`).
- **TimescaleDB**: Engineered a time-series database optimized for high-ingest rates of continuous weather metrics.

### 3. AI & Natural Language Processing (NLP)
- **Dual AI Assistant Architecture**:
  - **Local NLP Pipeline**: Implemented a blazing-fast, offline entity extraction engine using **FlashText** (O(1) complexity matching against 53k+ locations) and **Underthesea** (Vietnamese NER).
  - **Cloud LLM Integration**: Integrated **Google Gemini 2.5 Flash** for deep, context-aware meteorological insights and comprehensive user assistance.

### 4. Frontend & Visualization
- **Next.js 16 (React 19)**: Built a responsive, modern web application utilizing Server Components and the new App Router.
- **MapLibre GL & Deck.gl**: Rendered high-performance, interactive 3D map layers directly in the browser via WebGL.

### 5. DevOps & Infrastructure
- **Docker & Docker Compose**: Containerized the entire microservices stack (API, Web, Databases, Kafka) ensuring consistent environments across development and production.
- **CI/CD (GitHub Actions)**: Automated linting, testing, and build checks for both Node.js and Python ecosystems to maintain code quality.

## 💡 Key Achievements
- **Ultra-Fast Entity Resolution**: Solved the bottleneck of parsing Vietnamese location names by pivoting from heavy NER models to an optimized `FlashText` dictionary-based approach, achieving instant local inference.
- **Seamless System Integration**: Successfully unified streaming data (Kafka), spatial data (PostGIS), time-series data (TimescaleDB), and LLMs into a single cohesive platform.
- **Modern Monorepo Structure**: Organized the codebase using TurboRepo to neatly separate the frontend (`apps/web`), backend (`apps/api`), and ingestion scripts, making it highly scalable and maintainable.
