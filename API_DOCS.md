# OTP Voice Call Service — API Reference

---

## Base URL

```
http://YOUR_SERVER_IP:8080
```

---

## Authentication

Two methods are supported:

```http
X-API-Key: YOUR_API_KEY
```
or
```http
Authorization: Bearer YOUR_API_KEY
```

The API key is generated during installation and displayed once in the terminal.

---

## Endpoints

### GET /api/v1/health

No authentication required.

**Response `200`:**
```json
{
  "api": "ok",
  "ami": "connected",
  "active_calls": 0,
  "available_channels": 20
}
```

---

### POST /api/v1/otp/call

**Request:**
```json
{
  "mobile": "09123456789",
  "code": "1234",
  "repeat": 2
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `mobile` | string | ✅ | Iranian mobile — `09XXXXXXXXX` format |
| `code` | string | ✅ | Digits only, 4–8 chars |
| `repeat` | integer | ❌ | How many times to read the code, 1–3 (default: 2) |

**Response `202`:**
```json
{
  "request_id": "d78ed57f-38a7-4634-986d-fa2228af429b",
  "status": "queued",
  "estimated_time": 5
}
```

---

### GET /api/v1/otp/status/{request_id}

**Response `200`:**
```json
{
  "request_id": "d78ed57f-38a7-4634-986d-fa2228af429b",
  "status": "completed",
  "duration": null,
  "hangup_cause": "NORMAL_CLEARING"
}
```

**Status values:** `queued` → `ringing` → `completed` / `failed`

---

## Rate Limits

| Limit | Value |
|-------|-------|
| Per number | 3 calls / 10 minutes |
| Concurrent | 20 simultaneous calls |
| Hourly | 500 calls |

---

## Error Codes

| HTTP | Meaning |
|------|---------|
| 202 | Accepted |
| 400 | Invalid input |
| 401 | Invalid or missing API key |
| 429 | Rate limit exceeded |
| 503 | Service unavailable (AMI disconnected) |

---

## Examples

```bash
# Call
curl -X POST http://YOUR_SERVER_IP:8080/api/v1/otp/call \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"mobile":"09123456789","code":"5847"}'

# Status
curl http://YOUR_SERVER_IP:8080/api/v1/otp/status/REQUEST_ID \
  -H "X-API-Key: YOUR_API_KEY"
```

```python
import requests

BASE = "http://YOUR_SERVER_IP:8080"
HEADERS = {"X-API-Key": "YOUR_API_KEY"}

r = requests.post(f"{BASE}/api/v1/otp/call", headers=HEADERS,
                  json={"mobile": "09123456789", "code": "5847"})
request_id = r.json()["request_id"]
```

```php
$ch = curl_init("http://YOUR_SERVER_IP:8080/api/v1/otp/call");
curl_setopt_array($ch, [
    CURLOPT_POST           => true,
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_HTTPHEADER     => ["Content-Type: application/json", "X-API-Key: YOUR_API_KEY"],
    CURLOPT_POSTFIELDS     => json_encode(["mobile" => "09123456789", "code" => "5847"]),
]);
$result = json_decode(curl_exec($ch), true);
```
