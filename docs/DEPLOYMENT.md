# راهنمای استقرار (Deployment)

## پیش‌نیازها روی سرور Issabel

| مورد | وضعیت مورد نیاز |
|------|----------------|
| CentOS + Issabel PBX | ✅ |
| Asterisk 13+ | ✅ (سرور: 16.7.0) |
| Python 3.6+ | ✅ (سرور: 3.6.8) |
| sox | ✅ (`/usr/bin/sox`) |
| systemd | ✅ |
| SIP Trunk فعال | ✅ (نام: 90004455) |

---

## مرحله ۱: آماده‌سازی روی لپ‌تاپ (آنلاین)

### ۱.۱ دانلود dependencies
```bash
cd otp-voice-service
bash download_deps.sh
```
این دستور پوشه `vendor/` را پر می‌کند.

### ۱.۲ تولید فایل‌های صوتی
```bash
bash prepare_sounds.sh
```
فایل‌های صوتی در پوشه `sounds/` ذخیره می‌شوند.

### ۱.۳ اعتبارسنجی صداها
```bash
bash validate_sounds.sh
```
باید خروجی `✅ همه فایل‌ها معتبرند` نمایش دهد.

### ۱.۴ تست پخش (اختیاری)
```bash
bash test_sounds.sh
```

---

## مرحله ۲: انتقال به سرور

```bash
# از لپ‌تاپ
scp -r otp-voice-service/ root@SERVER_IP:/root/

# یا با rsync (سریع‌تر)
rsync -avz otp-voice-service/ root@SERVER_IP:/root/otp-voice-service/
```

---

## مرحله ۳: نصب روی سرور

```bash
# اتصال به سرور
ssh root@SERVER_IP

# وارد پوشه پروژه
cd /root/otp-voice-service

# اجرای نصب (با تایید دستی)
bash install.sh

# یا اجرای خودکار بدون توقف
bash install.sh --yes
```

### مراحل نصب خودکار:
1. چک prerequisites
2. Backup از `/etc/asterisk/extensions_custom.conf` و `manager_custom.conf`
3. ساخت user سرویس (`otp-service`)
4. ساخت virtualenv و نصب packages از `vendor/`
5. راه‌اندازی صداها
6. اضافه کردن AMI user به Asterisk
7. اضافه کردن dialplan
8. Reload Asterisk (فقط `dialplan reload` + `manager reload`)
9. تولید API Key و ایجاد `config.yaml`
10. نصب و راه‌اندازی systemd service
11. Health check نهایی
12. نمایش API Key

---

## مرحله ۴: تنظیمات SIP Trunk

فایل `/etc/otp-service/config.yaml` را ویرایش کنید:

```bash
nano /etc/otp-service/config.yaml
```

```yaml
asterisk:
  trunk: "90004455"       # ← نام SIP Trunk در Asterisk
  caller_id: "90004455"   # ← شماره نمایش داده شده
```

بعد از تغییر:
```bash
systemctl restart otp-service
```

---

## مرحله ۵: تست اولیه

### Health check:
```bash
curl http://127.0.0.1:8080/api/v1/health
```
باید خروجی زیر را نمایش دهد:
```json
{"api": "ok", "ami": "connected", "active_calls": 0, "available_channels": 20}
```

### تست تماس واقعی (با API Key از نصب):
```bash
curl -X POST http://127.0.0.1:8080/api/v1/otp/call \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"mobile": "09XXXXXXXXX", "code": "12345", "repeat": 2}'
```

### بررسی وضعیت dialplan:
```bash
asterisk -rx "dialplan show otp-playback-custom"
```

---

## مرحله ۶: فعال‌سازی دائمی سرویس

```bash
# سرویس از قبل توسط install.sh فعال شده
systemctl status otp-service

# در صورت نیاز
systemctl enable otp-service   # شروع خودکار با بوت
systemctl start otp-service    # شروع دستی
```

---

## نکات مهم

⚠️ **API Key فقط یک بار نمایش داده می‌شود** - آن را در جای امنی ذخیره کنید.

⚠️ **هرگز از `asterisk -rx "core restart"` استفاده نکنید** - فقط از reload های partial استفاده کنید.

✅ **Backup** قبل از نصب در `/root/otp-backup-YYYYMMDD_HHMMSS/` ذخیره می‌شود.
