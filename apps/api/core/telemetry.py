import time
from fastapi import FastAPI, Request
from prometheus_client import Counter, Histogram, Gauge, make_asgi_app

# Prometheus metrics definition
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

def setup_telemetry(app: FastAPI):
    # Add metrics middleware
    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        start_time = time.time()
        
        # Avoid tracking metrics endpoint itself
        if request.url.path == "/metrics":
            return await call_next(request)

        response = await call_next(request)
        
        duration = time.time() - start_time
        endpoint = request.url.path
        method = request.method
        status_code = str(response.status_code)

        weather_requests_total.labels(endpoint=endpoint, method=method, status_code=status_code).inc()
        weather_request_duration.labels(endpoint=endpoint).observe(duration)
        
        return response

    # Mount Prometheus metrics endpoint
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)
