# راهنمای API برای برنامه‌نویسان

## معرفی سرویس

سرویس OTP Voice Call یک REST API است که کد تایید (OTP) را از طریق تماس صوتی به کاربران ارسال می‌کند. سرویس روی سرور Issabel/Asterisk اجرا می‌شود و از طریق HTTP قابل دسترسی است.

**آدرس پایه:** `http://SERVER_IP:8080/api/v1`

---

## احراز هویت

همه درخواست‌ها (به جز `/health`) نیاز به API Key دارند:

```
Authorization: Bearer YOUR_API_KEY
```

API Key را در زمان نصب از ادمین بگیرید.

---

## Endpoints

### ۱. ارسال کد OTP

```
POST /api/v1/otp/call
```

**هدرها:**
```
Authorization: Bearer YOUR_API_KEY
Content-Type: application/json
```

**بدنه درخواست:**
```json
{
  "mobile": "09123456789",
  "code": "12345",
  "repeat": 2
}
```

| فیلد | نوع | اجباری | توضیح |
|------|-----|--------|-------|
| `mobile` | string | ✅ | شماره موبایل ایرانی |
| `code` | string | ✅ | کد OTP (۴ تا ۸ رقم) |
| `repeat` | integer | ❌ | تعداد تکرار (پیش‌فرض: ۲، حداکثر: ۳) |

**فرمت‌های معتبر موبایل:**
- `09123456789`
- `+989123456789`
- `00989123456789`

**پاسخ موفق (202):**
```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "estimated_time": 5
}
```

---

### ۲. بررسی وضعیت تماس

```
GET /api/v1/otp/status/{request_id}
```

**پاسخ:**
```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "duration": 18,
  "hangup_cause": "NORMAL_CLEARING"
}
```

**مقادیر `status`:**
| وضعیت | معنی |
|-------|------|
| `queued` | در صف انتظار |
| `ringing` | در حال زنگ زدن |
| `completed` | موفق - کاربر پاسخ داد |
| `failed` | شکست خورده |

---

### ۳. وضعیت سلامت سرویس

```
GET /api/v1/health
```

نیاز به Authentication ندارد.

**پاسخ:**
```json
{
  "api": "ok",
  "ami": "connected",
  "active_calls": 3,
  "available_channels": 17
}
```

---

## کدهای خطا

| کد HTTP | معنی | راه‌حل |
|---------|------|--------|
| 400 | داده ورودی نامعتبر | فرمت موبایل یا کد را بررسی کنید |
| 401 | API Key نامعتبر | کلید API را بررسی کنید |
| 404 | request_id یافت نشد | ID را بررسی کنید |
| 422 | Validation Error | ساختار JSON را بررسی کنید |
| 429 | Rate Limit | بعد از چند دقیقه دوباره تلاش کنید |
| 503 | ظرفیت پر است | بعد از چند ثانیه دوباره تلاش کنید |

---

## محدودیت‌ها (Rate Limits)

- **Per Number:** حداکثر ۳ تماس به یک شماره در ۱۰ دقیقه
- **همزمان:** حداکثر ۲۰ تماس همزمان در کل سیستم
- **ساعتی:** حداکثر ۵۰۰ تماس در ساعت

---

## نمونه کد

### curl

```bash
# ارسال OTP
curl -X POST http://SERVER_IP:8080/api/v1/otp/call \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"mobile": "09123456789", "code": "12345", "repeat": 2}'

# بررسی وضعیت
curl http://SERVER_IP:8080/api/v1/otp/status/REQUEST_ID \
  -H "Authorization: Bearer YOUR_API_KEY"

# health check
curl http://SERVER_IP:8080/api/v1/health
```

### Python

