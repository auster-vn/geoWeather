import json
import asyncio
import logging
from datetime import date as date_cls
from fastapi import APIRouter, Depends, Query, Request, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import speech_recognition as sr
import tempfile
import os

from ..core.config import settings
from ..core.database import get_db
from ..tools.weather_tools import weather_tool_definitions, execute_tool
from ..services.ai_nlp import nlp_service
from ..core.rate_limit import limiter

logger = logging.getLogger(__name__)
router = APIRouter()

# ─── System prompt ────────────────────────────────────────────────────────────

def _build_system_prompt() -> str:
    from datetime import datetime
    import zoneinfo
    vn_tz = zoneinfo.ZoneInfo('Asia/Bangkok')
    today = datetime.now(vn_tz).strftime('%Y-%m-%d')
    return f"""Bạn là GeoWeather Assistant – trợ lý thời tiết thông minh tích hợp bản đồ GIS thời gian thực.
Ngày hôm nay: {today} (múi giờ UTC+7, Việt Nam).

Bạn có quyền gọi các công cụ sau:
- get_weather_by_city(city_name): thời tiết HIỆN TẠI (nhiệt độ, độ ẩm, gió, mưa, tầm nhìn, lượng mây)
- get_weather_by_coords(lat, lon): thời tiết theo tọa độ
- compare_cities(cities): so sánh thời tiết nhiều thành phố cùng lúc
- get_rain_forecast(city_name, target_date?): dự báo nhiệt độ & mưa theo giờ (7 ngày). Dùng khi hỏi
  "khi nào mưa", "ngày mai có mưa không", "sáng mai nhiệt độ bao nhiêu", "lạnh không"
- get_daily_forecast(city_name): dự báo tổng quan 7 ngày tới (nhiệt độ max/min, UV). Dùng khi hỏi "thời tiết tuần tới", "dự báo các ngày tới".
- get_air_quality_and_uv(city_name): lấy chỉ số ô nhiễm không khí (AQI), PM2.5, bụi mịn và UV.
- get_sun_times(city_name, target_date?): giờ bình minh và hoàng hôn.

Quy tắc trả lời:
1. Luôn gọi tool trước rồi mới trả lời – KHÔNG bịa dữ liệu. Nếu dữ liệu rỗng, báo xin lỗi không có dữ liệu.
2. target_date phải là "YYYY-MM-DD". Ví dụ "ngày 7/6" → "{today[:4]}-06-07".
3. Khi có tọa độ, LUÔN chèn tag [MAP:lat,lon,zoom] để bản đồ tự động bay đến vị trí đó.
   Ví dụ: "Thời tiết Đà Nẵng [MAP:16.068,108.212,10] hiện tại..."
4. HIỂN THỊ ĐẸP MẮT: Sử dụng Markdown. Dùng BẢNG (table) khi trả về danh sách dự báo nhiều ngày hoặc nhiều giờ. In đậm các chỉ số quan trọng (như **AQI: 120 (Kém)**, **Nhiệt độ: 30°C**).
5. Trả lời bằng tiếng Việt thân thiện, dùng emoji phù hợp (🌧️🌅☀️😷).
"""

# ─── Gemini chat ──────────────────────────────────────────────────────────────

