# 🌍 GeoWeather Intelligence Platform

**GeoWeather** is an End-to-End Real-Time GIS & Weather Analytics System. It visualizes live weather data on an interactive WebGL map, supports real-time streaming, and features a dual AI-powered conversational assistant (Local NLP & Google Gemini) for advanced natural language location queries.

## 🚀 Features
- **Real-Time Map Visualization**: Next.js 16 WebGL interactive map using MapLibre GL JS and Deck.gl.
- **Dual AI Assistant**: Toggle between **Gemini 2.5 Flash** for comprehensive answers and a **Local NLP Model (FlashText/Underthesea)** for ultra-fast, offline natural language location resolution.
- **GIS Backend**: PostgreSQL with PostGIS for spatial data storage (over 53k+ administrative boundaries).
- **Time-Series Data**: TimescaleDB for continuous ingestion of weather metrics.
- **Streaming Pipeline**: Apache Kafka + Schema Registry + Python processor for real-time data ingestion.
- **Modern Infrastructure**: Fully containerized with Docker, automated via CI/CD (GitHub Actions).

## 🛠️ Tech Stack
- **Frontend**: Next.js 16 (React 19), MapLibre GL, Deck.gl, Tailwind CSS.
- **Backend API**: Python 3.11, FastAPI, SQLAlchemy, Underthesea (NLP), FlashText, Google GenAI SDK.
- **Data Engineering**: Apache Kafka, Confluent Schema Registry, Redis.
- **Databases**: PostgreSQL (PostGIS), TimescaleDB.
- **Deployment**: Docker, Docker Compose, GitHub Actions.

## 📦 Project Structure
This is a monorepo utilizing TurboRepo for fast local development:
```
├── apps
│   ├── web          # Next.js 16 Frontend
│   ├── api          # FastAPI Python Backend
│   └── gateway      # (Optional) Go API Gateway
├── packages         # Shared code/configs
├── services         # Python Streaming & Ingestion (Kafka Producers/Consumers)
├── docker-compose.yml
└── turbo.json
```

## ⚙️ Getting Started

### 1. Prerequisites
- Docker and Docker Compose (v2.x)
- Node.js >= 20.x

### 2. Environment Setup
Copy the example environment file and fill in your secrets (e.g. Gemini API Key):
```bash
cp .env.example .env
```
Open `.env` and set `GEMINI_API_KEY` to your actual API key if you plan to use the Gemini features.

### 3. Launching the Platform
Run the entire stack via Docker Compose:
```bash
docker-compose up -d --build
```
This will start:
- 🌐 **Web App**: `http://localhost:3001`
- ⚙️ **API Server**: `http://localhost:8000`
- 🗄️ **Databases**: PostgreSQL/PostGIS (5432), TimescaleDB (5433), Redis (6379)
- 📡 **Streaming**: Kafka (9092), Schema Registry (8081)

### 4. Local Development (Optional)
If you wish to run the Next.js frontend outside of Docker:
```bash
cd apps/web
npm install --legacy-peer-deps
npm run dev
```

## 🧠 AI NLP Features
The chat interface allows querying weather by natural language:
- **"Thời tiết Hồ Chí Minh chiều nay"** -> The NLP engine (via FlashText loaded with 63 Vietnamese provinces) extracts the location "Hồ Chí Minh", resolves the PostGIS coordinates, and fetches real-time data.
- **Dropdown Toggle**: Users can switch seamlessly between "Local AI" (Fast, Offline regex/keyword processing) and "Gemini Flash" (Cloud-based, comprehensive answers).

## 📝 CI/CD
This project uses **GitHub Actions** for continuous integration.
- Automatically builds the Next.js web application.
- Tests Python dependencies and environments on every push to `main` and `feature/*` branches.

## 📄 License
MIT License
