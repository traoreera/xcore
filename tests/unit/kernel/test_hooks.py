"""
Tests for HookManager.
"""

import asyncio

import pytest

from xcore.kernel.events.hooks import HookManager
from xcore.kernel.events.section import Event


class TestHookManager:
    """Test HookManager functionality."""

    @pytest.fixture
    def hook_manager(self):
        """Create fresh HookManager."""
        return HookManager()

    @pytest.mark.asyncio
    async def test_register_and_emit(self, hook_manager):
        """Test basic registration and emission."""
        handler_called = []

        def handler(event):
            handler_called.append(event.data)
            return "result"

        hook_manager.register("test.event", handler)
        results = await hook_manager.emit("test.event", {"key": "value"})

        assert len(handler_called) == 1
        assert handler_called[0]["key"] == "value"
        assert len(results) == 1
        assert results[0].result == "result"
        assert results[0].hook_name == "handler"

    @pytest.mark.asyncio
    async def test_emit_no_handlers(self, hook_manager):
        """Test emitting with no handlers."""
        results = await hook_manager.emit("test.event", {"key": "value"})
        assert results == []

    @pytest.mark.asyncio
    async def test_async_handler(self, hook_manager):
        """Test async handler."""
        handler_called = []

        async def async_handler(event):
            await asyncio.sleep(0.01)
            handler_called.append(event.data)
            return "async_result"

        hook_manager.register("test.event", async_handler)
        results = await hook_manager.emit("test.event", {"key": "value"})

        assert len(handler_called) == 1
        assert results[0].result == "async_result"

    @pytest.mark.asyncio
    async def test_priority_order(self, hook_manager):
        """Test handler priority execution order."""
        execution_order = []

        def low_priority(event):
            execution_order.append("low")
            return "low"

        def high_priority(event):
            execution_order.append("high")
            return "high"

        def medium_priority(event):
            execution_order.append("medium")
            return "medium"

        hook_manager.register("test.event", low_priority, priority=100)
        hook_manager.register("test.event", high_priority, priority=10)
        hook_manager.register("test.event", medium_priority, priority=50)

        await hook_manager.emit("test.event", {})

        assert execution_order == ["high", "medium", "low"]

    @pytest.mark.asyncio
    async def test_once_handler(self, hook_manager):
        """Test one-time handler."""
        handler_called = []

        def handler(event):
            handler_called.append(event)
            return "result"

        hook_manager.register("test.event", handler, once=True)

        await hook_manager.emit("test.event", {})
        await hook_manager.emit("test.event", {})

        assert len(handler_called) == 1

    @pytest.mark.asyncio
    async def test_unregister(self, hook_manager):
        """Test unregistering handlers."""
        handler_called = []

        def handler(event):
            handler_called.append(event)

        hook_manager.register("test.event", handler)
        result = hook_manager.unregister("test.event", handler)

        assert result is True

        await hook_manager.emit("test.event", {})
        assert len(handler_called) == 0

    def test_unregister_nonexistent(self, hook_manager):
        """Test unregistering from nonexistent event."""

        def handler(event):
            pass

        result = hook_manager.unregister("nonexistent", handler)
        assert result is False

    @pytest.mark.asyncio
    async def test_wildcard_pattern(self, hook_manager):
        """Test wildcard pattern matching."""
        handler_called = []

        def handler(event):
            handler_called.append(event.name)

        hook_manager.register("test.*", handler)

        await hook_manager.emit("test.event1", {})
        await hook_manager.emit("test.event2", {})
        await hook_manager.emit("other.event", {})

        assert len(handler_called) == 2
        assert "test.event1" in handler_called
        assert "test.event2" in handler_called
        assert "other.event" not in handler_called

    @pytest.mark.asyncio
    async def test_decorator_syntax(self, hook_manager):
        """Test @hook_manager.on decorator."""
        handler_called = []

        @hook_manager.on("test.event")
        def handler(event):
            handler_called.append(event.data)
            return "decorated"

        results = await hook_manager.emit("test.event", {"key": "value"})

        assert len(handler_called) == 1
        assert results[0].result == "decorated"

    @pytest.mark.asyncio
    async def test_decorator_once(self, hook_manager):
        """Test @hook_manager.once decorator."""
        handler_called = []

        @hook_manager.once("test.event")
        def handler(event):
            handler_called.append(event)

        await hook_manager.emit("test.event", {})
        await hook_manager.emit("test.event", {})

        assert len(handler_called) == 1

    @pytest.mark.asyncio
    async def test_stop_propagation(self, hook_manager):
        """Test stopping event propagation."""
        handler_called = []

        def first_handler(event):
            event.stop_propagation = True
            if not event.stop_propagation:
                handler_called.append("first")

        def second_handler(event):
            handler_called.append("second")

        hook_manager.register("test.event", first_handler, priority=100)
        hook_manager.register("test.event", second_handler, priority=50)

        await hook_manager.emit("test.event", {})

        assert handler_called == ["second"]

    @pytest.mark.asyncio
    async def test_cancelled_event(self, hook_manager):
        """Test cancelled event."""
        handler_called = []

        def handler(event):
            handler_called.append("called")
            return "result"

        hook_manager.register("test.event", handler)

        event = Event(name="test.event", cancelled=True)
        results = await hook_manager._execute_single_hook(
            hook_manager._hooks["test.event"][0], event, "test.event"
        )

        assert results.cancelled is True

    @pytest.mark.asyncio
    async def test_handler_error(self, hook_manager):
        """Test handler error handling."""

        def error_handler(event):
            raise ValueError("Test error")

        hook_manager.register("test.event", error_handler)
        results = await hook_manager.emit("test.event", {})

        assert len(results) == 1
        assert results[0].error is not None
        assert isinstance(results[0].error, ValueError)

    @pytest.mark.asyncio
    async def test_timeout_sync_handler(self, hook_manager):
        """Test timeout on synchronous handler."""

        def slow_handler(event):
            import time

            time.sleep(0.5)
            return "result"

        hook_manager.register("test.event", slow_handler, timeout=0.1)

        results = await hook_manager.emit("test.event", {})

        assert len(results) == 1
        assert results[0].error is not None

    @pytest.mark.asyncio
    async def test_timeout_async_handler(self, hook_manager):
        """Test timeout on async handler."""

        async def slow_handler(event):
            await asyncio.sleep(0.5)
            return "result"

        hook_manager.register("test.event", slow_handler, timeout=0.1)

        results = await hook_manager.emit("test.event", {})

        assert len(results) == 1
        assert results[0].error is not None

    @pytest.mark.asyncio
    async def test_metrics_tracking(self, hook_manager):
        """Test metrics tracking."""

        def handler(event):
            return "result"

        hook_manager.register("test.event", handler)

        await hook_manager.emit("test.event", {})
        await hook_manager.emit("test.event", {})

        metrics = hook_manager.get_metrics("test.event")
        assert metrics["total_emissions"] == 2
        assert metrics["total_hooks_executed"] == 2
        assert metrics["total_errors"] == 0
        assert metrics["avg_execution_time_ms"] > 0

    def test_list_hooks(self, hook_manager):
        """Test listing hooks."""

        def handler1(event):
            pass

        def handler2(event):
            pass

        hook_manager.register("event1", handler1, priority=10)
        hook_manager.register("event2", handler2, priority=20, once=True)

        hooks = hook_manager.list_hooks()

        assert "event1" in hooks
        assert "event2" in hooks
        assert hooks["event1"][0]["name"] == "handler1"
        assert hooks["event1"][0]["priority"] == 10
        assert hooks["event2"][0]["once"] is True

    def test_list_hooks_filtered(self, hook_manager):
        """Test listing hooks with filter."""

        def handler(event):
            pass

        hook_manager.register("test.*", handler)

        hooks = hook_manager.list_hooks("test.event")
        assert "test.*" in hooks

    def test_clear_event(self, hook_manager):
        """Test clearing specific event."""

        def handler(event):
            pass

        hook_manager.register("event1", handler)
        hook_manager.register("event2", handler)

        hook_manager.clear("event1")

        hooks = hook_manager.list_hooks()
        assert "event1" not in hooks
        assert "event2" in hooks

    def test_clear_all(self, hook_manager):
        """Test clearing all events."""

        def handler(event):
            pass

        hook_manager.register("event1", handler)
        hook_manager.register("event2", handler)

        hook_manager.clear()

        hooks = hook_manager.list_hooks()
        assert len(hooks) == 0
