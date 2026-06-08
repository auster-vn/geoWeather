# GeoWeather Routing Feature (Experimental)

Nhánh `feature/routing` chứa mã nguồn đang được phát triển cho tính năng Chỉ đường Thông minh (Smart Routing).

## Tính năng chính
- **Tìm kiếm địa điểm:** Sử dụng Photon API (dựa trên OpenStreetMap) để tìm kiếm và tự động điền (Autocomplete) địa chỉ toàn cầu.
- **Tính toán lộ trình:** Sử dụng OSRM (Open Source Routing Machine) để tìm đường đi ngắn nhất giữa hai điểm.
- **Giao diện Kính mờ (Glassmorphism):** Tích hợp mượt mà vào giao diện Mobile và Desktop với hiệu ứng kính mờ cao cấp.
- **Vẽ bản đồ:** Lộ trình được vẽ trực tiếp lên bản đồ MapLibre GL bằng chuẩn GeoJSON với hiệu ứng phát sáng (glow) để dễ nhìn trên nền tối.

## Cần phát triển thêm
- Xử lý các lỗi khi thay đổi kích thước cửa sổ trên thiết bị di động.
- Tối ưu hóa UI/UX để không bị che khuất bởi các bảng điều khiển khác.
- Tích hợp thêm các chỉ số thời tiết dọc theo lộ trình (ví dụ: mưa trên đường đi, cảnh báo sương mù).

## Cách chạy
Đảm bảo bạn đang ở nhánh `feature/routing`:
```bash
git checkout feature/routing
docker-compose up -d --build
```
