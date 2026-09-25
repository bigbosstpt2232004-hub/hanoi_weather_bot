"""
Weather Bot - Thông báo thời tiết Hà Nội
Gửi qua Telegram Bot
"""

import os
import requests
from datetime import datetime
from collections import defaultdict
import pytz

# ──────────────────────────────────────────
# CẤU HÌNH
# ──────────────────────────────────────────
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY")
TELEGRAM_BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID    = os.environ.get("TELEGRAM_CHAT_ID")

# Toạ độ Hà Nội
LAT = 21.0285
LON = 105.8542
TIMEZONE = pytz.timezone("Asia/Ho_Chi_Minh")

# ──────────────────────────────────────────
# LẤY DỮ LIỆU THỜI TIẾT
# ──────────────────────────────────────────

def get_weather_data() -> dict:
    """Lấy dữ liệu thời tiết hiện tại, dự báo 5 ngày và chất lượng không khí từ OpenWeatherMap."""
    base_url = "https://api.openweathermap.org/data/2.5"
    params = {
        "lat": LAT,
        "lon": LON,
        "appid": OPENWEATHER_API_KEY,
    }

    # 1. Thời tiết hiện tại
    current_resp = requests.get(
        f"{base_url}/weather",
        params={**params, "units": "metric", "lang": "vi"},
        timeout=10,
    )
    current_resp.raise_for_status()
    current = current_resp.json()

    # 2. Dự báo 5 ngày / 3 giờ (lấy 32 mốc để đủ 4 ngày)
    forecast_resp = requests.get(
        f"{base_url}/forecast",
        params={**params, "units": "metric", "lang": "vi", "cnt": 32},
        timeout=10,
    )
    forecast_resp.raise_for_status()
    forecast = forecast_resp.json()

    # 3. Chất lượng không khí (Air pollution: AQI, PM2.5, PM10)
    air = {}
    try:
        air_resp = requests.get(
            f"{base_url}/air_pollution",
            params=params,
            timeout=10,
        )
        if air_resp.ok:
            air = air_resp.json()
    except Exception as e:
        print(f"⚠️ Không lấy được thông tin ô nhiễm không khí: {e}")

    return {"current": current, "forecast": forecast, "air": air}


# ──────────────────────────────────────────
# HELPER: ICON, HƯỚNG GIÓ & CHẤT LƯỢNG KHÔNG KHÍ
# ──────────────────────────────────────────

def weather_emoji(description: str, icon_code: str) -> str:
    """Chuyển mã icon OpenWeather thành emoji."""
    icon_map = {
        "01": "☀️",   # trời quang
        "02": "🌤️",  # ít mây
        "03": "⛅",   # mây rải rác
        "04": "☁️",   # nhiều mây / u ám
        "09": "🌧️",  # mưa rào
        "10": "🌦️",  # mưa vừa / mưa nhỏ
        "11": "⛈️",   # dông sét / bão
        "13": "❄️",   # tuyết
        "50": "🌫️",  # sương mù / bụi mờ
    }
    prefix = icon_code[:2] if icon_code else "01"
    return icon_map.get(prefix, "🌡️")


def format_wind_direction(degrees: float) -> str:
    """Chuyển đổi góc gió sang hướng la bàn tiếng Việt."""
    directions = [
        "Bắc", "Đông Bắc", "Đông", "Đông Nam",
        "Nam", "Tây Nam", "Tây", "Tây Bắc"
    ]
    idx = round(degrees / 45) % 8
    return directions[idx]


def parse_air_quality(air_data: dict) -> dict:
    """Phân tích chỉ số ô nhiễm không khí (AQI & PM2.5)."""
    if not air_data or "list" not in air_data or not air_data["list"]:
        return {
            "aqi": 0,
            "pm2_5": 0.0,
            "label": "Không có dữ liệu",
            "is_warning": False,
            "summary": "Không có dữ liệu",
        }

    item = air_data["list"][0]
    aqi = item["main"]["aqi"]
    pm2_5 = item["components"].get("pm2_5", 0.0)

    # Thang đánh giá AQI của OpenWeatherMap (1 đến 5)
    levels = {
        1: ("Tốt 🟢", False),
        2: ("Khá 🟡", False),
        3: ("Trung bình 🟠", False),
        4: ("Kém 🔴", True),
        5: ("Rất có hại 🟣", True),
    }
    label, is_warning = levels.get(aqi, ("Trung bình", False))
    warning_icon = " ⚠️" if is_warning else ""
    summary = f"{label} (AQI: {aqi} | PM2.5: {pm2_5:.1f} µg/m³){warning_icon}"

    return {
        "aqi": aqi,
        "pm2_5": pm2_5,
        "label": label,
        "is_warning": is_warning,
        "summary": summary,
    }


