"""
permissions.py — Middleware for plugin permission checks.
"""

from __future__ import annotations

from xcore.kernel.permissions.engine import PermissionDenied

from ..observability import get_logger
from .middleware import Middleware

logger = get_logger("xcore.runtime.middlewares.permissions")


class PermissionMiddleware(Middleware):
    def __init__(self, permissions):
        self._permissions = permissions

    async def __call__(
        self, plugin_name, action, payload, next_call, handler, **kwargs
    ):
        resource = kwargs.get("resource") or f"{action}"
        try:
            self._permissions.check(plugin_name, resource, "execute")
        except PermissionDenied as e:
            logger.warning("call denied", plugin=plugin_name, error=str(e))
            return {"status": "error", "msg": str(e), "code": "permission_denied"}
        return await next_call(plugin_name, action, payload, handler, **kwargs)
