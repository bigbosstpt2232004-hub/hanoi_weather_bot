"""
Weather Alert Bot - Giám sát và cảnh báo thời tiết bất thường tại Hà Nội
Chạy tự động mỗi 1.5 giờ qua GitHub Actions.
Chỉ gửi tin nhắn Telegram khi phát hiện thiên tai / hiểm họa nguy hiểm.
"""

import os
import json
import requests
from datetime import datetime
import pytz

# ──────────────────────────────────────────
# CẤU HÌNH
# ──────────────────────────────────────────
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY")
TELEGRAM_BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID    = os.environ.get("TELEGRAM_CHAT_ID")

LAT = 21.0285
LON = 105.8542
TIMEZONE = pytz.timezone("Asia/Ho_Chi_Minh")

# File lưu trạng thái để tránh spam liên tục khi bão kéo dài
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alert_state.json")
COOLDOWN_HOURS = 3.5  # Khoảng cách tối thiểu giữa 2 lần cảnh báo cùng loại (tiếng)


def get_weather_data() -> dict:
    """Lấy dữ liệu thời tiết tức thời, dự báo ngắn và chất lượng không khí."""
    base_url = "https://api.openweathermap.org/data/2.5"
    params = {"lat": LAT, "lon": LON, "appid": OPENWEATHER_API_KEY}

    # 1. Thời tiết hiện tại
    current_resp = requests.get(
        f"{base_url}/weather",
        params={**params, "units": "metric", "lang": "vi"},
        timeout=10,
    )
    current_resp.raise_for_status()
    current = current_resp.json()

    # 2. Dự báo 4 mốc kế tiếp (khoảng 12 giờ tới)
    forecast_resp = requests.get(
        f"{base_url}/forecast",
        params={**params, "units": "metric", "lang": "vi", "cnt": 4},
        timeout=10,
    )
    forecast_resp.raise_for_status()
    forecast = forecast_resp.json()

    # 3. Chất lượng không khí
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


