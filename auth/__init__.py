from security.hash import Hash
from cache import Cached, CacheManager
from admin import dependencies


authCache = Cached(CacheManager(default_namespace="auth-users", default_ttl=60 * 5))


__all__ = ["authCache"]