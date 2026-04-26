import asyncio
import time
from typing import Dict, Tuple, Optional
from src.core.logger import get_logger

logger = get_logger()


class RateLimiter:
    """
    Rate limiter سه‌لایه بدون Redis:
      ۱. per-number: حداکثر N تماس به یک شماره در X دقیقه
      ۲. concurrent: حداکثر N تماس همزمان (semaphore)
      ۳. hourly: حداکثر N تماس در ساعت
    """

    def __init__(
        self,
        per_number_calls: int = 3,
        per_number_window_minutes: int = 10,
        max_concurrent: int = 20,
        hourly_limit: int = 500,
    ):
        self._per_number_calls = per_number_calls
        self._per_number_window = per_number_window_minutes * 60

        # {mobile: [timestamp, ...]}
        self._number_history: Dict[str, list] = {}

        # semaphore تماس همزمان
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_count = 0
        self._max_concurrent = max_concurrent

        # hourly counter
        self._hourly_limit = hourly_limit
        self._hourly_calls: list = []

        self._lock = asyncio.Lock()

    async def check_number_limit(self, mobile: str) -> Tuple[bool, Optional[str]]:
        """چک محدودیت per-number"""
        async with self._lock:
            now = time.time()
            window_start = now - self._per_number_window
            history = self._number_history.get(mobile, [])
            history = [t for t in history if t > window_start]

            if len(history) >= self._per_number_calls:
                wait_sec = int(history[0] - window_start)
                return False, f"حداکثر {self._per_number_calls} تماس در {self._per_number_window // 60} دقیقه - {wait_sec} ثانیه صبر کنید"

            history.append(now)
            self._number_history[mobile] = history
            return True, None

    async def check_hourly_limit(self) -> Tuple[bool, Optional[str]]:
        """چک محدودیت hourly"""
        async with self._lock:
            now = time.time()
            self._hourly_calls = [t for t in self._hourly_calls if t > now - 3600]

            if len(self._hourly_calls) >= self._hourly_limit:
                return False, f"محدودیت {self._hourly_limit} تماس در ساعت اعمال شده"

            self._hourly_calls.append(now)
            return True, None

    def check_concurrent_capacity(self) -> Tuple[bool, Optional[str]]:
        """چک ظرفیت تماس همزمان"""
        if self._active_count >= self._max_concurrent:
            return False, f"ظرفیت سیستم پر است ({self._max_concurrent} تماس همزمان)"
        return True, None

    def acquire_slot(self) -> None:
        self._active_count += 1

    def release_slot(self) -> None:
        if self._active_count > 0:
            self._active_count -= 1

    @property
    def active_calls(self) -> int:
        return self._active_count

    @property
    def available_channels(self) -> int:
        return max(0, self._max_concurrent - self._active_count)

    async def cleanup(self) -> None:
        """پاک‌سازی رکوردهای منقضی"""
        async with self._lock:
            now = time.time()
            window_start = now - self._per_number_window
            for mobile in list(self._number_history.keys()):
                history = [t for t in self._number_history[mobile] if t > window_start]
                if history:
                    self._number_history[mobile] = history
                else:
                    del self._number_history[mobile]
            self._hourly_calls = [t for t in self._hourly_calls if t > now - 3600]
            logger.debug(f"Cleanup done. Active numbers tracked: {len(self._number_history)}")


_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        raise RuntimeError("RateLimiter not initialized")
    return _rate_limiter


def init_rate_limiter(
    per_number_calls: int,
    per_number_window_minutes: int,
    max_concurrent: int,
    hourly_limit: int,
) -> RateLimiter:
    global _rate_limiter
    _rate_limiter = RateLimiter(
        per_number_calls=per_number_calls,
        per_number_window_minutes=per_number_window_minutes,
        max_concurrent=max_concurrent,
        hourly_limit=hourly_limit,
    )
    return _rate_limiter
