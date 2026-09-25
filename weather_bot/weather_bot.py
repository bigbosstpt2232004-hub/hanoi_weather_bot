"""
Weather Bot - Thông báo thời tiết Hà Nội mỗi buổi sáng
Gửi qua Telegram Bot
"""

import os
import requests
from datetime import datetime
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
    """Lấy dữ liệu thời tiết hiện tại và dự báo từ OpenWeatherMap."""
    base_url = "https://api.openweathermap.org/data/2.5"

    # Thời tiết hiện tại
    current_resp = requests.get(
        f"{base_url}/weather",
        params={
            "lat": LAT,
            "lon": LON,
            "appid": OPENWEATHER_API_KEY,
            "units": "metric",
            "lang": "vi",
        },
        timeout=10,
    )
    current_resp.raise_for_status()
    current = current_resp.json()

    # Dự báo 5 ngày (mỗi 3 giờ) - lấy nhiều để đủ dữ liệu từ giờ hiện tại đến nửa đêm
    forecast_resp = requests.get(
        f"{base_url}/forecast",
        params={
            "lat": LAT,
            "lon": LON,
            "appid": OPENWEATHER_API_KEY,
            "units": "metric",
            "lang": "vi",
            "cnt": 16,  # lấy 48h để luôn đủ mốc từ bất kỳ giờ nào đến 23:59
        },
        timeout=10,
    )
    forecast_resp.raise_for_status()
    forecast = forecast_resp.json()

    return {"current": current, "forecast": forecast}


# ──────────────────────────────────────────
# HELPER: ICON & LỜI KHUYÊN
# ──────────────────────────────────────────

def weather_emoji(description: str, icon_code: str) -> str:
    """Chuyển mã icon OpenWeather thành emoji."""
    icon_map = {
        "01": "☀️",   # clear sky
        "02": "🌤️",  # few clouds
        "03": "⛅",   # scattered clouds
        "04": "☁️",   # broken/overcast clouds
        "09": "🌧️",  # shower rain
        "10": "🌦️",  # rain
        "11": "⛈️",   # thunderstorm
        "13": "❄️",   # snow
        "50": "🌫️",  # mist
    }
    prefix = icon_code[:2] if icon_code else "01"
    return icon_map.get(prefix, "🌡️")


def get_advice(data: dict) -> str:
    """Đưa ra lời khuyên dựa trên thời tiết."""
    desc = data["current"]["weather"][0]["description"].lower()
    temp = data["current"]["main"]["temp"]
    humidity = data["current"]["main"]["humidity"]
    wind = data["current"]["wind"]["speed"] * 3.6  # m/s → km/h

    tips = []

    if "mưa" in desc or "rain" in desc or "shower" in desc:
        tips.append("☂️ Đừng quên mang theo ô hôm nay!")
    if temp >= 35:
        tips.append("🥵 Trời rất nóng, uống nhiều nước và tránh nắng gắt.")
    elif temp >= 30:
        tips.append("😓 Nóng, nên mặc quần áo thoáng mát.")
    elif temp <= 15:
        tips.append("🧥 Trời lạnh, nhớ mặc áo ấm!")
    if humidity >= 85:
        tips.append("💦 Độ ẩm cao, có thể cảm giác ngột ngạt.")
    if wind >= 40:
        tips.append("💨 Gió mạnh, cẩn thận khi ra đường.")
    if "sương" in desc or "mist" in desc or "fog" in desc:
        tips.append("🌫️ Có sương mù, lái xe cẩn thận.")

    if not tips:
        tips.append("😊 Thời tiết dễ chịu, có một ngày tuyệt vời!")

    return "\n".join(tips)


def format_wind_direction(degrees: float) -> str:
    """Chuyển đổi góc gió sang hướng la bàn tiếng Việt."""
    directions = [
        "Bắc", "Đông Bắc", "Đông", "Đông Nam",
        "Nam", "Tây Nam", "Tây", "Tây Bắc"
    ]
    idx = round(degrees / 45) % 8
    return directions[idx]


# ──────────────────────────────────────────
# ĐỊNH DẠNG TIN NHẮN
# ──────────────────────────────────────────

def format_message(data: dict) -> str:
    """Tạo nội dung tin nhắn thời tiết đẹp."""
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
    wind_spd  = round(wind["speed"] * 3.6)  # m/s → km/h
    wind_dir  = format_wind_direction(wind.get("deg", 0))
    desc      = weather["description"].capitalize()
    icon      = weather_emoji(desc, weather["icon"])

    # Lọc dự báo: chỉ lấy các mốc từ giờ hiện tại đến 23:59 hôm nay
    midnight = now.replace(hour=23, minute=59, second=59, microsecond=0)
    forecast_items = [
        item for item in data["forecast"]["list"]
        if now <= datetime.fromtimestamp(item["dt"], tz=TIMEZONE) <= midnight
    ]

    forecast_lines = []
    for item in forecast_items:
        dt_local = datetime.fromtimestamp(item["dt"], tz=TIMEZONE)
        hour_str = dt_local.strftime("%H:%M")
        f_temp   = round(item["main"]["temp"])
        f_icon   = weather_emoji(
            item["weather"][0]["description"],
            item["weather"][0]["icon"]
        )
        f_pop    = round(item.get("pop", 0) * 100)  # % xác suất mưa
        rain_str = f" ({f_pop}% mưa)" if f_pop > 20 else ""
        forecast_lines.append(f"  {hour_str}  {f_icon} {f_temp}°C{rain_str}")

    forecast_text = "\n".join(forecast_lines)
    advice        = get_advice(data)

    # Xác suất mưa cao nhất trong phần còn lại của ngày
    max_rain_pop = max(
        (round(item.get("pop", 0) * 100) for item in forecast_items),
        default=0
    )

    message = f"""
🌤️ *DỰ BÁO THỜI TIẾT HÀ NỘI*
📅 {date_str} | ⏰ {now.strftime("%H:%M")}

{icon} *{desc}*
🌡️ Nhiệt độ: *{temp}°C* (cảm giác như {feels}°C)
💧 Độ ẩm: {humidity}%
🌬️ Gió: {wind_spd} km/h hướng {wind_dir}
🌧️ Xác suất mưa cao nhất: {max_rain_pop}%

📊 *Dự Báo Đến Nửa Đêm:*
{forecast_text}

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
    # Kiểm tra biến môi trường
    missing = [
        var for var in ["OPENWEATHER_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
        if not os.environ.get(var)
    ]
    if missing:
        raise EnvironmentError(
            f"❌ Thiếu biến môi trường: {', '.join(missing)}\n"
            "Vui lòng thêm vào GitHub Secrets hoặc file .env"
        )

    print(f"🌍 Đang lấy thông tin thời tiết Hà Nội...")
    weather_data = get_weather_data()

    print("📝 Đang định dạng tin nhắn...")
    message = format_message(weather_data)
    print("\n--- Nội dung tin nhắn ---")
    print(message)
    print("-------------------------\n")

    print("📤 Đang gửi đến Telegram...")
    send_telegram(message)


if __name__ == "__main__":
    main()
