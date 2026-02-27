"""
Tests for EventBus and event system.
"""

import asyncio

import pytest

from xcore.kernel.events.bus import Event, EventBus


class TestEvent:
    """Test Event dataclass."""

    def test_event_creation(self):
        """Test creating an event."""
        event = Event(name="test.event", data={"key": "value"}, source="test")

        assert event.name == "test.event"
        assert event.data == {"key": "value"}
        assert event.source == "test"
        assert event.propagate is True
        assert event.cancelled is False

    def test_event_stop(self):
        """Test stopping event propagation."""
        event = Event(name="test.event")
        assert event.propagate is True

        event.stop()
        assert event.propagate is False

    def test_event_cancel(self):
        """Test cancelling an event."""
        event = Event(name="test.event")
        assert event.cancelled is False

        event.cancel()
        assert event.cancelled is True


class TestEventBus:
    """Test EventBus functionality."""

    @pytest.fixture
    def event_bus(self):
        """Create fresh EventBus."""
        return EventBus()

    @pytest.mark.asyncio
    async def test_subscribe_and_emit(self, event_bus):
        """Test basic subscription and emission."""
        handler_called = []

        async def handler(event):
            handler_called.append(event.data)

        event_bus.subscribe("test.event", handler)
        await event_bus.emit("test.event", {"message": "hello"})

        assert len(handler_called) == 1
        assert handler_called[0]["message"] == "hello"

    @pytest.mark.asyncio
    async def test_emit_no_handlers(self, event_bus):
        """Test emitting with no handlers."""
        results = await event_bus.emit("test.event", {"message": "hello"})
        assert results == []

    @pytest.mark.asyncio
    async def test_unsubscribe(self, event_bus):
        """Test unsubscribing from events."""
        handler_called = []

        async def handler(event):
            handler_called.append(event)

        event_bus.subscribe("test.event", handler)
        event_bus.unsubscribe("test.event", handler)

        await event_bus.emit("test.event", {})
        assert len(handler_called) == 0

    @pytest.mark.asyncio
    async def test_once_handler(self, event_bus):
        """Test one-time handler."""
        handler_called = []

        async def handler(event):
            handler_called.append(event)

        event_bus.subscribe("test.event", handler, once=True)

        await event_bus.emit("test.event", {})
        await event_bus.emit("test.event", {})  # Second emit

        assert len(handler_called) == 1  # Handler removed after first call

    @pytest.mark.asyncio
    async def test_priority_order(self, event_bus):
        """Test handler priority."""
        execution_order = []

        async def low_priority(event):
            execution_order.append("low")

        async def high_priority(event):
            execution_order.append("high")

        async def medium_priority(event):
            execution_order.append("medium")

        event_bus.subscribe("test.event", low_priority, priority=10)
        event_bus.subscribe("test.event", high_priority, priority=100)
        event_bus.subscribe("test.event", medium_priority, priority=50)

        await event_bus.emit("test.event", {}, gather=False)

        assert execution_order == ["high", "medium", "low"]

    @pytest.mark.asyncio
    async def test_stop_propagation(self, event_bus):
        """Test stopping event propagation."""
        handler_called = []

        async def first_handler(event):
            handler_called.append("first")
            event.stop()

        async def second_handler(event):
            handler_called.append("second")

        event_bus.subscribe("test.event", first_handler, priority=100)
        event_bus.subscribe("test.event", second_handler, priority=50)

        await event_bus.emit("test.event", {}, gather=False)

        assert handler_called == ["first"]  # Second handler not called

    @pytest.mark.asyncio
    async def test_decorator_syntax(self, event_bus):
        """Test @bus.on decorator."""
        handler_called = []

        @event_bus.on("test.event")
        async def handler(event):
            handler_called.append(event.data)

        await event_bus.emit("test.event", {"key": "value"})

        assert len(handler_called) == 1
        assert handler_called[0]["key"] == "value"

    @pytest.mark.asyncio
    async def test_emit_sync(self, event_bus):
        """Test synchronous emit."""
        handler_called = []

        @event_bus.on("test.event")
        async def handler(event):
            handler_called.append(event.data)

        event_bus.emit_sync("test.event", {"key": "value"})
        await asyncio.sleep(0.1)  # Wait for async task

        assert len(handler_called) == 1

    @pytest.mark.asyncio
    async def test_handler_count(self, event_bus):
        """Test handler count."""
        assert event_bus.handler_count("test.event") == 0

        async def handler(event):
            pass

        event_bus.subscribe("test.event", handler)
        assert event_bus.handler_count("test.event") == 1

        event_bus.subscribe("test.event", handler)
        assert event_bus.handler_count("test.event") == 2

    @pytest.mark.asyncio
    async def test_clear_event(self, event_bus):
        """Test clearing event handlers."""

        async def handler(event):
            pass

        event_bus.subscribe("test.event", handler)
        event_bus.clear("test.event")

        assert event_bus.handler_count("test.event") == 0

    @pytest.mark.asyncio
    async def test_clear_all(self, event_bus):
        """Test clearing all handlers."""

        async def handler1(event):
            pass

        async def handler2(event):
            pass

        event_bus.subscribe("event1", handler1)
        event_bus.subscribe("event2", handler2)

        event_bus.clear()

        assert event_bus.handler_count("event1") == 0
        assert event_bus.handler_count("event2") == 0

    @pytest.mark.asyncio
    async def test_handler_error_handling(self, event_bus, caplog):
        """Test handler error handling."""

        async def error_handler(event):
            raise ValueError("Test error")

        event_bus.subscribe("test.event", error_handler)

        results = await event_bus.emit("test.event", {})

        assert len(results) == 0
        assert "Test error" in caplog.text

    @pytest.mark.asyncio
    async def test_gather_execution(self, event_bus):
        """Test parallel execution with gather."""
        execution_times = []

        async def slow_handler(event):
            await asyncio.sleep(0.1)
            execution_times.append("slow")
            return "slow_result"

        async def fast_handler(event):
            execution_times.append("fast")
            return "fast_result"

        event_bus.subscribe("test.event", slow_handler)
        event_bus.subscribe("test.event", fast_handler)

        results = await event_bus.emit("test.event", {}, gather=True)

        assert set(results) == {"slow_result", "fast_result"}

    def test_list_events(self, event_bus):
        """Test listing events."""

        async def handler(event):
            pass

        event_bus.subscribe("event1", handler)
        event_bus.subscribe("event2", handler)

        events = event_bus.list_events()

        assert "event1" in events
        assert "event2" in events
