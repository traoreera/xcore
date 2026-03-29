"""
tracing.py — Middleware de tracing pour les appels de plugins.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from ..middleware import Middleware

logger = logging.getLogger("xcore.runtime.middlewares.tracing")


class TracingMiddleware(Middleware):
    """Gère le tracing OpenTelemetry pour chaque appel de plugin."""

    def __init__(self, tracer: Any):
        self._tracer = tracer

    async def __call__(
        self,
        plugin_name: str,
        action: str,
        payload: dict,
        next_call: Callable,
        **kwargs
    ) -> dict:
        if not self._tracer:
            return await next_call(plugin_name, action, payload, **kwargs)

        async with self._tracer.span(f"{plugin_name}.{action}") as span:
            span.set_attribute("plugin", plugin_name)
            span.set_attribute("action", action)

            result = await next_call(plugin_name, action, payload, **kwargs)

            if isinstance(result, dict) and result.get("status") == "error":
                span.set_status("error")

            return result
