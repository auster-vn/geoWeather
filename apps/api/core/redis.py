import logging
import redis.asyncio as aioredis
from .config import settings

logger = logging.getLogger(__name__)

redis_client: aioredis.Redis = None

async def init_redis():
    global redis_client
    logger.info("Initializing Redis client...")
    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    # Ping to test connection
    await redis_client.ping()
    logger.info("Redis initialized.")

async def get_redis() -> aioredis.Redis:
    if redis_client is None:
        raise RuntimeError("Redis client is not initialized. Call init_redis first.")
    return redis_client

async def close_redis():
    global redis_client
    if redis_client:
        logger.info("Closing Redis client...")
        await redis_client.close()
