"""
memory.py — Backend cache mémoire : LRU + TTL + max_size.
Zéro dépendance externe.
"""
from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any


@dataclass
class _Entry:
    value: Any
    expires_at: float | None   # None = jamais


class MemoryBackend:
    """
    Cache LRU en mémoire avec TTL et taille maximale.

    Usage:
        backend = MemoryBackend(ttl=300, max_size=1000)
        await backend.set("key", {"data": 1})
        value = await backend.get("key")   # {"data": 1}
        await backend.delete("key")
    """

    def __init__(self, ttl: int = 300, max_size: int = 1000) -> None:
        self._ttl      = ttl
        self._max_size = max_size
        self._store: OrderedDict[str, _Entry] = OrderedDict()
        self._hits   = 0
        self._misses = 0

    async def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return None
        if entry.expires_at is not None and time.monotonic() > entry.expires_at:
            del self._store[key]
            self._misses += 1
            return None
        # LRU move
        self._store.move_to_end(key)
        self._hits += 1
        return entry.value

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        effective_ttl = ttl if ttl is not None else self._ttl
        expires_at    = (time.monotonic() + effective_ttl) if effective_ttl > 0 else None

        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = _Entry(value=value, expires_at=expires_at)

        # Éviction LRU si max_size dépassé
        while len(self._store) > self._max_size:
            self._store.popitem(last=False)

    async def delete(self, key: str) -> bool:
        return self._store.pop(key, None) is not None

    async def exists(self, key: str) -> bool:
        return await self.get(key) is not None

    async def clear(self) -> None:
        self._store.clear()

    async def keys(self, pattern: str | None = None) -> list[str]:
        import fnmatch
        all_keys = list(self._store.keys())
        if pattern:
            return [k for k in all_keys if fnmatch.fnmatch(k, pattern)]
        return all_keys

    async def ttl(self, key: str) -> float | None:
        entry = self._store.get(key)
        if entry is None or entry.expires_at is None:
            return None
        remaining = entry.expires_at - time.monotonic()
        return max(0.0, remaining)

    async def ping(self) -> bool:
        return True

    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "backend": "memory",
            "size":    len(self._store),
            "max_size": self._max_size,
            "hits":    self._hits,
            "misses":  self._misses,
            "hit_rate": round(self._hits / total, 3) if total else 0.0,
        }
