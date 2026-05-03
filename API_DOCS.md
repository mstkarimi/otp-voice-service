# OTP Voice Call Service — API Reference (v1.1)

سرویس ارسال کد تایید از طریق تماس صوتی، با پشتیبانی کامل از وضعیت‌گیری دقیق و retry.

---

## Base URL

```
http://YOUR_SERVER_IP:8080
```

---

## Authentication

دو روش پشتیبانی می‌شود:

```http
X-API-Key: YOUR_API_KEY
```
یا
```http
Authorization: Bearer YOUR_API_KEY
```

---

## Endpoints

### 1. `GET /api/v1/health`

بدون احراز هویت.

```json
{ "api": "ok", "ami": "connected", "active_calls": 0, "available_channels": 20 }
```

---

### 2. `POST /api/v1/otp/call`

شروع تماس OTP.

**Body:**
```json
{ "mobile": "09123456789", "code": "1234", "repeat": 2 }
```

| فیلد | نوع | اجباری | توضیح |
|------|-----|--------|-------|
| `mobile` | string | ✅ | فرمت `09XXXXXXXXX` |
| `code` | string | ✅ | ۴ تا ۸ رقم |
| `repeat` | int | ❌ | بین ۱ تا ۳ (پیش‌فرض ۲) |

**Response `202`:**
```json
{ "request_id": "d78ed57f-...", "status": "queued", "estimated_time": 5 }
```

> پاسخ ۲۰۲ یعنی درخواست ثبت شد — برای دانستن نتیجه واقعی، endpoint بعدی را poll کنید.

---

### 3. `GET /api/v1/otp/status/{request_id}` ⭐ (به‌روزرسانی شده)

وضعیت کامل تماس **با timeline** و فلگ‌های تصمیم‌گیری.

**Response `200`:**
```json
{
  "request_id": "d78ed57f-38a7-4634-986d-fa2228af429b",
  "status": "completed",
  "mobile": "09123456789",

  "is_terminal": true,
  "is_answered": true,
  "can_retry": false,
  "retry_count": 0,
  "parent_request_id": null,

  "duration": null,
  "hangup_cause": "16 Normal Clearing",
  "asterisk_reason": "4",
  "created_at": 1777791629.22,
  "updated_at": 1777791637.00,

  "timeline": [
    { "at": 1777791629.22, "event": "queued",             "detail": null },
    { "at": 1777791629.23, "event": "originating",        "detail": null },
    { "at": 1777791630.10, "event": "ringing",            "detail": "channel=SIP/90004455-00001" },
    { "at": 1777791634.50, "event": "answered",           "detail": "channel=SIP/90004455-00001" },
    { "at": 1777791634.55, "event": "dialplan_start",     "detail": "channel=SIP/90004455-00001" },
    { "at": 1777791635.50, "event": "playing",            "detail": null },
    { "at": 1777791644.00, "event": "playback_complete",  "detail": null },
    { "at": 1777791644.10, "event": "hangup",             "detail": "cause=16 (Normal Clearing) channel=SIP/90004455-00001" }
  ]
}
```

#### مقادیر `status`

| status | معنی | کاربرد |
|--------|------|--------|
| `queued` | در صف داخلی، هنوز به Asterisk نرفته | وضعیت اولیه |
| `originating` | دستور به Asterisk فرستاده شد، در حال اقدام | حالت گذرا |
| `ringing` | در حال زنگ خوردن | کاربر تلفن را نگرفته |
| `answered` | کاربر جواب داد ✅ | تماس برقرار شد |
| `playing` | OTP در حال پخش است | وسط پخش |
| `completed` | OTP کامل پخش شد و قطع شد ✅✅ | موفقیت کامل |
| `no_answer` | زنگ خورد ولی جواب نداد | قابل retry |
| `busy` | خط کاربر اشغال است | قابل retry |
| `congestion` | خطوط مخابراتی شلوغ یا شماره/ترانک مشکل دارد | قابل retry |
| `unreachable` | شماره در دسترس نیست | قابل retry |
| `rejected` | کاربر تماس را رد کرد | قابل retry |
| `failed` | خطای فنی (شبکه، AMI، ...) | قابل retry |
| `cancelled` | تماس لغو شد | terminal |

