
#TODO: use redis cache for this options for  CacheManager

import time
from abc import ABC, abstractmethod
from typing import Any, Optional


class CacheBackend(ABC):
    @abstractmethod
    def get(self, key: str, ttl: Optional[int] = None) -> Optional[Any]:
        pass

    @abstractmethod
    def set(self, key: str, value: Any):
        pass

    @abstractmethod
    def delete(self, key: str):
        pass

    @abstractmethod
    def clear(self):
        pass


class CacheManager(CacheBackend):
    """Simple in-memory cache with TTL support"""

    def __init__(self):
        self.cache = {}
        self.timestamps = {}

    def get(self, key: str, ttl: Optional[int] = None):
        if key not in self.cache:
            return None

        if ttl and key in self.timestamps:
            age = time.time() - self.timestamps[key]
            if age > ttl:
                self.delete(key)
                return None

        return self.cache[key]

    def set(self, key: str, value: Any):
        self.cache[key] = value
        self.timestamps[key] = time.time()

    def delete(self, key: str):
        self.cache.pop(key, None)
        self.timestamps.pop(key, None)

    def clear(self):
        self.cache.clear()
        self.timestamps.clear()
