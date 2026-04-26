# OTP Voice Call Service

سرویس ارسال کد تایید (OTP) از طریق **تماس صوتی** روی سرور Issabel/FreePBX/Asterisk.

> **ویژگی‌ها:** آفلاین · بدون هزینه پیامک · پشتیبانی کامل از فارسی · نصب خودکار

---

## معماری

```
Client App ──HTTP──▶ FastAPI :8080 ──AMI──▶ Asterisk ──SIP──▶ User Phone
```

| لایه | فناوری |
|------|--------|
| API | FastAPI + Uvicorn (Python 3.8+) |
| PBX | Asterisk 16+ (Issabel / FreePBX) |
| ارتباط PBX | panoramisk (AMI async) |
| ذخیره‌سازی | SQLite (async) |
| صداها | فارسی (ضبط‌شده با Edge TTS) |

---

## پیش‌نیازها

| نیاز | نسخه |
|------|------|
| سرور | CentOS 7 / RHEL 7 یا بالاتر |
| Asterisk | 16+ (روی Issabel / FreePBX) |
| Python | 3.8+ (روی سرور) |
| دسترسی | root SSH |
| اینترنت سرور | **نیاز نیست** — نصب آفلاین |

---

## نصب سریع

### مرحله ۱ — دانلود پروژه (روی لپ‌تاپ/PC با اینترنت)

```bash
git clone https://github.com/YOUR_USERNAME/otp-voice-service.git
cd otp-voice-service
```

### مرحله ۲ — دانلود packages آفلاین

```bash
bash download_deps.sh
```

این اسکریپت تمام packages مورد نیاز را در پوشه `vendor/` ذخیره می‌کند.

### مرحله ۳ — انتقال به سرور

```bash
scp -r otp-voice-service/ root@YOUR_SERVER_IP:/root/
```

### مرحله ۴ — نصب روی سرور

```bash
ssh root@YOUR_SERVER_IP
cd /root/otp-voice-service
bash install.sh
```

پس از نصب، **API Key** یک‌بار نمایش داده می‌شود — آن را ذخیره کنید.

### مرحله ۵ — تست

```bash
# Health check
curl http://127.0.0.1:8080/api/v1/health

# تماس OTP
curl -X POST http://127.0.0.1:8080/api/v1/otp/call \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"mobile":"09123456789","code":"1234"}'
```

---

## ساختار پروژه

```
otp-voice-service/
├── src/                    # سورس‌کد Python
│   ├── main.py             # FastAPI entrypoint
│   ├── config.py           # بارگذاری config.yaml
│   ├── api/
│   │   ├── auth.py         # احراز هویت (X-API-Key / Bearer)
│   │   ├── routes.py       # endpoints
│   │   └── schemas.py      # Pydantic models
│   ├── ami/
│   │   ├── client.py       # اتصال به Asterisk AMI
│   │   └── originator.py   # شروع تماس
│   ├── core/
│   │   ├── rate_limiter.py # محدودیت تماس
│   │   ├── validator.py    # اعتبارسنجی موبایل/کد
│   │   └── logger.py       # لاگ‌گذاری
│   └── storage/
│       └── db.py           # SQLite async
├── asterisk/
│   ├── extensions_custom.conf  # Dialplan (append به سرور)
│   └── manager_custom.conf     # AMI user template
├── systemd/
│   └── otp-service.service     # systemd unit
├── sounds/                 # فایل‌های صوتی فارسی (WAV 8kHz Mono)
│   ├── otp-intro.wav
│   ├── otp-repeat.wav
│   ├── otp-goodbye.wav
│   ├── otp-error.wav
│   └── digits/0.wav … 9.wav
├── config/
│   └── config.example.yaml # نمونه تنظیمات
├── tools/                  # ابزارهای کمکی توسعه
│   ├── deploy.py           # استقرار SSH از لپ‌تاپ
│   ├── gen_sounds_edge.py  # تولید صداهای فارسی
│   └── ...
├── tests/                  # تست‌ها
├── install.sh              # نصب خودکار
├── uninstall.sh            # حذف کامل
└── download_deps.sh        # دانلود packages آفلاین
```

---

## تنظیمات

فایل `config.example.yaml` را کپی کرده و ویرایش کنید:

```bash
cp config/config.example.yaml /etc/otp-service/config.yaml
```

مهم‌ترین تنظیمات:

```yaml
api:
  api_key_hash: "..."    # توسط install.sh ساخته می‌شود

asterisk:
  trunk: "YOUR_SIP_TRUNK"    # شماره SIP Trunk
  caller_id: "YOUR_NUMBER"   # شماره نمایش به کاربر

rate_limit:
  per_number_calls: 3        # حداکثر تماس به یک شماره در 10 دقیقه
  max_concurrent_calls: 20   # حداکثر تماس همزمان
```

---

## API

سه endpoint اصلی:

| Method | Path | توضیح |
|--------|------|-------|
| GET | `/api/v1/health` | وضعیت سرویس |
| POST | `/api/v1/otp/call` | شروع تماس OTP |
| GET | `/api/v1/otp/status/{id}` | وضعیت تماس |

مستندات کامل: [API_DOCS.md](API_DOCS.md)

### نمونه درخواست

```bash
curl -X POST http://SERVER:8080/api/v1/otp/call \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"mobile":"09123456789","code":"5847","repeat":2}'
```

```json
{
  "request_id": "d78ed57f-38a7-4634-986d-fa2228af429b",
  "status": "queued",
  "estimated_time": 5
}
```

---

## مدیریت سرویس

```bash
systemctl status otp-service      # وضعیت
systemctl restart otp-service     # راه‌اندازی مجدد
journalctl -u otp-service -f      # لاگ زنده
```

---

## تولید صداهای فارسی (اختیاری)

صداهای پیش‌فرض پروژه با [Edge TTS](https://github.com/rany2/edge-tts) ساخته شده‌اند.
برای بازسازی:

```bash
pip install edge-tts
# ffmpeg هم لازم است
python tools/gen_sounds_edge.py
```

---

## Rate Limiting

| محدودیت | مقدار پیش‌فرض |
|---------|--------------|
| هر شماره | ۳ تماس در ۱۰ دقیقه |
| همزمان | ۲۰ تماس |
| ساعتی | ۵۰۰ تماس |

قابل تنظیم در `config.yaml`.

---

## حذف (Uninstall)

```bash
bash uninstall.sh
```

---

## License

MIT