#### فلگ‌های راهنما

| فیلد | معنی |
|------|------|
| `is_terminal` | اگر `true` بود، وضعیت دیگر تغییر نمی‌کند — می‌توانید stop poll کنید |
| `is_answered` | اگر `true` بود، یعنی کاربر **در یک نقطه‌ای** پاسخ داد (حتی اگر بعدا قطع شد) |
| `can_retry` | اگر `true` بود، می‌توانید retry بزنید |
| `retry_count` | چند بار این درخواست retry شده |
| `parent_request_id` | اگر این یک retry بود، ID درخواست اصلی |

#### مقادیر `event` در timeline

| event | منبع | معنی |
|-------|------|------|
| `queued` | API | درخواست ثبت شد |
| `originating` | API | دستور به Asterisk رفت |
| `originate_response` | Asterisk | پاسخ ابتدایی به Originate |
| `ringing` | Asterisk | کانال در حال زنگ |
| `answered` | Asterisk | کانال up شد (جواب داد) |
| `dialplan_start` | dialplan | کنترل به اسکریپت پخش OTP رسید |
| `playing` | dialplan | شروع پخش پیام |
| `playback_complete` | dialplan | پخش OTP تمام شد |
| `hangup` | Asterisk | تماس قطع شد (با cause code) |
| `failed` | API | شکست داخلی |

---

### 4. `POST /api/v1/otp/call/{request_id}/retry` ⭐ (جدید)

تکرار یک تماس قبلی. فقط روی درخواست‌های با `can_retry: true` کار می‌کند.

**Body (همه فیلدها اختیاری):**
```json
{
  "code": "9999",   // اختیاری: کد جدید. اگر ندید، همان کد قبلی استفاده می‌شود
  "repeat": 3       // اختیاری: تعداد تکرار جدید
}
```

**Response `202`:**
```json
{ "request_id": "NEW-UUID", "status": "queued", "estimated_time": 5 }
```

> تماس جدید با `parent_request_id = ID_قبلی` ساخته می‌شود و `retry_count` در درخواست والد افزایش می‌یابد.

**خطاهای ممکن:**

| HTTP | شرایط |
|------|-------|
| `404` | `request_id` پیدا نشد |
| `409` | وضعیت قبلی قابل retry نیست (مثلاً `completed`) |
| `400` | کد قبلی منقضی شده و کد جدید هم ندادید |
| `429` | به rate limit شماره خوردید |

---

## مثال‌های کامل

### Python — کل چرخه با retry هوشمند

```python
import requests
import time

BASE = "http://YOUR_SERVER_IP:8080"
HEADERS = {"X-API-Key": "YOUR_API_KEY", "Content-Type": "application/json"}


def call_with_retry(mobile: str, code: str, max_retries: int = 2) -> dict:
    """تماس + اگر جواب نداد، تا max_retries بار retry"""
    r = requests.post(f"{BASE}/api/v1/otp/call", headers=HEADERS,
                      json={"mobile": mobile, "code": code, "repeat": 2})
    r.raise_for_status()
    request_id = r.json()["request_id"]

    for attempt in range(max_retries + 1):
        # poll تا terminal
        while True:
            time.sleep(2)
            s = requests.get(f"{BASE}/api/v1/otp/status/{request_id}",
                             headers=HEADERS).json()
            if s["is_terminal"]:
                break

        # موفق بود؟
        if s["is_answered"] and s["status"] == "completed":
            print(f"✅ Success on attempt {attempt+1}")
            return s

        # قابل retry؟
        if not s["can_retry"] or attempt == max_retries:
            print(f"❌ Failed: {s['status']} (no more retries)")
            return s

        # retry
        print(f"⚠️  {s['status']} — retrying ({attempt+1}/{max_retries})...")
        r = requests.post(f"{BASE}/api/v1/otp/call/{request_id}/retry",
                          headers=HEADERS, json={})
        if r.status_code == 429:
            print("Rate limited — bailing out")
            return s
        request_id = r.json()["request_id"]

    return s


result = call_with_retry("09123456789", "5847", max_retries=2)
```

