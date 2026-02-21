"""
Event Bus — système de hooks/événements asynchrones.
Inspiré d'un EventEmitter avec priorités et filtres.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("integrations.events")


@dataclass
class Event:
    """Représente un événement déclenché dans le système."""

    name: str
    data: Dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None
    propagate: bool = True  # Si False, stoppe la propagation après le premier handler

    def stop_propagation(self):
        self.propagate = False


@dataclass
class HandlerEntry:
    handler: Callable
    priority: int = 50
    once: bool = False  # Se désenregistre après la première exécution
    name: Optional[str] = None


class EventBus:
    """
    Bus d'événements avec priorités et support async.

    Usage:
        bus = EventBus()

        @bus.on("user.created")
        async def on_user_created(event: Event):
            print(f"Nouvel utilisateur: {event.data}")

        await bus.emit("user.created", data={"username": "alice"})

        # One-shot
        @bus.once("app.startup")
        async def on_startup(event): ...

        # Priorité (100 = haute, 0 = basse)
        @bus.on("data.process", priority=100)
        async def high_priority_handler(event): ...
    """

    def __init__(self):
        self._handlers: Dict[str, List[HandlerEntry]] = {}

    # ── ENREGISTREMENT ────────────────────────────────────────

    def on(
        self,
        event_name: str,
        priority: int = 50,
        name: Optional[str] = None,
    ) -> Callable:
        """Décorateur pour s'abonner à un événement."""

        def decorator(handler: Callable) -> Callable:
            self.subscribe(event_name, handler, priority=priority, name=name)
            return handler

        return decorator

    def once(self, event_name: str, priority: int = 50) -> Callable:
        """Décorateur pour s'abonner une seule fois."""

        def decorator(handler: Callable) -> Callable:
            self.subscribe(event_name, handler, priority=priority, once=True)
            return handler

        return decorator

    def subscribe(
        self,
        event_name: str,
        handler: Callable,
        priority: int = 50,
        once: bool = False,
        name: Optional[str] = None,
    ):
        """S'abonne à un événement."""
        if event_name not in self._handlers:
            self._handlers[event_name] = []

        entry = HandlerEntry(
            handler=handler,
            priority=priority,
            once=once,
            name=name or getattr(handler, "__name__", str(handler)),
        )
        self._handlers[event_name].append(entry)
        self._handlers[event_name].sort(key=lambda e: e.priority, reverse=True)
        logger.debug(f"Handler enregistré: {entry.name} → {event_name} [p={priority}]")

    def unsubscribe(self, event_name: str, handler: Callable):
        """Désabonne un handler."""
        if event_name in self._handlers:
            self._handlers[event_name] = [
                e for e in self._handlers[event_name] if e.handler != handler
            ]

    # ── ÉMISSION ──────────────────────────────────────────────

    async def emit(
        self,
        event_name: str,
        data: Optional[Dict[str, Any]] = None,
        source: Optional[str] = None,
        gather: bool = True,
    ) -> List[Any]:
        """
        Émet un événement de façon asynchrone.
        gather=True : tous les handlers sont exécutés en parallèle.
        gather=False : handlers exécutés séquentiellement (respecte stop_propagation).
        """
        event = Event(name=event_name, data=data or {}, source=source)
        handlers = list(self._handlers.get(event_name, []))

        if not handlers:
            logger.debug(f"Aucun handler pour: {event_name}")
            return []

        results = []
        to_remove = []

        if gather:
            tasks = [self._call_handler(e, event) for e in handlers]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for entry, result in zip(handlers, results):
                if isinstance(result, Exception):
                    logger.error(f"Handler {entry.name} erreur: {result}")
                if entry.once:
                    to_remove.append(entry)
        else:
            for entry in handlers:
                if not event.propagate:
                    break
                try:
                    result = await self._call_handler(entry, event)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Handler {entry.name} erreur: {e}")
                if entry.once:
                    to_remove.append(entry)

        # Nettoyage des one-shot
        for entry in to_remove:
            self._handlers[event_name].remove(entry)

        return results

    def emit_sync(self, event_name: str, data: Optional[Dict[str, Any]] = None) -> None:
        """Émet un événement de façon synchrone (fire-and-forget)."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.emit(event_name, data))
        except RuntimeError:
            asyncio.run(self.emit(event_name, data))

    @staticmethod
    async def _call_handler(entry: HandlerEntry, event: Event) -> Any:
        if asyncio.iscoroutinefunction(entry.handler):
            return await entry.handler(event)
        return entry.handler(event)

    # ── INTROSPECTION ─────────────────────────────────────────

    def list_events(self) -> Dict[str, List[str]]:
        return {
            name: [e.name for e in entries] for name, entries in self._handlers.items()
        }

    def handler_count(self, event_name: str) -> int:
        return len(self._handlers.get(event_name, []))

    def clear(self, event_name: Optional[str] = None):
        if event_name:
            self._handlers.pop(event_name, None)
        else:
            self._handlers.clear()


# Singleton global
_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus
