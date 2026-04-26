# رفع اشکال (Troubleshooting)

## ۱. تماس برقرار نمی‌شود

### چک AMI connection:
```bash
# وضعیت health
curl http://127.0.0.1:8080/api/v1/health
# اگر "ami": "disconnected" بود:

# تست اتصال مستقیم به AMI
asterisk -rx "manager show connected"

# چک manager_custom.conf
grep -A 8 "\[otp_service\]" /etc/asterisk/manager_custom.conf

# reload manager
asterisk -rx "manager reload"

# لاگ سرویس
journalctl -u otp-service -n 50
```

### چک secret AMI:
```bash
# secret در config با manager باید یکسان باشد
grep "secret" /etc/otp-service/config.yaml
grep "secret" /etc/asterisk/manager_custom.conf
```

---

## ۲. خطای 503 - ظرفیت پر

```bash
# بررسی تماس‌های فعال Asterisk
asterisk -rx "core show calls"

# بررسی وضعیت SIP trunk
asterisk -rx "sip show peers"
asterisk -rx "sip show registry"

# اگر trunk offline است:
# ۱. در پنل Issabel وضعیت trunk را بررسی کنید
# ۲. نام trunk در config.yaml را چک کنید
grep "trunk" /etc/otp-service/config.yaml
```

---

## ۳. صدا پخش نمی‌شود (تماس برقرار می‌شود ولی سکوت)

```bash
# چک مسیر فایل‌های صوتی
ls -la /var/lib/asterisk/sounds/otp/
ls -la /var/lib/asterisk/sounds/otp/digits/

# چک permissions
stat /var/lib/asterisk/sounds/otp/otp-intro.wav
# باید asterisk:asterisk و حداقل 644 باشد

# چک dialplan
asterisk -rx "dialplan show otp-playback-custom"

# چک format فایل صوتی
soxi /var/lib/asterisk/sounds/otp/otp-intro.wav
# Sample Rate باید 8000 باشد

# اگر فایل‌ها مشکل دارند
cd /root/otp-voice-service
bash prepare_sounds.sh
bash install.sh --yes
```

---

## ۴. AMI Disconnect می‌شود

این سرویس reconnect خودکار دارد، اما اگر مشکل مداوم دارید:

```bash
# لاگ
journalctl -u otp-service -n 100 | grep -i "ami\|disconnect\|reconnect"

# چک writetimeout
grep "writetimeout" /etc/asterisk/manager_custom.conf
# باید 5000 یا بیشتر باشد

# چک firewall داخلی
iptables -L -n | grep 5038
# پورت 5038 از localhost باید باز باشد
```

---

## ۵. CPU بالا

```bash
# بررسی تعداد تماس‌های همزمان
curl http://127.0.0.1:8080/api/v1/health

# کاهش محدودیت همزمان اگر لازم است
nano /etc/otp-service/config.yaml
# rate_limit.max_concurrent_calls را کاهش دهید (مثلاً 10)
systemctl restart otp-service

# بررسی Asterisk
asterisk -rx "core show channels count"
```

---

## ۶. خطای نصب dependencies

```bash
# چک vendor
ls /root/otp-voice-service/vendor/

# اگر خالی بود، نصب آنلاین
/opt/otp-service/venv/bin/pip install -r /root/otp-voice-service/requirements.txt

# بررسی نسخه Python
python3 --version  # باید 3.6+
```

---

## ۷. سرویس راه‌اندازی نمی‌شود

```bash
# لاگ کامل
journalctl -u otp-service -n 100 --no-pager

# چک config
python3 -c "
import yaml
with open('/etc/otp-service/config.yaml') as f:
    print(yaml.safe_load(f))
"

# تست مستقیم
cd /opt/otp-service
OTP_CONFIG=/etc/otp-service/config.yaml \
  venv/bin/python -m uvicorn src.main:app --host 0.0.0.0 --port 8080
```

---

## ۸. دستورات عیب‌یابی سریع

```bash
# همه چیز یکجا
echo "=== Service Status ===" && systemctl status otp-service --no-pager
echo "=== Health ===" && curl -s http://127.0.0.1:8080/api/v1/health
echo "=== AMI ===" && asterisk -rx "manager show connected"
echo "=== Dialplan ===" && asterisk -rx "dialplan show otp-playback-custom" | head -20
echo "=== Sounds ===" && ls /var/lib/asterisk/sounds/otp/
echo "=== Last 20 logs ===" && journalctl -u otp-service -n 20 --no-pager
```
