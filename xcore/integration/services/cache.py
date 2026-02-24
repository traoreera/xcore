"""
Cache Service — cache mémoire, Redis ou Memcached.
API unifiée quelque soit le backend.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable, Optional

from ..config.loader import CacheConfig, IntegrationConfig

logger = logging.getLogger("integrations.cache")


# ─────────────────────────────────────────────────────────────
# Backends
# ─────────────────────────────────────────────────────────────


class MemoryBackend:
    """Cache en mémoire avec TTL."""

    def __init__(self, max_size: int = 1000):
        self._store: dict[str, tuple[Any, float]] = {}
        self._max_size = max_size

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at > 0 and time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl: int = 300):
        if len(self._store) >= self._max_size:
            # Eviction FIFO simple
            oldest = next(iter(self._store))
            del self._store[oldest]
        expires_at = time.monotonic() + ttl if ttl > 0 else 0
        self._store[key] = (value, expires_at)

    def delete(self, key: str):
        self._store.pop(key, None)

    def clear(self):
        self._store.clear()

    def exists(self, key: str) -> bool:
        return self.get(key) is not None

    def size(self) -> int:
        return len(self._store)


class RedisBackend:
    """Cache Redis."""

    def __init__(self, url: str):
        try:
            import redis

            self._client = redis.from_url(url, decode_responses=False)
            self._client.ping()
            logger.info("Cache Redis connecté")
        except ImportError:
            raise ImportError("redis-py non installé: pip install redis")

    def get(self, key: str) -> Optional[Any]:
        raw = self._client.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception as e:
            logger.warning(f"Valeur Redis invalide pour la clé '{key}': {e}")
            return None

    def set(self, key: str, value: Any, ttl: int = 300):
        payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        self._client.setex(key, ttl, payload.encode("utf-8"))

    def delete(self, key: str):
        self._client.delete(key)

    def clear(self):
        self._client.flushdb()

    def exists(self, key: str) -> bool:
        return bool(self._client.exists(key))

    def size(self) -> int:
        return self._client.dbsize()


# ─────────────────────────────────────────────────────────────
# Service principal
# ─────────────────────────────────────────────────────────────


class CacheService:
    """
    Service de cache avec API unifiée.

    Usage:
        cache.set("key", {"data": 123}, ttl=60)
        value = cache.get("key")
        cache.delete("key")

        # Décorateur
        @cache.cached(ttl=120, key="user:{user_id}")
        def get_user(user_id: int):
            return db.query(User).get(user_id)
    """

    def __init__(self, config: IntegrationConfig):
        self._config: CacheConfig = config.cache
        self._backend = None

    def init(self):
        backend = self._config.backend
        if backend == "redis":
            if not self._config.url:
                raise ValueError("url manquant pour le cache Redis")
            self._backend = RedisBackend(self._config.url)
        else:
            self._backend = MemoryBackend(max_size=self._config.max_size)
        logger.info(f"Cache initialisé [{backend}]")

    def _ensure_init(self):
        if self._backend is None:
            self.init()

    # ── API ───────────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        self._ensure_init()
        value = self._backend.get(key)
        return value if value is not None else default

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        self._ensure_init()
        self._backend.set(key, value, ttl=ttl or self._config.ttl)

    def delete(self, key: str) -> None:
        self._ensure_init()
        self._backend.delete(key)

    def exists(self, key: str) -> bool:
        self._ensure_init()
        return self._backend.exists(key)

    def clear(self) -> None:
        self._ensure_init()
        self._backend.clear()
        logger.info("Cache vidé")

    def get_or_set(
        self, key: str, factory: Callable[[], Any], ttl: Optional[int] = None
    ) -> Any:
        """Retourne la valeur en cache ou l'obtient via factory puis la met en cache."""
        value = self.get(key)
        if value is None:
            value = factory()
            self.set(key, value, ttl=ttl)
        return value

    def cached(self, ttl: Optional[int] = None, key: Optional[str] = None):
        """
        Décorateur de cache.

        @cache.cached(ttl=60, key="users:{user_id}")
        def get_user(user_id: int): ...
        """

        def decorator(func: Callable) -> Callable:
            import functools

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                if key:
                    # Remplacement des paramètres dans la clé
                    import inspect

                    sig = inspect.signature(func)
                    bound = sig.bind(*args, **kwargs)
                    bound.apply_defaults()
                    cache_key = key.format(**bound.arguments)
                else:
                    cache_key = f"{func.__module__}.{func.__qualname__}:{args}:{kwargs}"

                cached_value = self.get(cache_key)
                if cached_value is not None:
                    return cached_value

                result = func(*args, **kwargs)
                self.set(cache_key, result, ttl=ttl)
                return result

            return wrapper

        return decorator

    def __repr__(self):
        self._ensure_init()
        return (
            f"<CacheService backend={self._config.backend} size={self._backend.size()}>"
        )
