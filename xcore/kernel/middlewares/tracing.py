"""
tracing.py — Middleware de tracing pour les appels de plugins.

Wraps each plugin call in a span and propagates the trace context so that
Plugin A → supervisor.call("plugin_b", ...) stays in the same trace.
"""

from __future__ import annotations

import time
from typing import Callable

from xcore.kernel.observability import get_logger

from .middleware import Middleware

# from xcore.kernel.observability.tracing import _current_span_id, _current_trace_id


logger = get_logger("xcore.runtime.middleware.tracing")


class TracingMiddleware(Middleware):
    """
    Encapsule chaque appel plugin dans un Span.
    Le trace_id est propagé via ContextVar — les appels inter-plugins
    (Plugin A → supervisor.call → Plugin B) restent dans la même trace.
    """

    def __init__(self, tracer=None, metrics=None, events=None):
        self._tracer = tracer
        self._metrics = metrics
        self._events = events
        if self._metrics:
            self._h_lat = self._metrics.histogram("plugin_latency_seconds")

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
            self._metrics.counter(
                "plugin_calls_total", labels={"plugin": plugin_name, "action": action}
            ).inc()

        if self._tracer:
            # The ContextVar already holds the parent trace_id if we're inside
            # an outer span (e.g. HTTP request or another plugin call).
            # Tracer.span() reads it and continues the same trace automatically.
            with self._tracer.span(f"{plugin_name}.{action}") as span:
                span.set_attribute("plugin", plugin_name)
                span.set_attribute("action", action)
                # Propagate trace_id into payload metadata so sandboxed plugins
                # can log with the same trace_id even across process boundaries.
                if isinstance(payload, dict):
                    payload.setdefault(
                        "__trace__",
                        {
                            "trace_id": span.trace_id,
                            "parent_span_id": span.span_id,
                        },
                    )
                result = await next_call(
                    plugin_name, action, payload, handler, **kwargs
                )
                if isinstance(result, dict) and result.get("status") == "error":
                    span.set_status("error")
                    if self._metrics:
                        self._metrics.counter(
                            "plugin_errors_total",
                            labels={"plugin": plugin_name, "action": action},
                        ).inc()
                    if self._events:
                        self._events.emit_sync(
                            f"plugin.{plugin_name}.error",
                            {"action": action, "error": result.get("msg")},
                        )
        else:
            result = await next_call(plugin_name, action, payload, handler, **kwargs)
            if isinstance(result, dict) and result.get("status") == "error":
                if self._metrics:
                    self._metrics.counter(
                        "plugin_errors_total",
                        labels={"plugin": plugin_name, "action": action},
                    ).inc()
                if self._events:
                    self._events.emit_sync(
                        f"plugin.{plugin_name}.error",
                        {"action": action, "error": result.get("msg")},
                    )

        elapsed = time.monotonic() - t0
        if self._metrics:
            self._h_lat.observe(elapsed)

        return result
