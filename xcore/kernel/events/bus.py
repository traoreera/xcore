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
import logging
import re
from typing import TYPE_CHECKING, Any, Callable, Pattern

from .section import Event, _HandlerEntry

if TYPE_CHECKING:
    from ...services.cache import CacheService


logger = logging.getLogger("xcore.events.bus")


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

    def __init__(self, cache: "CacheService" = None) -> None:
        self._handlers: dict[str, list[_HandlerEntry]] = {}
        self._wildcard_patterns: dict[str, Pattern] = {}

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
            return []

        # Sort by priority across all matched patterns
        matched_handlers.sort(key=lambda e: e.priority, reverse=True)

        results: list[Any] = []
        to_remove: list[_HandlerEntry] = []

        if gather:
            # Wrap synchronous handlers in coroutines only when gathering
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
                    logger.error(
                        f"Handler '{entry.name}' erreur pour '{event_name}': {result}"
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
                    if entry.is_async:
                        result = await entry.handler(event)
                    else:
                        result = entry.handler(event)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Handler '{entry.name}' erreur : {e}")
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
        return results

    def emit_sync(self, event_name: str, data: dict[str, Any] | None = None) -> None:
        """Fire-and-forget with sync emit."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.emit(event_name, data))
        except RuntimeError:
            asyncio.run(self.emit(event_name, data))

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
