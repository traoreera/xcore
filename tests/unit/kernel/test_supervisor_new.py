from unittest.mock import AsyncMock, MagicMock

import pytest

from xcore.kernel.runtime.middlewares.middleware import Middleware
from xcore.kernel.runtime.middlewares.retry import RetryMiddleware
from xcore.kernel.runtime.supervisor import PluginSupervisor


class MockHandler:
    def __init__(self, manifest):
        self.manifest = manifest
        self.call = AsyncMock()


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.directory = "/tmp/plugins"
    return config


@pytest.fixture
def supervisor(mock_config):
    from xcore.kernel.context import KernelContext
    services = MagicMock()
    services.as_dict.return_value = {}
    ctx = KernelContext(
        config=mock_config,
        services=services,
        events=MagicMock(),
        hooks=MagicMock(),
        registry=MagicMock(),
        metrics=MagicMock(),
        tracer=MagicMock(),
        health=MagicMock(),
    )
    return PluginSupervisor(ctx)


@pytest.mark.asyncio
async def test_supervisor_middleware_pipeline(supervisor):
    # Setup
    supervisor._loader = MagicMock()
    handler = MockHandler(MagicMock())
    handler.call.return_value = {"status": "ok", "result": "success"}
    supervisor._loader.get.return_value = handler
    supervisor._loader.has.return_value = True

    # Initialize pipeline manually for test
    from xcore.kernel.runtime.middlewares.middleware import MiddlewarePipeline

    supervisor._pipeline = MiddlewarePipeline(
        middlewares=[], final_handler=supervisor._dispatch
    )

    # Call
    result = await supervisor.call("test_plugin", "test_action", {})

    # Verify
    assert result["status"] == "ok"
    handler.call.assert_called_once_with("test_action", {})


@pytest.mark.asyncio
async def test_retry_middleware(supervisor):
    # Setup
    manifest = MagicMock()
    # Configure retry: 3 attempts, 0s backoff
    manifest.runtime.retry.max_attempts = 3
    manifest.runtime.retry.backoff_seconds = 0

    handler = MockHandler(manifest)
    # Fail twice, succeed the third time
    handler.call.side_effect = [
        Exception("Fail 1"),
        Exception("Fail 2"),
        {"status": "ok", "result": "third_time_charm"},
    ]

    supervisor._loader = MagicMock()
    supervisor._loader.get.return_value = handler
    supervisor._loader.has.return_value = True

    from xcore.kernel.runtime.middlewares.middleware import MiddlewarePipeline

    supervisor._pipeline = MiddlewarePipeline(
        middlewares=[RetryMiddleware()], final_handler=supervisor._dispatch
    )

    # Call
    result = await supervisor.call("test_plugin", "test_action", {})

    # Verify
    assert result["status"] == "ok"
    assert result["result"] == "third_time_charm"
    assert handler.call.call_count == 3