def detect_threats(data: dict) -> list:
    """Kiểm tra các ngưỡng thiên tai, bão lũ, thời tiết cực đoan tại Hà Nội."""
    threats = []
    current = data.get("current", {})
    weather_id = current.get("weather", [{}])[0].get("id", 0)
    wind_spd = current.get("wind", {}).get("speed", 0) * 3.6
    wind_gust = current.get("wind", {}).get("gust", 0) * 3.6
    rain_1h = current.get("rain", {}).get("1h", 0.0)
    feels_like = current.get("main", {}).get("feels_like", 25)
    temp = current.get("main", {}).get("temp", 25)

    # 1. Dông bão / Lốc xoáy / Gió giật mạnh
    if (200 <= weather_id <= 232) or wind_gust >= 50 or wind_spd >= 40 or weather_id in [771, 781]:
        peak_wind = round(max(wind_gust, wind_spd))
        threats.append({
            "type": "STORM",
            "title": "⛈️ DÔNG LỐC & GIÓ GIẬT NGUY HIỂM",
            "detail": f"Gió giật cực đại: {peak_wind} km/h. Sấm sét, dông lốc mạnh.",
            "guide": (
                "• Hạn chế ra đường, tránh xa cây cổ thụ, cột điện, biển quảng cáo lớn.\n"
                "• Tìm nơi trú ẩn an toàn, ngắt các thiết bị điện ngoài trời."
            )
        })

    # 2. Mưa rất lớn / Nguy cơ ngập úng diện rộng
    forecast_rain_3h = 0.0
    forecast_list = data.get("forecast", {}).get("list", [])
    if forecast_list:
        forecast_rain_3h = forecast_list[0].get("rain", {}).get("3h", 0.0)

    if rain_1h >= 25 or forecast_rain_3h >= 35 or weather_id in [502, 503, 504]:
        total_m = max(rain_1h, forecast_rain_3h)
        threats.append({
            "type": "FLOOD",
            "title": "🌊 MƯA LỚN - NGUY CƠ NGẬP ÚNG DIỆN RỘNG",
            "detail": f"Lượng mưa đo được/dự báo: ~{round(total_m, 1)} mm. Mưa như trút nước.",
            "guide": (
                "• Đề phòng ngập sâu tại các tuyến phố trũng thấp của Hà Nội.\n"
                "• Chú ý các miệng cống ngập nước, thận trọng khi điều khiển phương tiện."
            )
        })

    # 3. Nhiệt độ cực đoan (Sốc nhiệt / Rét đậm)
    if feels_like >= 42 or temp >= 39:
        threats.append({
            "type": "HEATWAVE",
            "title": "🥵 NẮNG NÓNG ĐẶC BIỆT GAY GẮT",
            "detail": f"Nhiệt độ cảm giác thực tế: {round(feels_like)}°C. Nguy cơ sốc nhiệt cao.",
            "guide": (
                "• Tránh làm việc ngoài trời trong khoảng 11h - 16h.\n"
                "• Bổ sung nước và chất điện giải liên tục."
            )
        })
    elif temp <= 10:
        threats.append({
            "type": "COLD",
            "title": "🥶 RÉT ĐẬM - RÉT HẠI NGUY HIỂM",
            "detail": f"Nhiệt độ ngoài trời giảm sâu còn {round(temp)}°C.",
            "guide": (
                "• Giữ ấm toàn diện (cổ, ngực, bàn chân) đặc biệt với người già và trẻ nhỏ."
            )
        })

    # 4. Bụi mịn PM2.5 ở mức nguy hại
    air_list = data.get("air", {}).get("list", [])
    if air_list:
        pm2_5 = air_list[0].get("components", {}).get("pm2_5", 0)
        aqi = air_list[0].get("main", {}).get("aqi", 0)
        if aqi == 5 or pm2_5 >= 150:
            threats.append({
                "type": "POLLUTION",
                "title": "🟣 Ô NHIỄM KHÔNG KHÍ Ở MỨC NGUY HẠI",
                "detail": f"Chỉ số AQI: {aqi} | Bụi mịn PM2.5: {round(pm2_5, 1)} µg/m³ (Rất độc hại).",
                "guide": (
                    "• Hạn chế tối đa các hoạt động thể dục, làm việc ngoài trời.\n"
                    "• Bắt buộc đeo khẩu trang chuyên dụng (N95/KN95) khi phải ra ngoài."
                )
            })

    # 5. Khí áp tụt sâu (Tâm bão / Áp thấp nhiệt đới áp sát)
    pressure = current.get("main", {}).get("pressure", 1013)
    if pressure <= 998 and (wind_spd >= 25 or rain_1h > 0 or forecast_rain_3h > 0):
        threats.append({
            "type": "LOW_PRESSURE",
            "title": "🌀 TÂM BÃO / ÁP THẤP NHIỆT ĐỚI ÁP SÁT",
            "detail": f"Khí áp tụt sâu còn {pressure} hPa (Bình thường ~1013 hPa). Vùng tâm bão đang ảnh hưởng trực tiếp.",
            "guide": (
                "• Theo dõi sát các bản tin khẩn cấp từ Trung tâm Dự báo KTTV Quốc gia.\n"
                "• Chằng chống cửa sổ, mái tôn, kiểm tra ban công đề phòng gió lốc giật đổ.\n"
                "• Sạc đầy điện thoại, dự phòng đèn pin và nước sạch phòng mất điện diện rộng."
            )
        })

    # 6. Sương mù dày đặc / Tầm nhìn cực kém
    visibility = current.get("visibility", 10000)
    if (visibility <= 1000 or weather_id == 741) and visibility > 0:
        vis_km = round(visibility / 1000, 1)
        threats.append({
            "type": "DENSE_FOG",
            "title": "🌫️ SƯƠNG MÙ DÀY ĐẶC - TẦM NHÌN NGUY HIỂM",
            "detail": f"Tầm nhìn xa giảm xuống dưới {vis_km} km. Mù mịt nghiêm trọng.",
            "guide": (
                "• Bật đèn sương mù/đèn chiếu gần, giảm tốc độ và giữ khoảng cách an toàn khi lái xe.\n"
                "• Đặc biệt cẩn trọng khi qua các cây cầu lớn (Nhật Tân, Thăng Long, Thanh Trì) và cao tốc Nội Bài."
            )
        })

    # 7. Mưa đá (Hail)
    desc = current.get("weather", [{}])[0].get("description", "").lower()
    if weather_id == 511 or "đá" in desc or "hail" in desc:
        threats.append({
            "type": "HAIL",
            "title": "🧊 CẢNH BÁO MƯA ĐÁ NGUY HIỂM",
            "detail": "Xuất hiện mưa đá kèm dông lốc mạnh cục bộ.",
            "guide": (
                "• Tuyệt đối không ở ngoài trời, tìm ngay nơi trú ẩn có mái che kiên cố (nhà bê tông).\n"
                "• Đề phòng thủng mái tôn, vỡ kính xe ô tô và cây đổ."
            )
        })

    return threats


