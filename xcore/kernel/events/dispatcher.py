"""
dispatcher.py — Pont entre EventBus et HookManager.

L'EventDispatcher coordonne les deux systèmes :
  - EventBus : événements applicatifs structurés (subscribe/emit)
  - HookManager : hooks prioritaires avec wildcards

Usage:
    dispatcher = EventDispatcher(bus, hooks)
    dispatcher.forward("plugin.*.loaded", to_hooks=True)
"""

from __future__ import annotations

from typing import Any


class EventDispatcher:
    """Coordonne EventBus et HookManager."""

    def __init__(self, bus, hooks) -> None:
        self._bus = bus
        self._hooks = hooks

    def forward(self, pattern: str, to_hooks: bool = True) -> None:
        """Redirige les événements d'un pattern du bus vers les hooks."""
        if not to_hooks or self._hooks is None:
            return

        @self._bus.on(pattern)
        async def _forward(event):
            await self._hooks.emit(event.name, event.data)

    async def emit(self, event_name: str, data: dict[str, Any] | None = None) -> None:
        """Émet simultanément sur le bus et les hooks."""
        await self._bus.emit(event_name, data)
        if self._hooks:
            await self._hooks.emit(event_name, data)
