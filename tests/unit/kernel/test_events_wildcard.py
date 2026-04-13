import asyncio

import pytest

from xcore.kernel.events.bus import EventBus
from xcore.kernel.events.section import Event


@pytest.mark.asyncio
async def test_wildcard_subscription():
    bus = EventBus()
    received = []

    @bus.on("user.*")
    async def on_user_event(event: Event):
        received.append(event.name)

    await bus.emit("user.created", {"id": 1})
    await bus.emit("user.deleted", {"id": 1})
    await bus.emit("product.created", {"id": 2})

    assert "user.created" in received
    assert "user.deleted" in received
    assert "product.created" not in received


@pytest.mark.asyncio
async def test_wildcard_priority():
    bus = EventBus()
    order = []

    @bus.on("user.*", priority=10)
    async def low_priority(event: Event):
        order.append("low")

    @bus.on("user.created", priority=100)
    async def high_priority(event: Event):
        order.append("high")

    await bus.emit("user.created", gather=False)

    assert order == ["high", "low"]


@pytest.mark.asyncio
async def test_wildcard_once():
    bus = EventBus()
    count = 0

    @bus.once("user.*")
    async def once_handler(event: Event):
        nonlocal count
        count += 1

    await bus.emit("user.created")
    await bus.emit("user.updated")

    assert count == 1
    assert bus.handler_count("user.*") == 0


@pytest.mark.asyncio
async def test_multiple_wildcards():
    bus = EventBus()
    received = []

    @bus.on("*.created")
    async def on_created(event: Event):
        received.append(f"created:{event.name}")

    @bus.on("user.*")
    async def on_user(event: Event):
        received.append(f"user:{event.name}")

    await bus.emit("user.created")

    assert "created:user.created" in received
    assert "user:user.created" in received
