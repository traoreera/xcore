"""Tests for KernelHandler."""

import pytest
from unittest.mock import MagicMock, AsyncMock


def _make_handler():
    from xcore.kernel.runtime.kernel_handler import KernelHandler
    ctx = MagicMock()
    supervisor = MagicMock()
    supervisor.list_plugins.return_value = ["plugin_a", "plugin_b"]
    return KernelHandler(ctx, supervisor)


class TestKernelHandler:
    def test_is_available(self):
        h = _make_handler()
        assert h.is_available is True

    @pytest.mark.asyncio
    async def test_start_stop_noop(self):
        h = _make_handler()
        await h.start()
        await h.stop()

    def test_status(self):
        h = _make_handler()
        s = h.status()
        assert s["name"] == "xcore"
        assert s["state"] == "ready"

    @pytest.mark.asyncio
    async def test_call_plugin_list(self):
        h = _make_handler()
        result = await h.call("plugin.list", {})
        assert result["status"] == "ok"
        assert "plugins" in result
        assert "plugin_a" in result["plugins"]

    @pytest.mark.asyncio
    async def test_call_xflow_integration(self):
        h = _make_handler()
        result = await h.call("xflow.integration", {})
        assert result["status"] == "ok"
        assert "plugin" in result

    @pytest.mark.asyncio
    async def test_call_unknown_action(self):
        h = _make_handler()
        result = await h.call("unknown.action", {})
        assert result["status"] == "error"
        assert result["code"] == "unknown_action"
        assert "available" in result

    @pytest.mark.asyncio
    async def test_call_action_raises(self):
        from xcore.kernel.runtime.kernel_handler import KernelHandler
        ctx = MagicMock()
        supervisor = MagicMock()
        supervisor.list_plugins.side_effect = RuntimeError("boom")
        h = KernelHandler(ctx, supervisor)
        result = await h.call("plugin.list", {})
        assert result["status"] == "error"
        assert result["code"] == "kernel_error"

    def test_state_is_ready(self):
        from xcore.kernel.runtime.state_machine import PluginState
        h = _make_handler()
        assert h.state == PluginState.READY
