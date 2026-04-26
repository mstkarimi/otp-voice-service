# راهنمای عملیاتی (Operations)

## مدیریت سرویس

```bash
# وضعیت
systemctl status otp-service

# شروع
systemctl start otp-service

# توقف
systemctl stop otp-service

# راه‌اندازی مجدد
systemctl restart otp-service

# لاگ زنده
journalctl -u otp-service -f

# لاگ ۱۰۰ خط آخر
journalctl -u otp-service -n 100

# لاگ از زمان خاص
journalctl -u otp-service --since "2024-01-01 00:00:00"
```

---

## فایل‌های لاگ

```bash
# لاگ اصلی (rotating)
tail -f /var/log/otp-service/otp-service.log

# همه لاگ‌ها
ls -lh /var/log/otp-service/
```

---

## تغییر API Key

```bash
# ۱. تولید کلید جدید
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# ۲. hash کردن
/opt/otp-service/venv/bin/python -c "
from passlib.context import CryptContext
ctx = CryptContext(schemes=['bcrypt'], deprecated='auto')
print(ctx.hash('NEW_API_KEY_HERE'))
"

# ۳. ویرایش config
nano /etc/otp-service/config.yaml
# api_key_hash را با مقدار جدید جایگزین کنید

# ۴. راه‌اندازی مجدد
systemctl restart otp-service
```

---

## اضافه کردن IP به Whitelist

در فایل `/etc/otp-service/config.yaml`:

```yaml
api:
  ip_whitelist:
    - "127.0.0.1"
    - "192.168.1.100"     # ← IP جدید
    - "192.168.2.0/24"    # ← یا محدوده
```

سپس:
```bash
systemctl restart otp-service
```

---

## مانیتورینگ تماس‌های فعال

```bash
# از طریق API
curl http://127.0.0.1:8080/api/v1/health

# از طریق Asterisk
asterisk -rx "core show channels"
asterisk -rx "core show calls"
```

---

## مشاهده آمار database

```bash
# تعداد کل رکوردها
sqlite3 /var/lib/otp-service/otp.db "SELECT status, COUNT(*) FROM otp_calls GROUP BY status;"

# رکوردهای ۱ ساعت اخیر
sqlite3 /var/lib/otp-service/otp.db "
SELECT mobile, status, datetime(created_at, 'unixepoch', 'localtime') as time
FROM otp_calls
WHERE created_at > strftime('%s','now','-1 hour')
ORDER BY created_at DESC LIMIT 20;
"
```

---

## پاک‌سازی database

```bash
# رکوردهای قدیمی‌تر از ۷ روز
sqlite3 /var/lib/otp-service/otp.db "
DELETE FROM otp_calls WHERE created_at < strftime('%s','now','-7 days');
VACUUM;
"
```

---

## بروزرسانی سرویس

```bash
# ۱. آپلود کد جدید
scp -r otp-voice-service/src/ root@SERVER_IP:/opt/otp-service/

# ۲. تنظیم ownership
chown -R otp-service:otp-service /opt/otp-service/src/

# ۳. راه‌اندازی مجدد
systemctl restart otp-service
```

---

## Rollback کامل

```bash
# اگر مشکل داشتید
bash /root/otp-voice-service/uninstall.sh

# بازگشت backup Asterisk
cp /root/otp-backup-YYYYMMDD_HHMMSS/extensions_custom.conf /etc/asterisk/
cp /root/otp-backup-YYYYMMDD_HHMMSS/manager_custom.conf /etc/asterisk/
asterisk -rx "dialplan reload"
asterisk -rx "manager reload"
```