# ──────────────────────────────────────────
# DỰ BÁO TRONG NGÀY (INTRADAY FORECAST)
# ──────────────────────────────────────────

def format_intraday_forecast(forecast_data: dict, now: datetime) -> str:
    """Tạo dự báo các mốc trong ngày:
    - Sáng (< 10h): cập nhật mốc 6 giờ/khoảng (06:00, 12:00, 18:00, 24:00)
    - Trưa/Chiều (10h - 21h): cập nhật chi tiết 3 giờ/khoảng đến nửa đêm
    - Đêm (> 21h): 4 mốc 3h tiếp theo qua đêm đến sáng mai (tránh để trống)
    """
    midnight = now.replace(hour=23, minute=59, second=59, microsecond=0)

    # Các mốc còn lại trong ngày hôm nay
    today_items = [
        item for item in forecast_data.get("list", [])
        if now <= datetime.fromtimestamp(item["dt"], tz=TIMEZONE) <= midnight
    ]

    is_morning = now.hour < 10
    is_late_night = now.hour >= 22 or len(today_items) == 0

    if is_late_night:
        section_title = "⏱️ *DỰ BÁO ĐÊM NAY & SÁNG MAI (Mỗi 3h):*"
        chosen_items = [
            item for item in forecast_data.get("list", [])
            if datetime.fromtimestamp(item["dt"], tz=TIMEZONE) >= now
        ][:4]
    elif is_morning:
        section_title = "⏱️ *DỰ BÁO TRONG NGÀY (Mỗi 6h):*"
        # Lấy cách 6 tiếng (bước nhảy 2 trong danh sách mốc 3h)
        chosen_items = today_items[::2]
        if today_items and today_items[-1] not in chosen_items:
            chosen_items.append(today_items[-1])
    else:
        section_title = "⏱️ *DỰ BÁO CHIỀU & TỐI (Mỗi 3h):*"
        chosen_items = today_items

    lines = []
    for item in chosen_items:
        dt_local = datetime.fromtimestamp(item["dt"], tz=TIMEZONE)
        hour_str = dt_local.strftime("%H:%M")
        f_temp = round(item["main"]["temp"])
        f_icon = weather_emoji(
            item["weather"][0]["description"],
            item["weather"][0]["icon"],
        )
        f_pop = round(item.get("pop", 0) * 100)
        rain_3h = item.get("rain", {}).get("3h", 0.0)

        extra_tag = ""
        if 17 <= dt_local.hour <= 19:
            extra_tag = " ⚠️ [Tan tầm]" if f_pop >= 40 else " [Tan tầm]"

        rain_detail = ""
        if rain_3h > 0:
            rain_detail = f" ({f_pop}% mưa, ~{round(rain_3h, 1)}mm)"
        elif f_pop >= 20:
            rain_detail = f" ({f_pop}% mưa)"

        lines.append(f"  • {hour_str}  {f_icon} {f_temp}°C{rain_detail}{extra_tag}")

    content = "\n".join(lines) if lines else "  Chưa có dữ liệu dự báo cho mốc này."
    return f"{section_title}\n{content}"


# ──────────────────────────────────────────
# DỰ BÁO 3 NGÀY TỚI (MƯA, LƯỢNG NƯỚC & DÔNG BÃO)
# ──────────────────────────────────────────

