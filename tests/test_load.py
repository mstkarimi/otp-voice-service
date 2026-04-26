"""
تست بار: شبیه‌سازی 20 تماس همزمان
هدف: response time زیر 500ms برای همه درخواست‌ها
اجرا: python3 -m pytest tests/test_load.py -v -s
"""

import asyncio
import time
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import httpx


CONCURRENT_CALLS = 20
MAX_RESPONSE_MS = 500


async def _send_call(client: httpx.AsyncClient, mobile: str, api_key: str) -> float:
    start = time.time()
    resp = await client.post(
        "/api/v1/otp/call",
        json={"mobile": mobile, "code": "12345", "repeat": 1},
        headers={"Authorization": f"Bearer {api_key}"},
    )
    elapsed_ms = (time.time() - start) * 1000
    assert resp.status_code in (202, 429, 503), f"Unexpected status: {resp.status_code}"
    return elapsed_ms


@pytest.mark.asyncio
async def test_concurrent_20_calls():
    from passlib.context import CryptContext
    from src.core.rate_limiter import init_rate_limiter
    from src.ami.originator import init_originator

    API_KEY = "load-test-key"
    ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    API_KEY_HASH = ctx.hash(API_KEY)

    mock_config = MagicMock()
    mock_config.api.api_key_hash = API_KEY_HASH
    mock_config.api.ip_whitelist = []

    rl = init_rate_limiter(100, 60, 20, 1000)
    init_originator("90004455", "90004455", False)

    mock_ami = MagicMock()
    mock_ami.is_connected = True
    mock_ami.send_action = AsyncMock(return_value={"Response": "Success"})

    call_counter = [0]

    async def fake_create(*args, **kwargs):
        call_counter[0] += 1
        return f"uuid-{call_counter[0]}"

    with patch("src.config.get_config", return_value=mock_config), \
         patch("src.ami.client.get_ami_client", return_value=mock_ami), \
         patch("src.core.rate_limiter.get_rate_limiter", return_value=rl), \
         patch("src.storage.db.create_call_record", new_callable=AsyncMock,
               side_effect=fake_create), \
         patch("src.storage.db.update_call_status", new_callable=AsyncMock):

        from fastapi import FastAPI
        from src.api.routes import router
        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        # تولید 20 شماره موبایل مختلف
        mobiles = [f"091{i:09d}" for i in range(1, CONCURRENT_CALLS + 1)]

        async with httpx.AsyncClient(app=app, base_url="http://test") as client:
            start_total = time.time()
            tasks = [_send_call(client, mobile, API_KEY) for mobile in mobiles]
            response_times = await asyncio.gather(*tasks)
            total_elapsed = (time.time() - start_total) * 1000

        max_rt = max(response_times)
        avg_rt = sum(response_times) / len(response_times)

        print(f"\n  تعداد تماس: {CONCURRENT_CALLS}")
        print(f"  زمان کل: {total_elapsed:.1f}ms")
        print(f"  بیشترین response time: {max_rt:.1f}ms")
        print(f"  میانگین response time: {avg_rt:.1f}ms")

        assert max_rt < MAX_RESPONSE_MS, (
            f"Response time بیش از {MAX_RESPONSE_MS}ms: max={max_rt:.1f}ms"
        )
        print(f"  ✅ همه درخواست‌ها زیر {MAX_RESPONSE_MS}ms پاسخ گرفتند")
