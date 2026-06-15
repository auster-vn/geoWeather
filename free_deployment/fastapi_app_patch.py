# CẤU HÌNH TÍCH HỢP ENDPOINT SYNC VÀO FASTAPI (KAFKA-FREE)
# File này mô tả cách sửa đổi FastAPI router để sử dụng direct_ingest thay vì Kafka.

"""
Ý tưởng:
Thay vì sửa đổi trực tiếp vào mã nguồn hiện tại của bạn (giữ nguyên tính đóng băng của thư mục gốc theo yêu cầu),
dưới đây là hướng dẫn và mã nguồn sửa đổi cho file `apps/api/routers/weather.py`.

Khi bạn deploy lên môi trường Production (như Render hay Koyeb), bạn chỉ cần thay đổi hàm `run_sync` trong
`apps/api/routers/weather.py` để trỏ vào `run_ingestion` của `direct_ingest.py`.

Chi tiết thay đổi:
"""

# --- TRƯỚC KHI SỬA (Mặc định sử dụng Kafka): ---
"""
@router.post("/sync")
async def trigger_sync(background_tasks: BackgroundTasks):
    if sync_lock.locked():
        raise HTTPException(status_code=409, detail="Sync is already in progress.")
        
    async def run_sync():
        async with sync_lock:
            try:
                logger.info("Starting background sync ingestion...")
                from services.ingestion.producer import run_once
                await run_once()
                logger.info("Background sync ingestion completed successfully.")
            except Exception as e:
                logger.error(f"Error during background sync ingestion: {e}")
                
    background_tasks.add_task(run_sync)
    return {"status": "success", "message": "Sync started in background."}
"""

# --- SAU KHI SỬA (Sử dụng Direct Ingest không cần Kafka): ---

import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
import asyncio

logger = logging.getLogger("weather_router_patch")
router = APIRouter()
sync_lock = asyncio.Lock()

@router.post("/sync")
async def trigger_sync(background_tasks: BackgroundTasks):
    """
    Trigger the weather data ingestion cycle in the background.
    Bypasses Kafka and writes directly to PostgreSQL & Redis.
    """
    if sync_lock.locked():
        raise HTTPException(status_code=409, detail="Sync is already in progress.")
        
    async def run_sync():
        async with sync_lock:
            try:
                logger.info("Starting background direct sync ingestion...")
                # Import script đồng bộ trực tiếp đã tối ưu hóa
                from free_deployment.direct_ingest import run_ingestion
                await run_ingestion()
                logger.info("Background direct sync ingestion completed successfully.")
            except Exception as e:
                logger.error(f"Error during background direct sync ingestion: {e}")
                
    background_tasks.add_task(run_sync)
    return {"status": "success", "message": "Direct Sync started in background."}

# ==============================================================================
# PHƯƠNG ÁN 2: THIẾT LẬP CRON JOB BÊN NGOÀI (Khuyến khích cho Serverless)
# ==============================================================================
"""
Nếu deploy FastAPI lên các nền tảng Serverless hay Container tự tắt (như Render free tier ngủ sau 15p không hoạt động),
việc chạy Background Task trong FastAPI có thể bị dừng giữa chừng.

Vì vậy, cách tốt nhất là chạy script `direct_ingest.py` như một Cron Job độc lập, hoặc cấu hình một dịch vụ gọi
HTTP POST định kỳ đến endpoint `/api/v1/weather/sync` của API.

Ví dụ sử dụng GitHub Actions làm Cron Job miễn phí gọi API Sync mỗi 10 phút:

Tệp: .github/workflows/weather_sync.yml
----------------------------------------
name: GeoWeather Data Sync Cron

on:
  schedule:
    - cron: '*/10 * * * *' # Chạy mỗi 10 phút

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger Ingestion API
        run: |
          curl -X POST "https://your-geoweather-api.onrender.com/api/v1/weather/sync" \
               -H "accept: application/json" \
               -d ""
----------------------------------------
"""