```python
import requests

BASE_URL = "http://SERVER_IP:8080/api/v1"
API_KEY = "YOUR_API_KEY"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

def send_otp(mobile: str, code: str, repeat: int = 2) -> str:
    resp = requests.post(
        f"{BASE_URL}/otp/call",
        json={"mobile": mobile, "code": code, "repeat": repeat},
        headers=HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["request_id"]

def check_status(request_id: str) -> dict:
    resp = requests.get(
        f"{BASE_URL}/otp/status/{request_id}",
        headers=HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()

# استفاده
import time

request_id = send_otp("09123456789", "12345")
print(f"تماس در صف: {request_id}")

# بررسی وضعیت تا ۳۰ ثانیه
for _ in range(6):
    time.sleep(5)
    status = check_status(request_id)
    print(f"وضعیت: {status['status']}")
    if status["status"] in ("completed", "failed"):
        break
```

### PHP

```php
<?php

$BASE_URL = "http://SERVER_IP:8080/api/v1";
$API_KEY  = "YOUR_API_KEY";

function sendOtp(string $mobile, string $code, int $repeat = 2): string {
    global $BASE_URL, $API_KEY;
    
    $ch = curl_init("$BASE_URL/otp/call");
    curl_setopt_array($ch, [
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => json_encode([
            "mobile" => $mobile,
            "code"   => $code,
            "repeat" => $repeat,
        ]),
        CURLOPT_HTTPHEADER => [
            "Authorization: Bearer $API_KEY",
            "Content-Type: application/json",
        ],
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => 10,
    ]);
    
    $result = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    
    if ($httpCode !== 202) {
        throw new RuntimeException("خطا: HTTP $httpCode - $result");
    }
    
    return json_decode($result, true)["request_id"];
}

// استفاده
$requestId = sendOtp("09123456789", "12345");
echo "تماس در صف: $requestId\n";
```

---

## سناریوی کامل: ثبت‌نام با تایید موبایل

```python
import requests, time, random

BASE_URL = "http://SERVER_IP:8080/api/v1"
HEADERS = {"Authorization": "Bearer YOUR_API_KEY"}

def register_with_otp(mobile: str) -> bool:
    # ۱. تولید کد OTP
    otp_code = str(random.randint(10000, 99999))

    # ۲. ارسال تماس
    try:
        resp = requests.post(f"{BASE_URL}/otp/call",
            json={"mobile": mobile, "code": otp_code},
            headers=HEADERS, timeout=10)

        if resp.status_code == 429:
            print("تعداد درخواست زیاد است، بعداً تلاش کنید")
            return False

        resp.raise_for_status()
        request_id = resp.json()["request_id"]

    except requests.RequestException as e:
        print(f"خطا در ارسال: {e}")
        return False

    # ۳. ذخیره کد در session/database برای بررسی بعدی
    # session["otp_code"] = otp_code
    # session["otp_request_id"] = request_id
    # session["otp_mobile"] = mobile

    print(f"کد OTP به {mobile} ارسال شد (request: {request_id})")
    return True


def verify_otp(mobile: str, entered_code: str, saved_code: str, request_id: str) -> bool:
    # ۴. بررسی کد وارد شده
    if entered_code != saved_code:
        return False

    # ۵. اختیاری: بررسی وضعیت تماس
    try:
        resp = requests.get(f"{BASE_URL}/otp/status/{request_id}",
            headers=HEADERS, timeout=10)
        status = resp.json()["status"]
        if status == "failed":
            print("تماس برقرار نشد - کد را مجدداً ارسال کنید")
            return False
    except Exception:
        pass  # اگر status check شکست خورد، کد صحیح را قبول کنیم

    return True
```

---

## سوالات متداول

**چقدر طول می‌کشد تا تماس برقرار شود؟**
معمولاً ۳ تا ۱۰ ثانیه، بسته به وضعیت شبکه SIP.

**اگر کاربر جواب نداد چه اتفاقی می‌افتد؟**
بعد از ۳۰ ثانیه، تماس قطع می‌شود و status به `failed` تغییر می‌کند.

**چند بار می‌توان به یک شماره زنگ زد؟**
حداکثر ۳ بار در ۱۰ دقیقه.

**آیا سرویس همیشه در دسترس است؟**
از طریق endpoint `/health` می‌توان وضعیت را بررسی کرد.