async def run_gemini_chat(message: str, history: list, db: AsyncSession):
    """
    Gemini Function Calling pipeline:
    1. Send message + tool definitions → Gemini decides which tool(s) to call
    2. Execute tool(s) with real data (Open-Meteo / PostGIS)
    3. Feed tool results back → Gemini generates natural language response
    4. Stream the response word-by-word
    """
    from google import genai
    from google.genai import types

    # Initialize the new SDK client
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    # Build Gemini-compatible tool declarations from our tool definitions
    tool_defs = weather_tool_definitions()
    gemini_functions = []
    for t in tool_defs:
        gemini_functions.append(
            types.FunctionDeclaration(
                name=t["name"],
                description=t["description"],
                parameters=t["input_schema"]
            )
        )
    gemini_tools = types.Tool(function_declarations=gemini_functions)

    # Convert history to Gemini format
    gemini_history = []
    for h in history:
        role = "user" if h.get("role") == "user" else "model"
        gemini_history.append(
            types.Content(role=role, parts=[types.Part.from_text(text=h.get("content", ""))])
        )

    # Note: We must use the aio (async) client for streaming and non-blocking calls
    try:
        chat = client.aio.chats.create(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                system_instruction=_build_system_prompt(),
                tools=[gemini_tools],
                temperature=0.7,
            ),
            history=gemini_history if gemini_history else None
        )

        # Round 1: Let Gemini decide what tools to call
        response = await chat.send_message(message)

        # Collect all tool calls Gemini wants
        tool_results = []
        if response.function_calls:
            for fc in response.function_calls:
                tool_name = fc.name
                tool_args = dict(fc.args)

                logger.info(f"[Gemini] Calling tool: {tool_name}({tool_args})")
                yield f"data: {json.dumps({'type': 'tool_call', 'tool': tool_name, 'args': tool_args}, default=str)}\n\n"

                # Execute with REAL data
                result = await execute_tool(tool_name, tool_args, db)
                logger.info(f"[Gemini] Tool result: {json.dumps(result, default=str)[:200]}")

                yield f"data: {json.dumps({'type': 'tool_result', 'tool': tool_name, 'data': result}, default=str)}\n\n"
                tool_results.append((tool_name, tool_args, result))

        # If tools were called, send results back and stream final answer
        if tool_results:
            function_response_parts = []
            for tool_name, tool_args, result in tool_results:
                function_response_parts.append(
                    types.Part.from_function_response(
                        name=tool_name,
                        response=result
                    )
                )

            # Stream the final response
            response_stream = await chat.send_message_stream(function_response_parts)
            async for chunk in response_stream:
                if chunk.text:
                    yield f"data: {json.dumps({'type': 'text', 'content': chunk.text})}\n\n"
        else:
            # Gemini answered directly (no tool needed)
            if response.text:
                words = response.text.split(" ")
                for word in words:
                    yield f"data: {json.dumps({'type': 'text', 'content': word + ' '})}\n\n"
                    await asyncio.sleep(0.03)

    except Exception as e:
        logger.error(f"Gemini chat error: {e}", exc_info=True)
        # Fallback to mock
        async for chunk in run_mock_chat(message, db, history):
            yield chunk
        return

    yield "data: [DONE]\n\n"


# ─── Mock chat fallback (no API key) ─────────────────────────────────────────

