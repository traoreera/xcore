"""
bus.py — EventBus v2 : version consolidée (fusionné integration/core/events.py + hooks v1).

Un seul bus pour les deux usages :
  - Événements applicatifs (emit / subscribe) — async avec priorités
  - Compatibilité avec le HookManager v1 (on / once / emit)

Supprime le doublon EventBus présent dans integration/core/events.py et hooks/hooks.py.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger("xcore.events.bus")


@dataclass
class Event:
    """Événement structuré passé aux handlers."""
    name: str
    data: dict[str, Any] = field(default_factory=dict)
    source: str | None = None
    propagate: bool = True
    cancelled: bool = False

    def stop(self) -> None:
        self.propagate = False

    def cancel(self) -> None:
        self.cancelled = True


@dataclass
class _HandlerEntry:
    handler: Callable
    priority: int = 50
    once: bool = False
    name: str = ""


class EventBus:
    """
    Bus d'événements asynchrone avec priorités et one-shot handlers.

    Usage:
        bus = EventBus()

        @bus.on("user.created")
        async def welcome(event: Event):
            await send_email(event.data["email"])

        await bus.emit("user.created", {"email": "alice@example.com"})

        # Fire-and-forget depuis du code synchrone
        bus.emit_sync("server.tick", {})
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[_HandlerEntry]] = {}

    # ── Enregistrement ────────────────────────────────────────

    def on(self, event_name: str, priority: int = 50, name: str | None = None) -> Callable:
        """Décorateur pour s'abonner à un événement."""
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
        entry = _HandlerEntry(
            handler=handler,
            priority=priority,
            once=once,
            name=name or getattr(handler, "__name__", str(handler)),
        )
        self._handlers[event_name].append(entry)
        self._handlers[event_name].sort(key=lambda e: e.priority, reverse=True)

    def unsubscribe(self, event_name: str, handler: Callable) -> None:
        if event_name in self._handlers:
            self._handlers[event_name] = [
                e for e in self._handlers[event_name] if e.handler is not handler
            ]

    # ── Émission ──────────────────────────────────────────────

    async def emit(
        self,
        event_name: str,
        data: dict[str, Any] | None = None,
        source: str | None = None,
        gather: bool = True,
    ) -> list[Any]:
        """
        Émet un événement.

        gather=True  → handlers exécutés en parallèle (asyncio.gather)
        gather=False → séquentiels, stop_propagation respecté
        """
        event = Event(name=event_name, data=data or {}, source=source)
        handlers = list(self._handlers.get(event_name, []))
        if not handlers:
            return []

        results: list[Any] = []
        to_remove: list[_HandlerEntry] = []

        async def _call(entry: _HandlerEntry) -> Any:
            if asyncio.iscoroutinefunction(entry.handler):
                return await entry.handler(event)
            return entry.handler(event)

        if gather:
            raw = await asyncio.gather(*[_call(e) for e in handlers], return_exceptions=True)
            for entry, result in zip(handlers, raw):
                if isinstance(result, Exception):
                    logger.error(f"Handler '{entry.name}' erreur pour '{event_name}': {result}")
                else:
                    results.append(result)
                if entry.once:
                    to_remove.append(entry)
        else:
            for entry in handlers:
                if not event.propagate or event.cancelled:
                    break
                try:
                    result = await _call(entry)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Handler '{entry.name}' erreur : {e}")
                if entry.once:
                    to_remove.append(entry)

        for entry in to_remove:
            if event_name in self._handlers:
                try:
                    self._handlers[event_name].remove(entry)
                except ValueError:
                    pass

        return results

    def emit_sync(self, event_name: str, data: dict[str, Any] | None = None) -> None:
        """Fire-and-forget depuis du code synchrone."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.emit(event_name, data))
        except RuntimeError:
            asyncio.run(self.emit(event_name, data))

    # ── Introspection ─────────────────────────────────────────

    def list_events(self) -> dict[str, list[str]]:
        return {
            name: [e.name for e in entries]
            for name, entries in self._handlers.items()
        }

    def handler_count(self, event_name: str) -> int:
        return len(self._handlers.get(event_name, []))

    def clear(self, event_name: str | None = None) -> None:
        if event_name:
            self._handlers.pop(event_name, None)
        else:
            self._handlers.clear()
