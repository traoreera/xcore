import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from xcore.kernel.runtime.loader import PluginLoader
from xcore.kernel.runtime.supervisor import Middleware, PluginSupervisor


class DummyMiddleware(Middleware):
    def __init__(self, name, calls):
        self.name = name
        self.calls = calls

    async def __call__(self, plugin_name, action, payload, next_call, handler=None, **kwargs):
        self.calls.append(f"before:{self.name}")
        res = await next_call(plugin_name, action, payload, handler, **kwargs)
        self.calls.append(f"after:{self.name}")
        return res


@pytest.mark.asyncio
async def test_dynamic_middleware_registration():
    from xcore.kernel.context import KernelContext
    config = MagicMock()
    config.plugins.directory = "plugins"
    services = MagicMock()
    services.as_dict.return_value = {}
    ctx = KernelContext(
        config=config.plugins,
        services=services,
        events=MagicMock(),
        hooks=MagicMock(),
        registry=MagicMock(),
        metrics=MagicMock(),
        tracer=MagicMock(),
        health=MagicMock(),
    )

    supervisor = PluginSupervisor(ctx)

    # Mock boot process to avoid actual loading
    supervisor._loader = MagicMock()
    supervisor._loader.has.return_value = True
    handler = AsyncMock()
    handler.call.return_value = {"status": "ok"}
    supervisor._loader.get.return_value = handler

    from xcore.kernel.runtime.middlewares import MiddlewarePipeline
    supervisor._pipeline = MiddlewarePipeline([], supervisor._dispatch)

    calls = []
    m1 = DummyMiddleware("m1", calls)
    supervisor.register_middleware(m1)

    await supervisor.call("test_plugin", "test_action", {})

    assert calls == ["before:m1", "after:m1"]

    calls.clear()
    m2 = DummyMiddleware("m2", calls)
    supervisor.register_middleware(m2, first=True)

    await supervisor.call("test_plugin", "test_action", {})

    assert calls == ["before:m2", "before:m1", "after:m1", "after:m2"]
