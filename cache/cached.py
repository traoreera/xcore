import json
from functools import wraps
from typing import Any

import redis
from pydantic import BaseModel

from configurations.redis import Configure, Rediscfg

cfg = Rediscfg(Configure())


class CacheManager:
    def __init__(
        self,
        endpoint: str = cfg.custom_config["host"],
        port: int = cfg.custom_config["port"],
        default_ttl: int = cfg.custom_config["TTL"],
        default_namespace: str = "xcore",
    ):
        self.default_ttl = default_ttl
        self.default_namespace = default_namespace
        self.__cache = redis.Redis(
            host=endpoint, port=port, db=0, decode_responses=True
        )

    # ------------------------------------------------------
    # 🔹 Basic cache operations (JSON + Pydantic safe)
    # ------------------------------------------------------
    def get(self, key: str):
        value = self.__cache.get(f"{self.default_namespace}:{key}")
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    def set(self, key: str, value: Any):
        # Sérialisation : si Pydantic, on convertit en dict avant JSON
        if isinstance(value, BaseModel):
            value = value.model_dump()  # pour Pydantic v2

        elif not isinstance(value, (str, int, float, bytes)):
            value = json.dumps(value, default=str)

        print(key, json.dumps(value, default=str))
        return self.__cache.set(
            f"{self.default_namespace}:{key}",
            json.dumps(value, default=str),
            ex=self.default_ttl,
        )

    def remove(self, key: str):
        return self.__cache.delete(f"{self.default_namespace}:{key}")

    def flush_namespace(self, namespace: str | None = None) -> int:
        ns = namespace or self.default_namespace
        pattern = f"{ns}:*"
        keys = self.__cache.keys(pattern)

        return self.__cache.delete(*keys) if keys else 0


class Cached:
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager

    def _build_key(self, func, args, kwargs) -> str:
        """Build a cache key based on the function name and its arguments."""
        return f"{func.__module__}:{func.__name__}:{args}:{kwargs}"

    def cached(self, func):
        """
        It wraps a function to cache its result based on its arguments.
        he can verify if the result is already cached; if so, it returns the cached value. Otherwise, it calls the function, caches the result, and returns it.
        """

        @wraps(func)
        def wrapper(*args, **kwargs):
            """
            Description:
                This function checks if the result of the decorated function is already cached. If so, it returns the cached value. Otherwise, it calls the function, caches the result, and returns it.
            Args:
                *args: Positional arguments passed to the function.
                **kwargs: Keyword arguments passed to the function.
            Returns:
                _type_: The result of the decorated function
                she came back either from the cache or by executing the function.
            """
            key = self._build_key(func, args, kwargs)
            cached_value = self.cache_manager.get(key)
            if cached_value is not None:
                return cached_value
            result = func(*args, **kwargs)
            self.cache_manager.set(key, result)
            return result

        return wrapper

    def remove(self, func):
        """
        It wraps a function to remove its cached result based on its arguments.
        """

        @wraps(func)
        def wrapper(*args, **kwargs):
            """
            Description:
                This function removes the cached result of the decorated function based on its arguments.
            Args:
                *args: Positional arguments passed to the function.
                **kwargs: Keyword arguments passed to the function.
            Returns:
                _type_: The result of the decorated function after removing its cached value.

            """
            key = self._build_key(func, args, kwargs)
            self.cache_manager.remove(key)

        return wrapper
