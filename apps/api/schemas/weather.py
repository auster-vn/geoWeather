from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List

class WeatherResponse(BaseModel):
    geoname_id: int
    city_name: str
    country_code: str
    distance_meters: float
    temperature: Optional[float] = None
    feels_like: Optional[float] = None
    humidity: Optional[int] = None
    wind_speed: Optional[float] = None
    wind_direction: Optional[int] = None
    precipitation: Optional[float] = None
    weather_code: Optional[int] = None
    observed_at: Optional[datetime] = None
    h3_r4: Optional[str] = None
    h3_r7: Optional[str] = None

    class Config:
        from_attributes = True

class WeatherRegionStats(BaseModel):
    h3_index_r4: str
    window_start: datetime
    window_end: datetime
    avg_temperature: float
    max_wind_speed: float
    total_precip: float
    avg_humidity: float
    observation_count: int

class RouteWeatherPoint(BaseModel):
    idx: int
    latitude: float
    longitude: float
    temperature: Optional[float] = None
    weather_code: Optional[int] = None
    wind_speed: Optional[float] = None
    precipitation: Optional[float] = None

class CitySearchResponse(BaseModel):
    geoname_id: int
    city_name: str
    country_code: str
    population: int
    timezone: str
    latitude: float
    longitude: float
