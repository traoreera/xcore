"""
service.py — Façade CacheService : masque le backend (memory ou redis).

Les plugins n'ont pas à savoir quel backend tourne.
L'interface est identique pour les deux.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...configurations.sections import CacheConfig

from ..base import BaseService, ServiceStatus

logger = logging.getLogger("xcore.services.cache")


class CacheService(BaseService):
    """
    Service de cache unifié.

    Usage:
        cache = CacheService(config)
        await cache.init()

        await cache.set("user:123", {"name": "Alice"}, ttl=300)
        user = await cache.get("user:123")   # {"name": "Alice"}

        await cache.delete("user:123")
        await cache.clear()
    """

    name = "cache"

    def __init__(self, config: "CacheConfig") -> None:
        super().__init__()
        self._config = config
        self._backend = None

    async def init(self) -> None:
        self._status = ServiceStatus.INITIALIZING
        backend_type = self._config.backend.lower()

        if backend_type == "redis":
            if not self._config.url:
                raise ValueError("CacheConfig.url obligatoire pour le backend Redis")
            from .backends.redis import RedisCacheBackend

            self._backend = RedisCacheBackend(
                url=self._config.url, ttl=self._config.ttl
            )
            await self._backend.connect()
        else:  # memory (default)
            from .backends.memory import MemoryBackend

            self._backend = MemoryBackend(
                ttl=self._config.ttl,
                max_size=self._config.max_size,
            )

        self._status = ServiceStatus.READY
        logger.info(f"Cache prêt (backend={backend_type})")

    # ── API ───────────────────────────────────────────────────

    async def get(self, key: str) -> Any | None:
        return await self._backend.get(key)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        await self._backend.set(key, value, ttl=ttl)

    async def delete(self, key: str) -> bool:
        return await self._backend.delete(key)

    async def exists(self, key: str) -> bool:
        return await self._backend.exists(key)

    async def clear(self) -> None:
        await self._backend.clear()

    async def keys(self, pattern: str | None = None) -> list[str]:
        return await self._backend.keys(pattern)

    async def get_or_set(self, key: str, factory, ttl: int | None = None) -> Any:
        """Retourne la valeur en cache, ou l'initialise via factory()."""
        value = await self.get(key)
        if value is None:
            value = await factory() if callable(factory) else factory
            await self.set(key, value, ttl=ttl)
        return value

    async def mget(self, keys: list[str]) -> dict[str, Any]:
        return {k: await self.get(k) for k in keys}

    async def mset(self, mapping: dict[str, Any], ttl: int | None = None) -> None:
        for k, v in mapping.items():
            await self.set(k, v, ttl=ttl)

    # ── Cycle de vie ──────────────────────────────────────────

    async def shutdown(self) -> None:
        if hasattr(self._backend, "disconnect"):
            await self._backend.disconnect()
        self._status = ServiceStatus.STOPPED

    async def health_check(self) -> tuple[bool, str]:
        try:
            ok = await self._backend.ping()
            return ok, "ok" if ok else "ping failed"
        except Exception as e:
            return False, str(e)

    def status(self) -> dict:
        stats = self._backend.stats() if self._backend else {}
        return {"name": self.name, "status": self._status.value, **stats}
