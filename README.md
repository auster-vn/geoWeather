# GeoWeather

## Ý Tưởng (Idea)
GeoWeather là một hệ thống bản đồ thời tiết thời gian thực được xây dựng với mục tiêu cung cấp dữ liệu thời tiết chính xác dựa trên lưới không gian lục giác H3 của Uber. Thay vì chỉ hiển thị thời tiết theo tên thành phố tĩnh, hệ thống thu thập và phân tích dữ liệu ở cấp độ không gian - thời gian, hỗ trợ truy vấn NLP thông minh thông qua trí tuệ nhân tạo.

## Công Dụng (Use Cases)
- **Theo dõi thời tiết thời gian thực:** Cập nhật liên tục trạng thái thời tiết, nhiệt độ, lượng mưa, tốc độ gió trên bản đồ.
- **Phân tích không gian:** Phân mảnh bản đồ thành lưới H3 đa độ phân giải, giúp phân tích xu hướng thời tiết theo vùng một cách chính xác.
- **Trợ lý AI (GeoWeather Assistant):** Tích hợp công cụ tương tác bằng giọng nói và văn bản tự nhiên, tự động xử lý ý định (intent) và trả về thông tin thời tiết kèm theo bản đồ vị trí trực quan.
- **Giám sát hệ thống (Observability):** Thu thập các số liệu vận hành và hiệu suất hệ thống thời gian thực với Prometheus và Grafana.

## Công Nghệ (Technology Stack)
- **Frontend:** Next.js (React), Mapbox GL JS, WebSockets.
- **Backend API:** FastAPI (Python), SQLAlchemy, H3, Uvicorn, SlowAPI.
- **AI & NLP:** Google Gemini 1.5/2.5 Flash, NLTK, spaCy, Speech-to-Text.
- **Gateway & Load Balancing:** Go (Golang) Reverse Proxy.
- **Database & Ingestion:** PostgreSQL (PostGIS & TimescaleDB), Redis.
- **Infrastructure & Monitoring:** Docker Compose, Prometheus, Grafana.

## Kiến Trúc Hệ Thống (Architecture)
Hệ thống được thiết kế theo kiến trúc Microservices hướng sự kiện (Event-Driven):
1. **Data Ingestion Service:** Các background workers (producer) liên tục lấy dữ liệu từ Open-Meteo và đẩy vào TimescaleDB/PostGIS.
2. **Streaming Processor:** Lắng nghe thay đổi dữ liệu, tính toán các aggregate metric trên lưới H3 và phát sóng qua Redis Pub/Sub.
3. **API Layer:** FastAPI xử lý các truy vấn từ client, thực hiện Cache với Redis, Rate Limiting, và duy trì các kết nối WebSockets để đẩy dữ liệu thời gian thực cho UI.
4. **AI/NLP Layer:** Xử lý ngôn ngữ tự nhiên từ người dùng (Text/Audio), tích hợp Function Calling với Gemini để tra cứu CSDL hoặc gọi external API.
5. **Gateway Layer:** Được viết bằng Go, đóng vai trò nhận toàn bộ traffic, xử lý SSL, phân luồng requests (chia tải) về các service thích hợp.

## Cài Đặt & Cấu Hình (Configuration)

### 1. Yêu Cầu Hệ Thống
- Docker và Docker Compose (phiên bản mới nhất)
- Node.js >= 18 (nếu muốn chạy Web tĩnh độc lập)
- Các API Keys cần thiết: Mapbox Token, Gemini API Key.

### 2. Thiết lập Biến Môi Trường
Tạo file `.env` ở thư mục gốc của dự án với các cấu hình cơ bản sau:
```env
# Database
POSTGRES_USER=geo_user
POSTGRES_PASSWORD=your_password
POSTGRES_DB=geo_weather

# API Keys
GEMINI_API_KEY=your_gemini_api_key
NEXT_PUBLIC_MAPBOX_TOKEN=your_mapbox_token
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 3. Khởi Động Hệ Thống
Dự án được đóng gói toàn bộ qua Docker Compose. Để khởi chạy:
```bash
docker-compose up -d --build
```

### 4. Các Dịch Vụ Sẵn Sàng
Sau khi hệ thống khởi động hoàn tất, bạn có thể truy cập các dịch vụ tại:
- **Frontend Web UI:** http://localhost:3001
- **Backend API (Swagger Docs):** http://localhost:8000/docs
- **Grafana Dashboard:** http://localhost:3002 (Mặc định: admin/admin)
- **Prometheus Metrics:** http://localhost:9090
