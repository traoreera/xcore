"""
permissions.py — Middleware for plugin permission checks.
"""

from __future__ import annotations

import logging

from ...permissions.engine import PermissionDenied
from .middleware import Middleware

logger = logging.getLogger("xcore.runtime.middlewares.permissions")


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
            logger.warning(f"[{plugin_name}] Appel refusé : {e}")
            return {"status": "error", "msg": str(e), "code": "permission_denied"}
        return await next_call(plugin_name, action, payload, handler, **kwargs)