async def run_mock_chat(message: str, db: AsyncSession, history: list = None):
    """Keyword-based NLP fallback used when no Gemini API key is configured or quota is exceeded."""
    logger.info("Running mock chatbot fallback...")

    import re
    import unicodedata
    from sqlalchemy import text

    def remove_diacritics(text_val: str) -> str:
        normalized = unicodedata.normalize('NFKD', text_val)
        cleaned = "".join([c for c in normalized if not unicodedata.combining(c)])
        return cleaned.replace('Đ', 'D').replace('đ', 'd')

    normalized = remove_diacritics(message).lower()
    clean_msg  = re.sub(r'[^a-z0-9\s]', ' ', normalized)
    clean_msg  = " ".join(clean_msg.split())

    RAIN_KEYWORDS = ["mua", "bao gio mua", "khi nao mua", "het mua", "rain",
                     "forecast", "du bao mua", "xac suat mua", "co mua khong"]
    SUN_KEYWORDS  = ["binh minh", "hoang hon", "mat troi moc", "mat troi lan",
                     "sunrise", "sunset", "dawn", "dusk", "may gio mat troi"]

    is_rain_query = any(kw in clean_msg for kw in RAIN_KEYWORDS)
    is_sun_query  = any(kw in clean_msg for kw in SUN_KEYWORDS)

    target_date = None
    today = date_cls.today()
    date_match = re.search(r'(\d{1,2})[\/\-](\d{1,2})', message)
    if date_match:
        day, month = int(date_match.group(1)), int(date_match.group(2))
        try:
            target_date = date_cls(today.year, month, day).isoformat()
        except ValueError:
            pass

    target_hour = None
    hour_match = re.search(r'(?<!\d)(\d{1,2})\s*(h|giờ|g)', clean_msg)
    if hour_match:
        target_hour = int(hour_match.group(1))

    async def extract_city(msg_str: str):
        # Check for explicit coordinates first
        coords_match = re.search(r'lat:\s*([0-9.-]+).*lon:\s*([0-9.-]+)', msg_str, re.IGNORECASE)
        if coords_match:
            try:
                lat = float(coords_match.group(1))
                lon = float(coords_match.group(2))
                q_nearest = text("""
                    SELECT city_name, ST_Y(geom) AS lat, ST_X(geom) AS lon
                    FROM cities
                    ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
                    LIMIT 1;
                """)
                res = await db.execute(q_nearest, {"lon": lon, "lat": lat})
                row = res.mappings().first()
                if row:
                    return dict(row)
            except Exception as e:
                logger.error(f"Coord lookup error: {e}")
        c_msg = re.sub(r'[^a-z0-9\s]', ' ', remove_diacritics(msg_str).lower())
        c_msg = " ".join(c_msg.split())
        if not c_msg: return None
        try:
            q = text("""
                SELECT city_name, ST_Y(geom) AS lat, ST_X(geom) AS lon
                FROM cities
                WHERE :padded LIKE '% ' || LOWER(REGEXP_REPLACE(ascii_name,
                      ' (City|Province|Town|District|Municipality)$', '', 'i')) || ' %'
                ORDER BY population DESC LIMIT 1;
            """)
            res = await db.execute(q, {"padded": f" {c_msg} "})
            row = res.mappings().first()
            if row:
                return dict(row)

            words = c_msg.split()
            candidates = list(words)
            for i in range(len(words) - 1):
                candidates.append(f"{words[i]} {words[i+1]}")
                candidates.append(f"{words[i]}{words[i+1]}")
            STOPWORDS = {"toi", "the", "nao", "khi", "bao", "gio", "thu", "mua",
                         "ngay", "mai", "hom", "nay", "co", "khong", "luc", "het",
                         "rain", "sun", "may", "mat", "khi", "tiet", "thoi", "thi", "sao", "o", "tai"}
            for cand in sorted(candidates, key=len, reverse=True):
                if len(cand) < 3 or cand in STOPWORDS:
                    continue
                q2 = text("""
                    SELECT city_name, ST_Y(geom) AS lat, ST_X(geom) AS lon FROM cities
                    WHERE LOWER(REGEXP_REPLACE(ascii_name,
                          ' (City|Province|Town|District|Municipality)$', '', 'i')) ILIKE :cand
                    ORDER BY population DESC LIMIT 1;
                """)
                r2 = await db.execute(q2, {"cand": cand})
                row2 = r2.mappings().first()
                if row2:
                    return dict(row2)
        except Exception as e:
            logger.error(f"City lookup error: {e}")
        return None

    city_to_query = await extract_city(message)
    if not city_to_query and history:
        for h in reversed(history):
            if h.get("role") == "user":
                city_to_query = await extract_city(h.get("content", ""))
                if city_to_query:
                    break

    response_text = ""

    if city_to_query and is_sun_query:
        sun = await execute_tool("get_sun_times",
            {"city_name": city_to_query["city_name"], **({"target_date": target_date} if target_date else {})}, db)
        if "error" in sun:
            response_text = f"Không thể lấy dữ liệu: {sun['error']}"
        else:
            lat, lon = sun["lat"], sun["lon"]
            lines = [f"🌅 **Bình minh & Hoàng hôn tại {sun['city']}** [MAP:{lat:.4f},{lon:.4f},9]",
                     f"_(Múi giờ: {sun.get('timezone', 'Asia/Bangkok')})_\n"]
            for d in sun["sun_schedule"]:
                lines.append(f"- **{d['date']}** — 🌄 Mọc: **{d['sunrise']}** | 🌇 Lặn: **{d['sunset']}** ({d['daylight_hours']}h)")
            response_text = "\n".join(lines)

    elif city_to_query and is_rain_query:
        rain = await execute_tool("get_rain_forecast",
            {"city_name": city_to_query["city_name"], **({"target_date": target_date} if target_date else {})}, db)
        if "error" in rain:
            response_text = f"Không thể lấy dự báo mưa: {rain['error']}"
        else:
            lat, lon = rain["lat"], rain["lon"]
            lines = [f"🌧️ **Dự báo mưa tại {rain['city']}** [MAP:{lat:.4f},{lon:.4f},9]",
                     f"_({'ngày ' + target_date if target_date else '3 ngày tới'})_\n"]
            if rain["daily_summary"]:
                lines.append("**Tổng hợp theo ngày:**")
                for d in rain["daily_summary"]:
                    lines.append(f"- {d['date']}: 💧 {d['total_rain_mm']} mm ({d['rain_hours']}h) — {d['condition']}")
                lines.append("")
            s = rain.get("summary", {})
            fr = s.get("first_likely_rain")
            fc = s.get("first_clear_after_rain")
            if fr:
                lines.append(f"⏰ **Bắt đầu mưa:** {fr['time']} ({fr['precip_prob_pct']}%, {fr['precipitation_mm']} mm)")
            else:
                lines.append("✅ Không có dự báo mưa.")
            if fc:
                lines.append(f"☀️ **Tạnh mưa từ:** {fc['time']} (còn {fc['precip_prob_pct']}%)")
            hourly = sorted([h for h in rain["hourly_forecast"] if h["precip_prob_pct"] > 0],
                            key=lambda x: x["precip_prob_pct"], reverse=True)[:6]
            if hourly:
                lines.append("\n**Giờ mưa cao nhất:**")
                for h in sorted(hourly, key=lambda x: x["time"]):
                    bar = "█" * (h["precip_prob_pct"] // 10)
                    lines.append(f"- {h['time']}: {bar} {h['precip_prob_pct']}% — {h['precipitation_mm']} mm")
            response_text = "\n".join(lines)

    elif city_to_query and target_hour is not None:
        from apps.api.tools.weather_tools import _fetch_open_meteo_forecast
        try:
            forecast_data = await _fetch_open_meteo_forecast(city_to_query["lat"], city_to_query["lon"], tz="Asia/Bangkok")
            hourly = forecast_data.get("hourly", {})
            times = hourly.get("time", [])
            
            idx = -1
            target_time_str = f"T{target_hour:02d}:00"
            for i, t in enumerate(times):
                if target_date and f"{target_date}{target_time_str}" in t:
                    idx = i
                    break
                elif not target_date and target_time_str in t and i < 48:
                    # Next occurrence of this hour
                    idx = i
                    break
                    
            if idx != -1:
                temp = hourly.get("temperature_2m", [])[idx]
                prob = hourly.get("precipitation_probability", [])[idx]
                precip = hourly.get("precipitation", [])[idx]
                
                response_text = (
                    f"🌍 Thời tiết tại **{city_to_query['city_name']}** lúc **{target_hour}h** "
                    f"({'ngày ' + target_date if target_date else 'hôm nay/ngày mai'}):\n\n"
                    f"- 🌡️ **Nhiệt độ:** {temp:.1f}°C\n"
                    f"- 💧 **Xác suất mưa:** {prob}%\n"
                    f"- 🌧️ **Lượng mưa:** {precip:.1f} mm\n\n"
                    "Hỏi thêm: \"Khi nào mưa?\", \"Hoàng hôn mấy giờ?\" 😊"
                )
            else:
                response_text = "Không tìm thấy dữ liệu dự báo cho khung giờ này."
        except Exception as e:
            logger.error(f"Error fetching hourly forecast: {e}")
            response_text = "Lỗi khi tải dữ liệu dự báo theo giờ."

    elif city_to_query:
        weather_info = await execute_tool("get_weather_by_city", {"city_name": city_to_query["city_name"]}, db)
        if "error" in weather_info or "note" in weather_info:
            response_text = (f"Tìm thấy **{city_to_query['city_name']}** "
                             f"[MAP:{city_to_query['lat']},{city_to_query['lon']},10] "
                             "nhưng chưa có dữ liệu thời tiết thực. Hãy chạy đồng bộ dữ liệu!")
        else:
            def fmt(val):
                return f"{float(val):.1f}" if isinstance(val, (int, float)) else val

            wcode = weather_info.get('weather_code', 0) or 0
            desc_map = {(0,): "Trời quang ☀️", (1,2,3): "Có mây ⛅",
                        (45,48): "Sương mù 🌫️", (51,53,55,61,63,65): "Có mưa 🌧️",
                        (95,96,99): "Có dông ⛈️"}
            desc = next((v for keys, v in desc_map.items() if wcode in keys), "Bình thường")
            response_text = (
                f"🌍 Thời tiết hiện tại tại **{city_to_query['city_name']}** "
                f"[MAP:{city_to_query['lat']},{city_to_query['lon']},10]:\n\n"
                f"- 🌡️ **Nhiệt độ:** {fmt(weather_info.get('temperature', '?'))}°C "
                f"(cảm giác {fmt(weather_info.get('feels_like', '?'))}°C)\n"
                f"- 🌤️ **Trạng thái:** {desc}\n"
                f"- 💧 **Độ ẩm:** {fmt(weather_info.get('humidity', '?'))}%\n"
                f"- 💨 **Gió:** {fmt(weather_info.get('wind_speed', '?'))} m/s\n"
                f"- 🌧️ **Lượng mưa:** {fmt(weather_info.get('precipitation', 0))} mm\n\n"
                "Hỏi thêm: \"Khi nào mưa?\", \"Hoàng hôn mấy giờ?\" 😊"
            )
    else:
        response_text = (
            "Chào bạn! Tôi là **GeoWeather Assistant** 🌤️\n\n"
            "Bạn có thể hỏi:\n"
            "- 🌡️ \"Thời tiết Hà Nội hôm nay?\"\n"
            "- 🌧️ \"Khi nào Đà Nẵng mưa?\"\n"
            "- 🌧️ \"Ngày mai Huế có mưa không?\"\n"
            "- 🌅 \"Bình minh Hội An ngày 07/06 mấy giờ?\"\n"
            "- 🌇 \"Hoàng hôn Vũng Tàu lúc mấy giờ?\"\n"
            "- ⚖️ \"So sánh thời tiết Hà Nội và Sài Gòn\"\n\n"
            "Nhập tên tỉnh/thành phố bằng tiếng Việt có dấu hoặc tiếng Anh nhé!"
        )

    words = response_text.split(" ")
    for word in words:
        yield f"data: {json.dumps({'type': 'text', 'content': word + ' '})}\n\n"
        await asyncio.sleep(0.04)
    yield "data: [DONE]\n\n"


async def run_local_nlp_chat(message: str, db: AsyncSession):
    intent = nlp_service.classify_intent(message)
    target_time = nlp_service.extract_time(message)
    
    response_text = ""
    
    # Check for exact coordinates in message (e.g. from Get Location button)
    import re
    coord_match = re.search(r"lat:\s*(-?\d+\.?\d*),\s*lon:\s*(-?\d+\.?\d*)", message)
    
    if coord_match:
        lat = float(coord_match.group(1))
        lon = float(coord_match.group(2))
        city_name = "Vị trí của bạn"
        location = "vị trí của tôi"
    else:
        location = await nlp_service.extract_location(message, db)
        if location:
            lat, lon, city_name = await nlp_service.get_city_coords(location, db)
        else:
            lat, lon, city_name = None, None, None
    
    if location:
        if lat and lon:
            if target_time:
                from ..tools.weather_tools import execute_tool
                hourly = await execute_tool("get_hourly_forecast", {"city_name": city_name, "target_time": target_time}, db)
                if "error" in hourly:
                    response_text = f"Xin lỗi, {hourly['error']}"
                else:
                    response_text = (
                        f"⏰ **Dự báo cho {city_name} lúc {target_time} hôm nay** [MAP:{lat},{lon},10]:\n\n"
                        f"- 🌡️ Nhiệt độ: {hourly.get('temperature')}°C\n"
                        f"- 💧 Xác suất mưa: {hourly.get('precip_prob_pct')}%\n"
                        f"- 🌧️ Lượng mưa: {hourly.get('precipitation')} mm\n"
                        f"- ☁️ Trạng thái: {hourly.get('condition')}"
                    )
            elif intent == "rain" or intent == "forecast":
                from ..tools.weather_tools import execute_tool
                forecast = await execute_tool("get_rain_forecast", {"city_name": city_name}, db)
                if "error" in forecast:
                    response_text = f"Xin lỗi, {forecast['error']}"
                else:
                    rain_info = forecast.get('first_likely_rain', {})
                    response_text = (
                        f"🌧️ **Dự báo mưa cho {city_name}** [MAP:{lat},{lon},10]:\n\n"
                        f"- ☔ Thời gian mưa gần nhất: {rain_info.get('time', 'Không rõ')}\n"
                        f"- 🌡️ Nhiệt độ lúc mưa: {rain_info.get('temperature', '?')}°C\n"
                        f"- 💧 Lượng mưa dự kiến: {rain_info.get('precipitation_mm', '?')} mm\n"
                        f"- ☁️ Trạng thái: {rain_info.get('condition', '?')}\n\n"
                        f"*(Dự báo dựa trên Open-Meteo)*"
                    )
            elif intent == "sun":
                from ..tools.weather_tools import execute_tool
                sun = await execute_tool("get_sun_times", {"city_name": city_name}, db)
                if "error" in sun:
                    response_text = f"Xin lỗi, {sun['error']}"
                else:
                    response_text = (
                        f"🌅 **Thời gian Mặt trời tại {city_name}** [MAP:{lat},{lon},10]:\n\n"
                        f"- Bình minh: {sun.get('sunrise_time', '?')}\n"
                        f"- Hoàng hôn: {sun.get('sunset_time', '?')}"
                    )
            else:
                from ..tools.weather_tools import execute_tool
                weather = await execute_tool("get_weather_by_coords", {"lat": lat, "lon": lon}, db)
                if "error" in weather:
                    response_text = f"Xin lỗi, {weather['error']}"
                else:
                    def fmt(v): return round(v, 1) if isinstance(v, float) else v
                    response_text = (
                        f"🌍 **Thời tiết hiện tại tại {city_name}** [MAP:{lat},{lon},10]:\n\n"
                        f"- 🌡️ Nhiệt độ: {fmt(weather.get('temperature', '?'))}°C (cảm giác {fmt(weather.get('feels_like', '?'))}°C)\n"
                        f"- 💧 Độ ẩm: {fmt(weather.get('humidity', '?'))}%\n"
                        f"- 💨 Gió: {fmt(weather.get('wind_speed', '?'))} m/s\n"
                        f"- 🌧️ Lượng mưa: {fmt(weather.get('precipitation', 0))} mm"
                    )
        else:
            response_text = f"Xin lỗi, tôi không tìm thấy dữ liệu cho khu vực '{location}'. Bạn có thể gõ rõ tên tỉnh thành bằng tiếng Việt có dấu được không?"
    else:
        # If no location is found
        if "chào" in message.lower():
            response_text = "Chào bạn! Tôi là GeoWeather Assistant (Local AI). Bạn cần xem thời tiết ở đâu?"
        else:
            response_text = "Bạn vui lòng cung cấp tên Tỉnh/Thành phố rõ ràng để tôi tra cứu nhé (VD: 'thời tiết Hà Nội', 'khi nào Sài Gòn mưa')."
            
    words = response_text.split(" ")
    for word in words:
        yield f"data: {json.dumps({'type': 'text', 'content': word + ' '})}\n\n"
        await asyncio.sleep(0.04)
    yield "data: [DONE]\n\n"

@router.get("/stream")
@limiter.limit("5/minute")
async def chat_stream(
    request: Request,
    message: str = Query(..., min_length=1),
    history_json: str = Query("[]"),
    model: str = Query("local"),
    db: AsyncSession = Depends(get_db)
):
    if model == "gemini":
        history = json.loads(history_json) if history_json else []
        return StreamingResponse(run_gemini_chat(message, history, db), media_type="text/event-stream")
    else:
        return StreamingResponse(run_local_nlp_chat(message, db), media_type="text/event-stream")

@router.post("/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    try:
        audio_bytes = await audio.read()
        
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        
        result = await client.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                types.Part.from_bytes(
                    data=audio_bytes,
                    mime_type='audio/wav',
                ),
                "Transcribe this Vietnamese speech to text accurately. Output only the transcription, without any markdown formatting, quotes, or conversational filler."
            ]
        )
        
        text = result.text.strip()
        if not text:
            return {"error": "Không thể nhận diện giọng nói. Bạn có thể nói lại rõ hơn không?"}
            
        return {"text": text}
    except Exception as e:
        logger.error(f"STT Error: {e}")
        return {"error": str(e)}
