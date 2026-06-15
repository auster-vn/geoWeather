# CẨM NANG TRIỂN KHAI GEOWEATHER HOÀN TOÀN MIỄN PHÍ (0 USD / THÁNG)

Tài liệu này hướng dẫn bạn cách tối ưu hóa và đưa hệ thống **GeoWeather** từ kiến trúc 13 microservices chạy Docker cục bộ lên môi trường Cloud hoàn toàn miễn phí mà không làm giảm hiệu năng cốt lõi hay tính năng bản đồ và AI.

---

## 📊 So Sánh Kiến Trúc: Local Docker vs. Production Free Tier

| Thành phần | Môi trường Local (Docker) | Giải pháp Production Free Tier (0 USD) |
| :--- | :--- | :--- |
| **Frontend UI** | Docker Container (Next.js) | **Vercel** (Free Tier - Tốc độ cao, băng thông rộng) |
| **Backend API** | Docker Container (FastAPI) | **Render** hoặc **Koyeb** (Free Tier cho Python web service) |
| **Cơ sở dữ liệu** | PostgreSQL + PostGIS | **Supabase** (Free Tier - Cấp PostgreSQL + PostGIS đám mây) |
| **Thời gian thực** | TimescaleDB | **Supabase Postgres** (Lưu trữ lịch sử dưới dạng bảng thường) |
| **Caching / PubSub**| Redis (Docker) | **Upstash Redis** (Serverless Redis Free - Giao thức chuẩn) |
| **Data Ingestion** | Kafka + Schema Registry + Flink | Script rút gọn **`direct_ingest.py`** chạy qua Cron Job / Sync API |
| **Martin Tiles** | Martin Vector Tiles Server | Bỏ qua (Web UI sử dụng Deck.gl trực tiếp trên CartoDB base map) |
| **Giám sát** | Prometheus + Grafana | Sử dụng Dashboard mặc định của Render/Koyeb & Supabase |

---

## 🛠️ Bước 1: Thiết Lập Database (Supabase)
Supabase cung cấp PostgreSQL được cài đặt sẵn PostGIS, đáp ứng hoàn hảo yêu cầu tính toán không gian của ứng dụng.

