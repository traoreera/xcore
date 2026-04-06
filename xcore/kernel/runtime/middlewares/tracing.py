"""
tracing.py — Middleware de tracing (OpenTelemetry) pour les appels de plugins.
"""

from __future__ import annotations

import logging
import time
from typing import Callable

from .middleware import Middleware

logger = logging.getLogger("xcore.runtime.middleware.tracing")


class TracingMiddleware(Middleware):
    """
    Middleware gérant le tracing et l'observabilité (OpenTelemetry, Metrics).
    Encapsule chaque appel dans un Span si un traceur est disponible.
    """

    def __init__(self, tracer=None, metrics=None):
        self._tracer = tracer
        self._metrics = metrics

        if self._metrics:
            self._c_calls = self._metrics.counter("plugin.calls")
            self._c_errors = self._metrics.counter("plugin.errors")
            self._h_lat = self._metrics.histogram("plugin.latency_seconds")

    async def __call__(
        self,
        plugin_name: str,
        action: str,
        payload: dict,
        next_call: Callable,
        handler,
        **kwargs,
    ) -> dict:
        t0 = time.monotonic()

        if self._metrics:
            self._c_calls.inc()

        # Span de tracing optionnel
        if self._tracer:
            async with self._tracer.span(f"{plugin_name}.{action}") as span:
                span.set_attribute("plugin", plugin_name)
                span.set_attribute("action", action)
                result = await next_call(plugin_name, action, payload, handler, **kwargs)

                if isinstance(result, dict) and result.get("status") == "error":
                    span.set_status("error")
                    if self._metrics:
                        self._c_errors.inc()
        else:
            result = await next_call(plugin_name, action, payload, handler, **kwargs)
            if isinstance(result, dict) and result.get("status") == "error":
                if self._metrics:
                    self._c_errors.inc()

        elapsed = time.monotonic() - t0
        if self._metrics:
            self._h_lat.observe(elapsed)

        return result
