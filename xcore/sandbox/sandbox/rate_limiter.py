"""
sandbox/rate_limiter.py
────────────────────────
Limiteur de débit par plugin — fenêtre glissante.
Utilisé dans plugin_manager.call() avant de router vers Trusted ou Sandbox.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque

from ..contracts.plugin_manifest import RateLimitConfig


class RateLimitExceeded(Exception):
    """Levée quand le plugin dépasse son quota d'appels."""


class RateLimiter:
    """
    Fenêtre glissante par plugin.
    Thread-safe via asyncio.Lock.
    """

    def __init__(self, config: RateLimitConfig) -> None:
        self._config = config
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def check(self, plugin_name: str) -> None:
        """
        Vérifie si l'appel est autorisé.
        Lève RateLimitExceeded si le quota est dépassé.
        """
        async with self._lock:
            now = time.monotonic()
            cutoff = now - self._config.period_seconds

            # Purge les timestamps hors fenêtre
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()

            if len(self._timestamps) >= self._config.calls:
                oldest = self._timestamps[0]
                retry_in = round(oldest - cutoff, 2)
                raise RateLimitExceeded(
                    f"Plugin '{plugin_name}' : quota dépassé "
                    f"({self._config.calls} appels / {self._config.period_seconds}s). "
                    f"Réessaie dans {retry_in}s."
                )

            self._timestamps.append(now)

    def stats(self) -> dict:
        """Retourne les stats courantes du rate limiter."""
        now = time.monotonic()
        cutoff = now - self._config.period_seconds
        current = sum(t >= cutoff for t in self._timestamps)
        return {
            "calls_in_window": current,
            "limit": self._config.calls,
            "period_seconds": self._config.period_seconds,
            "remaining": max(0, self._config.calls - current),
        }


# ── Registre global des rate limiters (un par plugin) ──


class RateLimiterRegistry:
    """Maintient un RateLimiter par plugin."""

    def __init__(self) -> None:
        self._limiters: dict[str, RateLimiter] = {}

    def register(self, plugin_name: str, config: RateLimitConfig) -> None:
        self._limiters[plugin_name] = RateLimiter(config)

    async def check(self, plugin_name: str) -> None:
        """No-op si le plugin n'a pas de rate limiter configuré."""
        if limiter := self._limiters.get(plugin_name):
            await limiter.check(plugin_name)

    def stats(self, plugin_name: str) -> dict | None:
        limiter = self._limiters.get(plugin_name)
        return limiter.stats() if limiter else None
