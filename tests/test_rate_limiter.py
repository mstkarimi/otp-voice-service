import pytest
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.rate_limiter import RateLimiter


@pytest.fixture
def limiter():
    return RateLimiter(
        per_number_calls=3,
        per_number_window_minutes=10,
        max_concurrent=5,
        hourly_limit=10,
    )


@pytest.mark.asyncio
async def test_per_number_allows_within_limit(limiter):
    mobile = "09120000001"
    for _ in range(3):
        ok, msg = await limiter.check_number_limit(mobile)
        assert ok, msg


@pytest.mark.asyncio
async def test_per_number_blocks_over_limit(limiter):
    mobile = "09120000002"
    for _ in range(3):
        await limiter.check_number_limit(mobile)
    ok, msg = await limiter.check_number_limit(mobile)
    assert not ok
    assert msg is not None


@pytest.mark.asyncio
async def test_different_numbers_independent(limiter):
    for i in range(3):
        await limiter.check_number_limit("09120000003")
    # شماره دیگر نباید بلاک باشد
    ok, _ = await limiter.check_number_limit("09120000004")
    assert ok


@pytest.mark.asyncio
async def test_hourly_limit(limiter):
    for _ in range(10):
        ok, _ = await limiter.check_hourly_limit()
        assert ok
    ok, msg = await limiter.check_hourly_limit()
    assert not ok


def test_concurrent_capacity(limiter):
    for _ in range(5):
        limiter.acquire_slot()
    ok, msg = limiter.check_concurrent_capacity()
    assert not ok


def test_release_slot(limiter):
    limiter.acquire_slot()
    limiter.acquire_slot()
    limiter.release_slot()
    assert limiter.active_calls == 1


def test_available_channels(limiter):
    limiter.acquire_slot()
    limiter.acquire_slot()
    assert limiter.available_channels == 3
