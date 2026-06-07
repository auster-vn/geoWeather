import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:geoweather_local@localhost:5432/geoweather"
    TIMESCALE_URL: str = "postgresql+asyncpg://postgres:geoweather_local@localhost:5433/geoweather_ts"
    REDIS_URL: str = "redis://localhost:6379/0"
    KAFKA_BOOTSTRAP: str = "localhost:9092"
    SCHEMA_REGISTRY_URL: str = "http://localhost:8081"
    ANTHROPIC_API_KEY: str = "mock-key-for-now"
    GEMINI_API_KEY: str = ""
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
