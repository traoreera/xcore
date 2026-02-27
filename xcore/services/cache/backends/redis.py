"""
redis.py — Backend cache Redis pour CacheService.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger("xcore.services.cache.redis")


class RedisCacheBackend:
    """
    Backend cache Redis.
    Sérialise en JSON pour stocker n'importe quel type Python.

    Usage:
        backend = RedisCacheBackend(url="redis://localhost:6379", ttl=300)
        await backend.connect()
        await backend.set("key", {"data": 1})
        value = await backend.get("key")
    """

    def __init__(self, url: str, ttl: int = 300) -> None:
        self._url = url
        self._ttl = ttl
        self._client = None

    async def connect(self) -> None:
        try:
            import redis.asyncio as aioredis
        except ImportError as e:
            raise ImportError("redis non installé — pip install redis[asyncio]") from e
        self._client = aioredis.from_url(self._url, decode_responses=True)
        await self._client.ping()

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()

    async def get(self, key: str) -> Any | None:
        raw = await self._client.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        ex = ttl if ttl is not None else self._ttl
        raw = json.dumps(value) if not isinstance(value, (str, bytes)) else value
        await self._client.set(key, raw, ex=ex if ex > 0 else None)

    async def delete(self, key: str) -> bool:
        return bool(await self._client.delete(key))

    async def exists(self, key: str) -> bool:
        return bool(await self._client.exists(key))

    async def clear(self) -> None:
        await self._client.flushdb()

    async def keys(self, pattern: str | None = None) -> list[str]:
        return await self._client.keys(pattern or "*")

    async def ttl(self, key: str) -> float | None:
        val = await self._client.ttl(key)
        return float(val) if val >= 0 else None

    async def ping(self) -> bool:
        try:
            await self._client.ping()
            return True
        except Exception:
            return False

    def stats(self) -> dict:
        return {"backend": "redis", "url": self._url[:30]}
