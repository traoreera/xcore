from admin import dependencies
from cache import Cached, CacheManager
from security.hash import Hash

authCache = Cached(CacheManager(default_namespace="auth-users", default_ttl=60 * 5))


__all__ = ["authCache"]
