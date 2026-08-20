"""
tiered.py — Backend cache étagé : L1 mémoire locale + L2 Redis partagé.

Lecture : L1 d'abord (micro-secondes), puis L2 sur miss (repeuple L1 au passage).
Écriture : write-through sur L1 et L2 à chaque set/mset — cohérence
inter-nœuds bornée par le TTL de L1, pas d'invalidation push entre nœuds
(pas de pub/sub Redis ici). Un `set()` fait sur un autre nœud n'invalide pas
immédiatement le L1 local — la donnée locale reste périmée jusqu'à expiration
de son TTL L1. Acceptable pour du cache "eventually consistent" ; si une
fraîcheur stricte inter-nœuds est requise, appeler `CacheConfig.ttl` court
côté L1 ou utiliser directement le backend redis seul.
"""

from __future__ import annotations

from typing import Any

from .memory import MemoryBackend
from .redis import RedisCacheBackend


class TieredCacheBackend:
    """
    Cache à deux étages : L1 (MemoryBackend, local au process) + L2
    (RedisCacheBackend, partagé entre nœuds).

    Usage:
        backend = TieredCacheBackend(
            l1=MemoryBackend(ttl=30, max_size=1000),
            l2=RedisCacheBackend(url="redis://localhost:6379", ttl=300),
        )
        await backend.connect()
        await backend.set("key", {"data": 1})
        value = await backend.get("key")   # L1 si chaud, sinon L2 (repeuple L1)
    """

    def __init__(self, l1: MemoryBackend, l2: RedisCacheBackend) -> None:
        self._l1 = l1
        self._l2 = l2

    async def connect(self) -> None:
        await self._l2.connect()

    async def disconnect(self) -> None:
        await self._l2.disconnect()

    async def get(self, key: str) -> Any | None:
        value = await self._l1.get(key)
        if value is not None:
            return value
        value = await self._l2.get(key)
        if value is not None:
            await self._l1.set(key, value)
        return value

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        await self._l1.set(key, value, ttl=ttl)
        await self._l2.set(key, value, ttl=ttl)

    async def delete(self, key: str) -> bool:
        l1_deleted = await self._l1.delete(key)
        l2_deleted = await self._l2.delete(key)
        return l1_deleted or l2_deleted

    async def exists(self, key: str) -> bool:
        if await self._l1.exists(key):
            return True
        return await self._l2.exists(key)

    async def clear(self) -> None:
        await self._l1.clear()
        await self._l2.clear()

    async def mget(self, keys: list[str]) -> dict[str, Any]:
        results = await self._l1.mget(keys)
        missing = [k for k, v in results.items() if v is None]
        if not missing:
            return results

        l2_results = await self._l2.mget(missing)
        to_backfill = {k: v for k, v in l2_results.items() if v is not None}
        if to_backfill:
            await self._l1.mset(to_backfill)
        results.update(l2_results)
        return results

    async def mset(self, mapping: dict[str, Any], ttl: int | None = None) -> None:
        await self._l1.mset(mapping, ttl=ttl)
        await self._l2.mset(mapping, ttl=ttl)

    async def keys(self, pattern: str | None = None) -> list[str]:
        # L2 = source de vérité inter-nœuds — L1 n'est qu'un sous-ensemble local.
        return await self._l2.keys(pattern)

    async def ttl(self, key: str) -> float | None:
        return await self._l2.ttl(key)

    async def ping(self) -> bool:
        return await self._l2.ping()

    def stats(self) -> dict:
        return {
            "backend": "tiered",
            "l1": self._l1.stats(),
            "l2": self._l2.stats(),
        }
