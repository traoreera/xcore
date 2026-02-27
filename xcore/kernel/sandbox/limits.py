"""
limits.py — Rate limiting par plugin (fenêtre glissante).
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass


class RateLimitExceeded(Exception):
    pass


@dataclass
class RateLimitConfig:
    calls: int = 100
    period_seconds: float = 60.0


class RateLimiter:
    def __init__(self, config: RateLimitConfig) -> None:
        self._config = config
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def check(self, plugin_name: str) -> None:
        async with self._lock:
            now = time.monotonic()
            cutoff = now - self._config.period_seconds
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()
            if len(self._timestamps) >= self._config.calls:
                retry_in = round(self._timestamps[0] - cutoff, 2)
                raise RateLimitExceeded(
                    f"Plugin '{plugin_name}' : quota dépassé "
                    f"({self._config.calls}/{self._config.period_seconds}s). "
                    f"Réessaie dans {retry_in}s."
                )
            self._timestamps.append(now)

    def stats(self) -> dict:
        now = time.monotonic()
        cutoff = now - self._config.period_seconds
        current = sum(t >= cutoff for t in self._timestamps)
        return {
            "calls_in_window": current,
            "limit": self._config.calls,
            "period_seconds": self._config.period_seconds,
            "remaining": max(0, self._config.calls - current),
        }


class RateLimiterRegistry:
    def __init__(self) -> None:
        self._limiters: dict[str, RateLimiter] = {}

    def register(self, plugin_name: str, config: RateLimitConfig) -> None:
        self._limiters[plugin_name] = RateLimiter(config)

    async def check(self, plugin_name: str) -> None:
        if limiter := self._limiters.get(plugin_name):
            await limiter.check(plugin_name)

    def stats(self, plugin_name: str) -> dict | None:
        lim = self._limiters.get(plugin_name)
        return lim.stats() if lim else None
