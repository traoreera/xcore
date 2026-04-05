import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock
from xcore.kernel.sandbox.process_manager import SandboxProcessManager
from xcore.kernel.sandbox.ipc import IPCResponse
from xcore.kernel.context import KernelContext

@pytest.mark.asyncio
async def test_sandboxed_service_rpc_integration():
    # Setup mock channel and response
    mock_channel = AsyncMock()

    # 1. Mock get_services response
    mock_channel.call.side_effect = [
        # Call 1: get_services
        IPCResponse(success=True, data={"status": "ok", "services": ["calculator"]}),
        # Call 2: rpc_call
        IPCResponse(success=True, data={"status": "ok", "result": 42})
    ]

    # Mock context
    registry = MagicMock()
    ctx = KernelContext(
        config=MagicMock(),
        services=MagicMock(),
        registry=registry,
        events=AsyncMock()
    )

    # Instantiate manager
    manifest = MagicMock()
    manifest.name = "math_plugin"
    manifest.plugin_dir = MagicMock()
    manifest.resources.max_disk_mb = 10
    manifest.runtime.health_check.enabled = False

    mgr = SandboxProcessManager(manifest, ctx=ctx)
    mgr._channel = mock_channel
    mgr._state = MagicMock() # To simulate RUNNING state
    type(mgr).is_available = property(lambda x: True)

    # Act 1: Discover services
    proxies = await mgr.propagate_services()

    # Assert discovery
    assert "calculator" in proxies
    registry.register_service.assert_called_once()

    # Act 2: Call RPC method on proxy
    proxy = proxies["calculator"]
    result = await proxy.add(20, 22)

    # Assert RPC call
    assert result == 42
    mock_channel.call.assert_called_with(
        "rpc_call",
        {
            "service": "calculator",
            "method": "add",
            "args": [20, 22],
            "kwargs": {}
        }
    )
