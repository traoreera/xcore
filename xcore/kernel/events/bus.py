"""
— EventBus v2: Consolidated version (merged integration/core/events.py + hooks v1).
A single bus for both uses:
- Application events (emit/subscribe) — asynchronous with priority
- Compatibility with HookManager v1 (on/once/emit)
Removes the duplicate EventBus present in integration/core/events.py and hooks/hooks.py.
"""

from __future__ import annotations

import asyncio
import contextlib
import fnmatch
import inspect
import re
import time
from collections import deque
from typing import TYPE_CHECKING, Any, Callable, Pattern

from .section import Event, _HandlerEntry

if TYPE_CHECKING:
    from ...services.cache import CacheService

from ...kernel.observability import get_logger

logger = get_logger("xcore.events.bus")


class EventBus:
    """
    Asynchronous event bus with priorities and one-shot handlers.

    Use:
    ```python
        bus = EventBus()

        @bus.on("user.created")
        async def welcome(event: Event):
            await send_email(event.data["email"])

        await bus.emit("user.created", {"email": "alice@example.com"})

        # Fire-and-forgetwith sync emit
        bus.emit_sync("server.tick", {})
    ```
    """

    def __init__(self, cache: "CacheService" = None, max_audit: int = 10_000) -> None:
        self._handlers: dict[str, list[_HandlerEntry]] = {}
        self._wildcard_patterns: dict[str, Pattern] = {}

        # Supervision : journal borné des émissions + métriques agrégées par
        # event, même pattern que PermissionEngine._audit_log — pour voir ce
        # qui s'est réellement passé plutôt que de deviner depuis les logs.
        self._emission_log: deque[dict] = deque(maxlen=max_audit)
        self._stats: dict[str, dict] = {}

    # ── Enregistrement ────────────────────────────────────────

    def on(
        self, event_name: str, priority: int = 50, name: str | None = None
    ) -> Callable:
        """decorator to subscribe to an event."""

        def decorator(fn: Callable) -> Callable:
            self.subscribe(event_name, fn, priority=priority, name=name)
            return fn

        return decorator

    def once(self, event_name: str, priority: int = 50) -> Callable:
        """Décorateur pour s'abonner une seule fois."""

        def decorator(fn: Callable) -> Callable:
            self.subscribe(event_name, fn, priority=priority, once=True)
            return fn

        return decorator

    def subscribe(
        self,
        event_name: str,
        handler: Callable,
        priority: int = 50,
        once: bool = False,
        name: str | None = None,
    ) -> None:
        if event_name not in self._handlers:
            self._handlers[event_name] = []

        # If it's a wildcard, pre-compile and store it
        if (
            any(c in event_name for c in "*?[]")
            and event_name not in self._wildcard_patterns
        ):
            self._wildcard_patterns[event_name] = re.compile(
                fnmatch.translate(event_name)
            )

        entry = _HandlerEntry(
            handler=handler,
            is_async=inspect.iscoroutinefunction(handler),
            priority=priority,
            once=once,
            name=name or getattr(handler, "__name__", str(handler)),
            pattern=event_name,
        )
        self._handlers[event_name].append(entry)
        self._handlers[event_name].sort(key=lambda e: e.priority, reverse=True)

    def unsubscribe(self, event_name: str, handler: Callable) -> None:
        if event_name in self._handlers:
            self._handlers[event_name] = [
                e for e in self._handlers[event_name] if e.handler is not handler
            ]
            # Clean up the pattern list and wildcard patterns if empty
            if not self._handlers[event_name]:
                self._handlers.pop(event_name)
                self._wildcard_patterns.pop(event_name, None)

    # ── Émission ──────────────────────────────────────────────

    async def emit(
        self,
        event_name: str,
        data: dict[str, Any] | None = None,
        source: str | None = None,
        gather: bool = True,
    ) -> list[Any]:
        """
        Issues an event.
        `gather=True` → handlers executed in parallel (`asyncio.gather`)
        `gather=False` → sequential, `propagate` respected
        eg:
        ```python
            await bus.emit("user.created", {"email": "alice@example.com"})
        ```
        """
        t0 = time.monotonic()
        event = Event(name=event_name, data=data or {}, source=source)

        # 1. Exact match lookup (O(1))
        matched_handlers: list[_HandlerEntry] = []
        if event_name in self._handlers:
            matched_handlers.extend(self._handlers[event_name])

        # 2. Wildcard lookup (O(N_wildcards)) - much faster than O(N_all)
        for pattern, regex in self._wildcard_patterns.items():
            # If the pattern is EXACTLY event_name, it was already handled above.
            if pattern == event_name:
                continue
            if regex.match(event_name):
                matched_handlers.extend(self._handlers[pattern])

        if not matched_handlers:
            self._audit_emission(
                event_name, source, matched=0, errors=0, duration_ms=0.0
            )
            return []

        # Sort by priority across all matched patterns
        matched_handlers.sort(key=lambda e: e.priority, reverse=True)

        results: list[Any] = []
        to_remove: list[_HandlerEntry] = []
        error_count = 0

        if gather:
            # Fast-path: only one handler
            if len(matched_handlers) == 1:
                entry = matched_handlers[0]
                try:
                    result = (
                        await entry.handler(event)
                        if entry.is_async
                        else entry.handler(event)
                    )
                    results.append(result)
                except Exception as e:
                    error_count += 1
                    logger.error(
                        "event handler error",
                        handler=entry.name,
                        event=event_name,
                        error=str(e),
                    )
                if entry.once:
                    to_remove.append(entry)
            else:
                # Multiple handlers: parallel execution
                async def _call_sync(h, e):
                    return h(e)

                tasks = [
                    (
                        entry.handler(event)
                        if entry.is_async
                        else _call_sync(entry.handler, event)
                    )
                    for entry in matched_handlers
                ]

                raw = await asyncio.gather(*tasks, return_exceptions=True)
                for entry, result in zip(matched_handlers, raw):
                    if isinstance(result, Exception):
                        error_count += 1
                        logger.error(
                            "event handler error",
                            handler=entry.name,
                            event=event_name,
                            error=str(result),
                        )
                    else:
                        results.append(result)
                    if entry.once:
                        to_remove.append(entry)
        else:
            for entry in matched_handlers:
                if not event.propagate or event.cancelled:
                    break
                try:
                    result = (
                        await entry.handler(event)
                        if entry.is_async
                        else entry.handler(event)
                    )
                    results.append(result)
                except Exception as e:
                    error_count += 1
                    logger.error(
                        "event handler error", handler=entry.name, error=str(e)
                    )
                if entry.once:
                    to_remove.append(entry)

        for entry in to_remove:
            # Use entry.pattern for O(1) removal
            entries = self._handlers.get(entry.pattern)
            if entries:
                with contextlib.suppress(ValueError):
                    entries.remove(entry)
                    if not entries:
                        self._handlers.pop(entry.pattern, None)
                        self._wildcard_patterns.pop(entry.pattern, None)

        duration_ms = (time.monotonic() - t0) * 1000
        self._audit_emission(
            event_name,
            source,
            matched=len(matched_handlers),
            errors=error_count,
            duration_ms=duration_ms,
        )
        return results

    def emit_sync(self, event_name: str, data: dict[str, Any] | None = None) -> None:
        """Fire-and-forget with sync emit."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.emit(event_name, data))
        except RuntimeError:
            asyncio.run(self.emit(event_name, data))

    # ── Supervision ───────────────────────────────────────────

    def _audit_emission(
        self,
        event_name: str,
        source: str | None,
        matched: int,
        errors: int,
        duration_ms: float,
    ) -> None:
        entry = {
            "event": event_name,
            "source": source,
            "handlers_matched": matched,
            "errors": errors,
            "duration_ms": round(duration_ms, 2),
            "timestamp": time.time(),
        }
        self._emission_log.append(entry)

        stats = self._stats.setdefault(
            event_name, {"emissions": 0, "errors": 0, "total_duration_ms": 0.0}
        )
        stats["emissions"] += 1
        stats["errors"] += errors
        stats["total_duration_ms"] += duration_ms

    def recent_emissions(
        self, event_name: str | None = None, limit: int = 100
    ) -> list[dict]:
        """Journal des émissions récentes — le plus récent en dernier."""
        from itertools import islice

        it = reversed(self._emission_log)
        if event_name:
            it = (e for e in it if e["event"] == event_name)
        results = list(islice(it, limit))
        results.reverse()
        return results

    def stats(self, event_name: str | None = None) -> dict:
        """Statistiques agrégées par event : émissions, erreurs, durée moyenne."""
        if event_name:
            s = self._stats.get(event_name)
            if not s:
                return {}
            return {
                "emissions": s["emissions"],
                "errors": s["errors"],
                "avg_duration_ms": round(s["total_duration_ms"] / s["emissions"], 2),
            }
        return {
            name: {
                "emissions": s["emissions"],
                "errors": s["errors"],
                "avg_duration_ms": (
                    round(s["total_duration_ms"] / s["emissions"], 2)
                    if s["emissions"]
                    else 0.0
                ),
            }
            for name, s in self._stats.items()
        }

    # ── Introspection ─────────────────────────────────────────

    def list_events(self) -> dict[str, list[str]]:
        """List all events and their handlers."""
        return {
            name: [e.name for e in entries] for name, entries in self._handlers.items()
        }

    def handler_count(self, event_name: str) -> int:
        """Returns the number of handlers for an event."""
        return len(self._handlers.get(event_name, []))

    def clear(self, event_name: str | None = None) -> None:
        """Clear the bus or a specific event."""
        if event_name:
            self._handlers.pop(event_name, None)
            self._wildcard_patterns.pop(event_name, None)
        else:
            self._handlers.clear()
            self._wildcard_patterns.clear()