def parse_3day_forecast(forecast_data: dict, now: datetime) -> list:
    """Gom nhóm theo ngày để tính nhiệt độ min-max, tổng mưa (mm), xác suất và cảnh báo bão."""
    days_data = defaultdict(lambda: {
        "temps": [],
        "rain_mm": 0.0,
        "pops": [],
        "storm": False,
        "weather_descs": [],
        "icons": [],
        "date_obj": None,
    })

    today_date = now.date()

    for item in forecast_data.get("list", []):
        dt_local = datetime.fromtimestamp(item["dt"], tz=TIMEZONE)
        item_date = dt_local.date()

        # Bỏ qua mốc trước ngày hôm nay
        if item_date < today_date:
            continue

        day_key = item_date.strftime("%Y-%m-%d")
        days_data[day_key]["date_obj"] = item_date
        days_data[day_key]["temps"].append(item["main"]["temp"])

        # Cộng dồn lượng mưa mm nếu có
        rain_3h = item.get("rain", {}).get("3h", 0.0)
        days_data[day_key]["rain_mm"] += rain_3h

        # Xác suất mưa (%)
        days_data[day_key]["pops"].append(item.get("pop", 0))

        # Cảnh báo dông bão: mã 2xx (Thunderstorm), hoặc mưa rất to 502-504, hoặc gió giật >= 45 km/h
        weather_id = item["weather"][0]["id"]
        gust = item.get("wind", {}).get("gust", 0) * 3.6
        if (200 <= weather_id <= 232) or (gust >= 45) or (weather_id in [502, 503, 504]):
            days_data[day_key]["storm"] = True

        days_data[day_key]["weather_descs"].append(item["weather"][0]["description"])
        days_data[day_key]["icons"].append(item["weather"][0]["icon"])

    results = []
    sorted_days = sorted(days_data.keys())[:3]

    for i, day_str in enumerate(sorted_days):
        d_info = days_data[day_str]
        item_date = d_info["date_obj"]

        if item_date == today_date:
            day_label = "Hôm nay"
        elif (item_date - today_date).days == 1:
            day_label = "Ngày mai"
        elif (item_date - today_date).days == 2:
            day_label = "Ngày kia"
        else:
            weekdays_vi = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
            day_label = weekdays_vi[item_date.weekday()]

        date_formatted = item_date.strftime("%d/%m")
        min_t = round(min(d_info["temps"]))
        max_t = round(max(d_info["temps"]))
        total_rain = round(d_info["rain_mm"], 1)
        max_pop = round(max(d_info["pops"]) * 100) if d_info["pops"] else 0

        # Lựa chọn icon đại diện
        if d_info["storm"]:
            rep_icon = "⛈️"
        elif total_rain > 5:
            rep_icon = "🌧️"
        elif total_rain > 0 or max_pop >= 40:
            rep_icon = "🌦️"
        else:
            mid_idx = len(d_info["icons"]) // 2
            rep_icon = weather_emoji("", d_info["icons"][mid_idx])

        rain_desc_parts = []
        if total_rain > 0:
            rain_desc_parts.append(f"~{total_rain} mm")
        if max_pop >= 30:
            rain_desc_parts.append(f"{max_pop}%")

        rain_str = f" ({', '.join(rain_desc_parts)})" if rain_desc_parts else ""
        storm_tag = " ⚠️ Dông bão" if d_info["storm"] else ""

        line = f"• {day_label} ({date_formatted}): {min_t}° - {max_t}°C | {rep_icon}{rain_str}{storm_tag}"
        results.append({
            "line": line,
            "day_label": day_label,
            "date": date_formatted,
            "is_storm": d_info["storm"],
            "total_rain": total_rain,
            "max_pop": max_pop,
        })

    return results


# ──────────────────────────────────────────
# LỜI KHUYÊN THÔNG MINH
# ──────────────────────────────────────────

def get_advice(data: dict, air_info: dict, three_days: list, now: datetime) -> str:
    """Đưa ra lời khuyên toàn diện dựa trên thời tiết, ô nhiễm không khí và dự báo bão."""
    current = data["current"]
    desc = current["weather"][0]["description"].lower()
    temp = current["main"]["temp"]
    feels = current["main"]["feels_like"]
    humidity = current["main"]["humidity"]
    wind_spd = current["wind"]["speed"] * 3.6

    tips = []

    # 1. Cảnh báo dông bão trong 3 ngày tới
    for d in three_days:
        if d["is_storm"]:
            tips.append(f"⚡ CẢNH BÁO: {d['day_label']} ({d['date']}) có khả năng xảy ra dông bão, sấm sét và gió giật mạnh!")
            break

    # 2. Cảnh báo bụi mịn PM2.5 / Không khí kém
    if air_info.get("is_warning"):
        tips.append("😷 Không khí ở mức Kém, hãy đeo khẩu trang chống bụi mịn PM2.5 khi ra đường.")

    # 3. Lời khuyên mưa / ô dù
    has_rain_today = any(d["day_label"] == "Hôm nay" and (d["total_rain"] > 0 or d["max_pop"] >= 40) for d in three_days)
    if "mưa" in desc or "rain" in desc or has_rain_today:
        if now.hour < 12:
            tips.append("☂️ Hôm nay có khả năng mưa, đừng quên mang theo ô/áo mưa!")
        elif now.hour < 19:
            tips.append("☂️ Chiều tối nay có thể có mưa, chú ý chuẩn bị áo mưa khi đi làm về.")

    # 4. Nhiệt độ & oi bức
    if feels >= 38 or temp >= 35:
        tips.append("🥵 Trời rất oi bức gay gắt, uống nhiều nước và tránh ở ngoài trời quá lâu.")
    elif temp >= 32:
        tips.append("😓 Trời khá nóng, nên chọn trang phục thoáng mát.")
    elif temp <= 16:
        tips.append("🧥 Trời rét buốt, nhớ giữ ấm cơ thể khi ra ngoài!")

    # 5. Độ ẩm & Gió
    if humidity >= 85 and temp >= 28:
        tips.append("💦 Độ ẩm cao trên 85%, cảm giác ngột ngạt khó chịu.")
    if wind_spd >= 40:
        tips.append("💨 Gió giật mạnh, cẩn thận cây đổ hoặc vật rơi khi di chuyển.")

    if not tips:
        tips.append("Thời tiết thuận lợi, chúc bạn một ngày tốt lành!")

    return "\n".join(tips)


