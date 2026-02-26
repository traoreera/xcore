"""
redis.py — Adaptateur Redis asynchrone (redis-py ≥ 4.2).
"""
from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ....configurations.sections import DatabaseConfig

logger = logging.getLogger("xcore.services.database.redis")


class RedisAdapter:
    """
    Adaptateur Redis async.

    Usage:
        await adapter.set("key", "value", ex=300)
        value = await adapter.get("key")
        client = adapter.client   # accès direct redis.asyncio.Redis
    """

    def __init__(self, name: str, cfg: "DatabaseConfig") -> None:
        self.name = name
        self.url  = cfg.url or "redis://localhost:6379"
        self._max = cfg.max_connections or 10
        self._client = None

    async def connect(self) -> None:
        try:
            import redis.asyncio as aioredis
        except ImportError as e:
            raise ImportError("redis non installé — pip install redis[asyncio]") from e

        pool = aioredis.ConnectionPool.from_url(
            self.url,
            max_connections=self._max,
            decode_responses=True,
        )
        self._client = aioredis.Redis(connection_pool=pool)
        await self._client.ping()
        logger.info(f"[{self.name}] Redis connecté → {self.url[:30]}…")

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get(self, key: str) -> str | None:
        return await self._client.get(key)

    async def set(self, key: str, value: Any, ex: int | None = None) -> bool:
        return await self._client.set(key, value, ex=ex)

    async def delete(self, *keys: str) -> int:
        return await self._client.delete(*keys)

    async def exists(self, key: str) -> bool:
        return bool(await self._client.exists(key))

    async def hget(self, name: str, key: str) -> str | None:
        return await self._client.hget(name, key)

    async def hset(self, name: str, mapping: dict) -> int:
        return await self._client.hset(name, mapping=mapping)

    async def hgetall(self, name: str) -> dict:
        return await self._client.hgetall(name)

    @property
    def client(self):
        return self._client

    async def ping(self) -> tuple[bool, str]:
        try:
            await self._client.ping()
            return True, "ok"
        except Exception as e:
            return False, str(e)