1. Đăng ký tài khoản miễn phí tại [Supabase.com](https://supabase.com/).
2. Tạo một dự án mới (ví dụ: `geoWeather`).
3. Truy cập **SQL Editor** trong bảng điều khiển Supabase, sao chép nội dung file [init-db.sql](file:///home/cp/Documents/geoWeather/infra/docker/init-db.sql) và chạy để khởi tạo cấu trúc bảng (`cities`, `regions`, `weather_current`, `weather_observations`, `weather_hourly_agg`).
4. Đi tới **Project Settings > Database** và lấy **Connection String** của PostgreSQL dạng URI (chọn chế độ Connection Pooler / Transaction Mode, có dạng `postgresql://...`). Bạn sẽ dùng chuỗi này làm biến `DATABASE_URL`.

---

## ⚡ Bước 2: Thiết Lập Cache & WebSocket Pub/Sub (Upstash)
Upstash cung cấp dịch vụ Serverless Redis chất lượng cao với 10,000 requests miễn phí mỗi ngày.

1. Đăng ký tài khoản tại [Upstash.com](https://upstash.com/).
2. Tạo một Redis Database mới, chọn vùng địa lý gần nhất (ví dụ: Singapore hoặc Châu Á).
3. Lấy chuỗi kết nối **Redis Connect URL** ở mục **Endpoints** (dạng `rediss://default:...@...upstash.io:6379`). Bạn sẽ sử dụng chuỗi này làm biến `REDIS_URL`.

---

## 🐍 Bước 3: Deploy Backend API (Render hoặc Koyeb)
Cả Render và Koyeb đều cung cấp dịch vụ Hosting Python Web Service miễn phí. Dưới đây là hướng dẫn cho Render:

1. Đăng ký tại [Render.com](https://render.com/).
2. Tạo một **Web Service** mới và kết nối với Github Repository của bạn.
3. Thiết lập cấu hình dự án:
   - **Runtime**: `Python`
   - **Build Command**: `pip install -r pyproject.toml` (hoặc cài đặt thông qua `pip install poetry && poetry install` tùy thuộc cách quản lý gói của bạn)
   - **Start Command**: `uvicorn apps.api.main:app --host 0.0.0.0 --port $PORT`
4. Thêm các **Environment Variables**:
    - `DATABASE_URL`: *<Chuỗi kết nối Supabase của bạn, khuyên dùng Direct URL ở cổng 5432 để tránh lỗi định dạng và prepared statements, ví dụ: postgresql://postgres.xzqprlvqfcndzwljxxzf:MẬT_KHẨU_ĐÃ_MÃ_HÓA@aws-1-ap-northeast-1.pooler.supabase.com:5432/postgres>*
    - `TIMESCALE_URL`: *<Sử dụng chung chuỗi kết nối Supabase cổng 5432 ở trên>*
    - `REDIS_URL`: *<Chuỗi kết nối Upstash Redis của bạn>*
    - `GEMINI_API_KEY`: *<API Key lấy từ Google AI Studio>*

> [!IMPORTANT]
> **Lưu ý đặc biệt về chuỗi kết nối Supabase (DATABASE_URL):**
> 1. Nếu mật khẩu của bạn chứa các ký tự đặc biệt như `?` hay `#`, bạn bắt buộc phải mã hóa URL (URL encode) các ký tự đó. Ví dụ: Ký tự `?` phải được viết thành `%3F`. Do đó, mật khẩu kết thúc bằng `??` sẽ trở thành `%3F%3F`.
> 2. Hãy sử dụng **Direct URL cổng 5432** thay vì cổng 6543 (transaction mode pooler) cho `DATABASE_URL` và `TIMESCALE_URL` của Render. Thư viện `asyncpg` sử dụng Prepared Statements để tối ưu hóa truy vấn, tính năng này không được hỗ trợ ổn định trên cổng 6543 (PgBouncer Transaction mode) và dễ gây ra các lỗi kết nối.

*Lưu ý: Bạn cần thay đổi tệp `apps/api/routers/weather.py` theo hướng dẫn tại [fastapi_app_patch.py](file:///home/cp/Documents/geoWeather/free_deployment/fastapi_app_patch.py) để kích hoạt cơ chế đồng bộ trực tiếp không dùng Kafka.*

---

## 🌐 Bước 4: Deploy Frontend (Vercel)
Vercel là dịch vụ lưu trữ tối ưu nhất cho Next.js Monorepo. Dưới đây là cách cấu hình để vượt qua lỗi Turborepo thiếu trường `packageManager`:

### Cách 1: Bỏ qua Turborepo (Khuyên dùng)
1. Đăng ký tài khoản tại [Vercel.com](https://vercel.com/).
2. Nhấp **Add New > Project**, chọn Github Repository chứa mã nguồn của bạn.
3. Trong phần cấu hình Monorepo (Next.js Monorepo):
   - **Framework Preset**: `Next.js`
   - **Root Directory**: `.` (để ở thư mục gốc của Monorepo)
   - **Build Command**: Thay đổi mặc định thành `npm run build --prefix apps/web`
   - **Output Directory**: `apps/web/.next`

### Cách 2: Đặt Thư mục gốc trực tiếp vào ứng dụng web
- Thiết lập **Root Directory** trong Vercel thành `apps/web` thay vì `.`. Vercel sẽ tự động phát hiện dự án Next.js độc lập và dùng lệnh build tiêu chuẩn (`next build`) mà không chạy Turborepo.

### Cách 3: Sửa file package.json gốc
- Thêm trường `"packageManager"` vào tệp `package.json` ở thư mục gốc của bạn:
  ```json
  "packageManager": "npm@10.2.4"
  ```
  *(Bạn cần thay đổi phiên bản npm tương ứng với môi trường của mình).*

4. Thiết lập **Environment Variables**:
   - `NEXT_PUBLIC_API_URL`: *<URL dịch vụ Backend API đã deploy ở Bước 3, ví dụ: https://geoweather-api.onrender.com>*
   - `NEXT_PUBLIC_MAPBOX_TOKEN`: *(Không bắt buộc / Để trống - Dự án sử dụng bản đồ nền miễn phí từ CartoDB nên không cần token này).*
5. Nhấp **Deploy** và chờ quá trình build hoàn tất.

---

## ⏰ Bước 5: Cấu Hình Đồng Bộ Dữ Liệu Tự Động (Cron Job)
Hệ thống cần định kỳ gọi Open-Meteo API để cập nhật thời tiết và phân tích dữ liệu không gian. Để làm việc này tự động và miễn phí:

### Cách 1: Sử dụng GitHub Actions (Khuyên dùng)
Tạo file `.github/workflows/weather_sync.yml` trong repo của bạn:
```yaml
name: GeoWeather Data Ingestion Cron

on:
  schedule:
    - cron: '*/10 * * * *' # Chạy mỗi 10 phút một lần

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger Ingestion API
        run: |
          curl -X POST "https://<url-backend-cua-ban>.onrender.com/api/v1/weather/sync" \
               -H "accept: application/json" \
               -d ""
```

### Cách 2: Sử dụng cron-job.org
1. Đăng ký tài khoản miễn phí tại [cron-job.org](https://cron-job.org/).
2. Tạo một Cronjob mới.
3. Nhập URL: `https://<url-backend-cua-ban>.onrender.com/api/v1/weather/sync`.
4. Chọn Method: `POST`.
5. Đặt tần suất chạy: Mỗi 10 hoặc 15 phút.

---

## 🚀 Bước 6: Khởi Tạo Dữ Liệu Ban Đầu (Seeding Cities)
Để bản đồ hiển thị được các thành phố ban đầu, bạn cần chạy script nhập dữ liệu một lần duy nhất.
Bạn có thể mở Terminal cục bộ, trỏ `DATABASE_URL` tới Supabase và chạy lệnh:
```bash
DATABASE_URL="postgresql://user:pass@supabase-host:5432/postgres" python services/ingestion/city_loader.py
```
Script sẽ tự động tải danh sách 15,000 thành phố lớn nhất thế giới từ GeoNames, tính toán H3 index cho từng tọa độ, và lưu trữ trực tiếp vào database Supabase của bạn.

Chúc bạn triển khai dự án GeoWeather thành công và vận hành 24/7 với chi phí 0 USD!