# ──────────────────────────────────────────
# ĐỊNH DẠNG TIN NHẮN TỔNG HỢP
# ──────────────────────────────────────────

def format_message(data: dict) -> str:
    """Tạo nội dung tin nhắn thời tiết hoàn chỉnh gửi Telegram."""
    now = datetime.now(TIMEZONE)
    weekdays_vi = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm",
                   "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
    weekday = weekdays_vi[now.weekday()]
    date_str = now.strftime(f"{weekday}, %d/%m/%Y")

    current = data["current"]
    main    = current["main"]
    weather = current["weather"][0]
    wind    = current["wind"]

    temp      = round(main["temp"])
    feels     = round(main["feels_like"])
    humidity  = main["humidity"]
    wind_spd  = round(wind["speed"] * 3.6)
    wind_dir  = format_wind_direction(wind.get("deg", 0))
    desc      = weather["description"].capitalize()
    icon      = weather_emoji(desc, weather["icon"])

    # 1. Chất lượng không khí
    air_info = parse_air_quality(data.get("air", {}))

    # 2. Dự báo trong ngày (6h hoặc 3h)
    intraday_text = format_intraday_forecast(data.get("forecast", {}), now)

    # 3. Dự báo 3 ngày tới
    three_days = parse_3day_forecast(data.get("forecast", {}), now)
    three_days_lines = "\n".join(d["line"] for d in three_days)

    # 4. Lời khuyên
    advice = get_advice(data, air_info, three_days, now)

    greeting_title = "DỰ BÁO THỜI TIẾT HÀ NỘI"
    if now.hour < 10:
        greeting_title = "DỰ BÁO BUỔI SÁNG HÀ NỘI"
    elif now.hour < 14:
        greeting_title = "CẬP NHẬT THỜI TIẾT TRƯA HÀ NỘI"

    message = f"""
🌤️ *{greeting_title}*
📅 {date_str} | ⏰ {now.strftime("%H:%M")}

{icon} *{desc}*
🌡️ Nhiệt độ: *{temp}°C* (cảm giác như {feels}°C)
💧 Độ ẩm: {humidity}% | 🌬️ Gió: {wind_spd} km/h ({wind_dir})
🌫️ Không khí: {air_info['summary']}

{intraday_text}

📅 *DỰ BÁO 3 NGÀY TỚI:*
{three_days_lines}

💡 *Lời Khuyên:*
{advice}

━━━━━━━━━━━━━━━━━━━━
🤖 _Hà Nội Weather Bot_
""".strip()

    return message


# ──────────────────────────────────────────
# GỬI TIN NHẮN TELEGRAM
# ──────────────────────────────────────────

def send_telegram(message: str) -> None:
    """Gửi tin nhắn đến Telegram Chat."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()
    print(f"✅ Đã gửi tin nhắn Telegram thành công! (status: {resp.status_code})")


# ──────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────

def main():
    missing = [
        var for var in ["OPENWEATHER_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
        if not os.environ.get(var)
    ]
    if missing:
        raise EnvironmentError(
            f"❌ Thiếu biến môi trường: {', '.join(missing)}\n"
            "Vui lòng thêm vào GitHub Secrets hoặc file .env"
        )

    print("🌍 Đang lấy dữ liệu thời tiết & chất lượng không khí Hà Nội...")
    weather_data = get_weather_data()

    print("📝 Đang tạo định dạng tin nhắn...")
    message = format_message(weather_data)
    print("\n--- Nội dung tin nhắn chuẩn bị gửi ---")
    print(message)
    print("--------------------------------------\n")

    print("📤 Đang gửi đến Telegram...")
    send_telegram(message)


if __name__ == "__main__":
    main()
