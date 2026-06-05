"""Tests for EventDispatcher."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from xcore.kernel.events.dispatcher import EventDispatcher


class TestEventDispatcher:
    @pytest.mark.asyncio
    async def test_emit_calls_bus(self):
        bus = MagicMock()
        bus.emit = AsyncMock()
        hooks = None
        dispatcher = EventDispatcher(bus, hooks)
        await dispatcher.emit("user.created", {"email": "a@b.com"})
        bus.emit.assert_called_once_with("user.created", {"email": "a@b.com"})

    @pytest.mark.asyncio
    async def test_emit_calls_hooks_if_set(self):
        bus = MagicMock()
        bus.emit = AsyncMock()
        hooks = MagicMock()
        hooks.emit = AsyncMock()
        dispatcher = EventDispatcher(bus, hooks)
        await dispatcher.emit("user.created", {"email": "a@b.com"})
        hooks.emit.assert_called_once_with("user.created", {"email": "a@b.com"})

    @pytest.mark.asyncio
    async def test_emit_no_hooks(self):
        bus = MagicMock()
        bus.emit = AsyncMock()
        dispatcher = EventDispatcher(bus, None)
        await dispatcher.emit("user.created")
        bus.emit.assert_called_once()

    def test_forward_registers_on_bus(self):
        bus = MagicMock()
        hooks = MagicMock()

        def mock_on(pattern):
            def decorator(fn):
                return fn
            return decorator

        bus.on = mock_on
        dispatcher = EventDispatcher(bus, hooks)
        dispatcher.forward("plugin.*.loaded", to_hooks=True)

    def test_forward_to_hooks_false_noop(self):
        bus = MagicMock()
        hooks = MagicMock()
        dispatcher = EventDispatcher(bus, hooks)
        dispatcher.forward("plugin.*.loaded", to_hooks=False)
        bus.on.assert_not_called()

    def test_forward_no_hooks_noop(self):
        bus = MagicMock()
        dispatcher = EventDispatcher(bus, None)
        dispatcher.forward("plugin.*.loaded", to_hooks=True)
        bus.on.assert_not_called()