def should_send_alert(threats: list) -> bool:
    """Kiểm tra thời gian giãn cách (cooldown) để tránh spam."""
    if not threats:
        return False

    if not os.path.exists(STATE_FILE):
        return True

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)

        last_time_str = state.get("last_alert_time")
        if not last_time_str:
            return True

        last_time = datetime.fromisoformat(last_time_str)
        now_utc = datetime.now(pytz.utc)
        hours_passed = (now_utc - last_time).total_seconds() / 3600

        # Nếu đã qua thời gian giãn cách -> gửi lại để cập nhật tình hình
        if hours_passed >= COOLDOWN_HOURS:
            return True

        # Nếu phát hiện thêm loại hiểm họa mới chưa có trong lần cảnh báo trước -> gửi ngay
        current_types = set(t["type"] for t in threats)
        last_types = set(state.get("threat_types", []))
        if not current_types.issubset(last_types):
            return True

        return False
    except Exception:
        return True


def save_alert_state(threats: list):
    """Lưu lại lịch sử cảnh báo gần nhất vào file JSON."""
    state = {
        "last_alert_time": datetime.now(pytz.utc).isoformat(),
        "threat_types": [t["type"] for t in threats],
    }
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️ Không thể lưu file trạng thái: {e}")


def build_alert_message(threats: list, data: dict) -> str:
    """Định dạng nội dung tin nhắn cảnh báo khẩn cấp gửi Telegram."""
    now = datetime.now(TIMEZONE)
    date_str = now.strftime("%H:%M | %d/%m/%Y")

    threat_sections = []
    for t in threats:
        threat_sections.append(
            f"*{t['title']}*\n"
            f"📍 {t['detail']}\n\n"
            f"🛡️ *Khuyến nghị an toàn:*\n{t['guide']}"
        )

    body = "\n\n━━━━━━━━━━━━━━━━━━━━\n\n".join(threat_sections)

    message = f"""
🚨 *CẢNH BÁO THỜI TIẾT KHẨN CẤP - HÀ NỘI*
⏰ Cập nhật: {date_str}

{body}

━━━━━━━━━━━━━━━━━━━━
🤖 _Hà Nội Weather Alert Bot_
""".strip()
    return message


def send_telegram(message: str) -> None:
    """Gửi cảnh báo khẩn cấp đến Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()
    print(f"🚨 ĐÃ PHÁT CẢNH BÁO KHẨN CẤP ĐẾN TELEGRAM! (Status: {resp.status_code})")


def main():
    missing = [
        var for var in ["OPENWEATHER_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
        if not os.environ.get(var)
    ]
    if missing:
        raise EnvironmentError(
            f"❌ Thiếu biến môi trường: {', '.join(missing)}\n"
            "Vui lòng thiết lập biến môi trường trước khi chạy."
        )

    print("🔍 Đang quét tình hình thời tiết và nguy cơ thiên tai tại Hà Nội...")
    data = get_weather_data()
    threats = detect_threats(data)

    if not threats:
        print("✅ Thời tiết Hà Nội hiện tại bình thường. Không có nguy cơ thiên tai.")
        return

    print(f"⚠️ Phát hiện {len(threats)} nguy cơ thời tiết bất thường!")

    if should_send_alert(threats):
        message = build_alert_message(threats, data)
        print("\n--- Nội dung cảnh báo ---")
        print(message)
        print("-------------------------\n")
        send_telegram(message)
        save_alert_state(threats)
    else:
        print("⏳ Cảnh báo cùng loại đã được gửi gần đây. Bỏ qua để tránh spam.")


if __name__ == "__main__":
    main()
