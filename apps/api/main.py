import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from apps.api.core.database import init_db, close_db
from apps.api.core.redis import init_redis, close_redis, get_redis
from apps.api.core.telemetry import setup_telemetry
from apps.api.core.rate_limit import limiter
from apps.api.routers import weather, locations, tiles, websocket, chat

from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend

# Setup logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("api_main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing GeoWeather API services...")
    # Initialize DB (PostgreSQL engines & TimescaleDB hypertables creation)
    await init_db()
    # Initialize Redis
    await init_redis()
    
    # Initialize FastAPI Cache using the redis client
    redis_client = await get_redis()
    FastAPICache.init(RedisBackend(redis_client), prefix="fastapi-cache")
    
    # Start Redis WebSocket pub/sub listener as background task
    listener_task = asyncio.create_task(websocket.redis_listener())
    
    yield
    
    logger.info("Shutting down GeoWeather API services...")
    listener_task.cancel()
    try:
        await listener_task
    except asyncio.CancelledError:
        pass
        
    await close_db()
    await close_redis()

app = FastAPI(
    title="GeoWeather API",
    description="Production-Grade Real-Time GIS & Weather Analytics Platform Backend",
    version="1.0.0",
    lifespan=lifespan
)

# Add Middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Health Check endpoints
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "geoweather-api"}

@app.get("/ready")
async def ready_check():
    return {"status": "ready"}

# Include Routers
app.include_router(weather.router, prefix="/api/v1/weather", tags=["weather"])
app.include_router(locations.router, prefix="/api/v1/locations", tags=["locations"])
app.include_router(tiles.router, prefix="/tiles", tags=["tiles"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"])
app.include_router(websocket.router, prefix="/ws", tags=["websocket"])

# Setup Prometheus metrics
setup_telemetry(app)