### PHP

```php
function callWithRetry(string $mobile, string $code, int $maxRetries = 2): array {
    $base = 'http://YOUR_SERVER_IP:8080';
    $headers = ['Content-Type: application/json', 'X-API-Key: YOUR_API_KEY'];

    $req = function(string $url, ?array $body = null) use ($headers) {
        $ch = curl_init($url);
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_HTTPHEADER     => $headers,
        ]);
        if ($body !== null) {
            curl_setopt($ch, CURLOPT_POST, true);
            curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($body));
        }
        $resp = curl_exec($ch);
        curl_close($ch);
        return json_decode($resp, true);
    };

    $r = $req("$base/api/v1/otp/call", ['mobile' => $mobile, 'code' => $code, 'repeat' => 2]);
    $rid = $r['request_id'];

    for ($attempt = 0; $attempt <= $maxRetries; $attempt++) {
        do {
            sleep(2);
            $s = $req("$base/api/v1/otp/status/$rid");
        } while (!$s['is_terminal']);

        if ($s['is_answered'] && $s['status'] === 'completed') return $s;
        if (!$s['can_retry'] || $attempt === $maxRetries) return $s;

        $r = $req("$base/api/v1/otp/call/$rid/retry", []);
        if (isset($r['detail'])) return $s;  // rate-limited or error
        $rid = $r['request_id'];
    }
    return $s;
}
```

### cURL

```bash
# 1. شروع تماس
curl -X POST http://YOUR_SERVER_IP:8080/api/v1/otp/call \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"mobile":"09123456789","code":"5847"}'

# 2. وضعیت
curl http://YOUR_SERVER_IP:8080/api/v1/otp/status/REQUEST_ID \
  -H "X-API-Key: YOUR_API_KEY"

# 3. retry با همان کد
curl -X POST http://YOUR_SERVER_IP:8080/api/v1/otp/call/REQUEST_ID/retry \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{}'

# 4. retry با کد جدید
curl -X POST http://YOUR_SERVER_IP:8080/api/v1/otp/call/REQUEST_ID/retry \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"code":"9999","repeat":1}'
```

---

## استراتژی پیشنهادی برای برنامه‌نویس

```
1. POST /otp/call           → request_id بگیر
2. POST /otp/status/{id}    → هر ۲ ثانیه poll (تا is_terminal=true)
3. اگر status == "completed" و is_answered == true:
       ✅ موفق — کد ارسال شد
4. اگر can_retry == true:
       می‌توانی POST /retry بزنی (با همان کد یا کد جدید)
5. اگر can_retry == false (مثل rejected):
       به کاربر بگو "تماس برقرار نشد" یا fallback به SMS
```

**مدت زمان معمولی:** ۵ تا ۳۰ ثانیه از queued تا is_terminal.
بعد از ۶۰ ثانیه اگر هنوز terminal نشد، احتمالاً چیزی غیرعادی است.

---

## Rate Limits

| محدودیت | مقدار |
|---------|-------|
| هر شماره | ۳ تماس در ۱۰ دقیقه (شامل retry) |
| همزمان | ۲۰ تماس |
| ساعتی | ۵۰۰ تماس |

پاسخ خطا با HTTP `429` و توضیح فارسی.

---

## کدهای خطا

| HTTP | معنی |
|------|------|
| `202` | پذیرفته شد |
| `400` | ورودی نامعتبر |
| `401` | API Key اشتباه |
| `404` | request_id پیدا نشد |
| `409` | وضعیت اجازه retry نمی‌دهد |
| `429` | rate limit |
| `503` | AMI قطع است یا ظرفیت پر است |

---

## نکات مهم

- زبان پیام: **فارسی**
- شناسه تماس از سمت سرور: `90004455` (CallerID)
- بعد از ۵ دقیقه از ساخت، رکورد + کد منقضی می‌شوند (و retry با همان کد امکان‌پذیر نیست — باید code جدید بدهید)
- در `timeline`، فیلد `at` یک Unix timestamp است (ثانیه با اعشار)
