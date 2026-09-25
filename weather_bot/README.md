# 🌤️ Hà Nội Weather Bot

Bot tự động gửi thông báo thời tiết Hà Nội mỗi sáng lúc **6:00 AM** qua **Telegram**.

## Công Nghệ
- 🐍 **Python 3.11**
- ⚙️ **GitHub Actions** (lập lịch miễn phí)
- 🌦️ **OpenWeatherMap API** (free tier)
- 📱 **Telegram Bot API**

---

## Hướng Dẫn Cài Đặt

### Bước 1: Đăng ký OpenWeatherMap API Key

1. Truy cập [openweathermap.org](https://openweathermap.org/api)
2. Tạo tài khoản miễn phí → Vào **My API Keys**
3. Copy API Key của bạn

> ⏳ API key mới cần ~10 phút để kích hoạt

### Bước 2: Tạo Telegram Bot

1. Mở Telegram → Tìm **@BotFather**
2. Gõ `/newbot` → Làm theo hướng dẫn
3. Nhận **Bot Token** (dạng: `1234567890:ABCdef...`)
4. **Lấy Chat ID của bạn:**
   - Gửi bất kỳ tin nhắn nào cho bot vừa tạo
   - Truy cập URL sau (thay YOUR_TOKEN):
     ```
     https://api.telegram.org/botYOUR_TOKEN/getUpdates
     ```
   - Tìm trường `"id"` trong `"chat"` → Đó là Chat ID

### Bước 3: Tạo GitHub Repository & Thêm Secrets

1. Tạo repo mới trên GitHub (public hoặc private đều được)
2. Push toàn bộ code lên repo
3. Vào **Settings → Secrets and variables → Actions → New repository secret**
4. Thêm 3 secrets sau:

   | Secret Name | Giá trị |
   |---|---|
   | `OPENWEATHER_API_KEY` | API key từ Bước 1 |
   | `TELEGRAM_BOT_TOKEN` | Bot token từ Bước 2 |
   | `TELEGRAM_CHAT_ID` | Chat ID từ Bước 2 |

### Bước 4: Kích Hoạt & Test

1. Vào tab **Actions** trên GitHub
2. Chọn workflow **"🌤️ Hà Nội Weather Notification"**
3. Click **"Run workflow"** để test thủ công
4. Kiểm tra Telegram xem có nhận được tin nhắn không ✅

---

## Cấu Trúc Project

```
.
├── .github/
│   └── workflows/
│       └── weather_notify.yml   # Lập lịch GitHub Actions
└── weather_bot/
    ├── weather_bot.py           # Script chính
    └── requirements.txt         # Thư viện Python
```

---

## Lịch Chạy

- **Múi giờ**: Asia/Ho_Chi_Minh (UTC+7)
- **Thời gian**: 6:00 AM mỗi ngày
- **Cron UTC**: `0 23 * * *`

---

## Test Cục Bộ

```bash
# Cài thư viện
pip install -r weather_bot/requirements.txt

# Thiết lập biến môi trường
set OPENWEATHER_API_KEY=your_key_here
set TELEGRAM_BOT_TOKEN=your_token_here
set TELEGRAM_CHAT_ID=your_chat_id_here

# Chạy thử
python weather_bot/weather_bot.py
```
