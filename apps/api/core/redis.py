import logging
import asyncio
import redis.asyncio as aioredis
from .config import settings

logger = logging.getLogger(__name__)

redis_client: aioredis.Redis = None

async def init_redis():
    global redis_client
    logger.info("Initializing Redis client...")
    try:
        redis_client = aioredis.from_url(
            settings.REDIS_URL, 
            decode_responses=True,
            socket_timeout=3.0,
            socket_connect_timeout=3.0
        )
        # Ping to test connection
        await asyncio.wait_for(redis_client.ping(), timeout=3.0)
        logger.info("Redis initialized.")
    except Exception as e:
        logger.error(f"Redis initialization failed: {e}. Running in degraded (no-cache) mode.")
        # Create a dummy client or set to None
        redis_client = None

async def get_redis() -> aioredis.Redis:
    if redis_client is None:
        raise RuntimeError("Redis client is not initialized. Call init_redis first.")
    return redis_client

async def close_redis():
    global redis_client
    if redis_client:
        logger.info("Closing Redis client...")
        await redis_client.close()
