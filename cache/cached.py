import redis
import json
from functools import wraps
from typing import Any
from pydantic import BaseModel


class CacheManager:
    def __init__(
        self,
        endpoint: str = "localhost",
        port: int = 6379,
        default_ttl: int = 60,
        default_namespace: str = "xcore",
    ):
        self.default_ttl = default_ttl
        self.default_namespace = default_namespace
        self.__cache = redis.Redis(host=endpoint, port=port, db=0, decode_responses=True)

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

    def set(self,key:str, value: Any):
        # Sérialisation : si Pydantic, on convertit en dict avant JSON
        if isinstance(value, BaseModel):
            value = value.model_dump()  # pour Pydantic v2

        elif not isinstance(value, (str, int, float, bytes)):
            value = json.dumps(value, default=str)
        
        print(key, json.dumps(value, default=str))
        return self.__cache.set(f"{self.default_namespace}:{key}",json.dumps(value, default=str), ex=self.default_ttl)

    def remove(self, key: str):
        return self.__cache.delete(f"{self.default_namespace}:{key}")

    def flush_namespace(self, namespace: str | None = None) -> int:
        ns = namespace or self.default_namespace
        pattern = f"{ns}:*"
        keys = self.__cache.keys(pattern)
        if not keys:
            return 0
        return self.__cache.delete(*keys)


class Cached:
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager

    def _build_key(self, func, args, kwargs) -> str:
        return f"{func.__module__}:{func.__name__}:{args}:{kwargs}"

    def cached(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = self._build_key(func, args, kwargs)
            cached_value = self.cache_manager.get(key)
            if cached_value is not None:
                return cached_value
            result = func(*args, **kwargs)
            self.cache_manager.set(key,result)
            return result

        return wrapper

    def remove(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = self._build_key(func, args, kwargs)
            self.cache_manager.remove(key)

        return wrapper
