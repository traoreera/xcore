
from unittest.mock import MagicMock

import pytest

from xcore.kernel.runtime.middlewares.middleware import (Middleware,
                                                         MiddlewarePipeline)


class MockMiddleware(Middleware):
    def __init__(self, name):
        self.name = name
        self.calls = []

    async def __call__(self, plugin_name, action, payload, next_call, handler, **kwargs):
        self.calls.append((plugin_name, action, payload))
        return await next_call(plugin_name, action, payload, handler, **kwargs)


@pytest.mark.asyncio
async def test_compiled_pipeline_execution_order():
    mw1 = MockMiddleware("mw1")
    mw2 = MockMiddleware("mw2")

    async def final_handler(p, a, pay, handler, **kwargs):
        return {"status": "ok", "handler_passed": handler is not None}

    handler = MagicMock()
    pipeline = MiddlewarePipeline([mw1, mw2], final_handler)

    result = await pipeline.execute("plugin", "action", {"data": 1}, handler=handler)

    assert result["status"] == "ok"
    assert result["handler_passed"] is True
    assert mw1.calls == [("plugin", "action", {"data": 1})]
    assert mw2.calls == [("plugin", "action", {"data": 1})]


@pytest.mark.asyncio
async def test_compiled_pipeline_handler_propagation():
    received_handlers = []

    class HandlerTrackingMiddleware(Middleware):
        async def __call__(self, plugin_name, action, payload, next_call, handler, **kwargs):
            received_handlers.append(handler)
            return await next_call(plugin_name, action, payload, handler, **kwargs)

    mw = HandlerTrackingMiddleware()

    async def final_handler(p, a, pay, handler, **kwargs):
        received_handlers.append(handler)
        return {"status": "ok"}

    handler = MagicMock()
    pipeline = MiddlewarePipeline([mw], final_handler)
    await pipeline.execute("p", "a", {}, handler=handler)

    assert len(received_handlers) == 2
    assert received_handlers[0] is handler
    assert received_handlers[1] is handler
