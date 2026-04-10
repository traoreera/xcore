"""
ratelimit.py — Middleware for plugin rate limiting.
"""

from __future__ import annotations

from .middleware import Middleware
from ...sandbox.limits import RateLimitExceeded


class RateLimitMiddleware(Middleware):
    def __init__(self, rate):
        self._rate = rate

    async def __call__(
        self, plugin_name, action, payload, next_call, handler, **kwargs
    ):
        try:
            self._rate.check(plugin_name)
        except RateLimitExceeded as e:
            return {"status": "error", "msg": str(e), "code": "rate_limit_exceeded"}
        return await next_call(plugin_name, action, payload, handler, **kwargs)
