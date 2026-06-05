"""Tests for TrustedBase properties and methods in contract.py."""

import pytest
from unittest.mock import AsyncMock, MagicMock


def _make_plugin(ctx=None):
    from xcore.kernel.api.contract import TrustedBase

    class ConcretePlugin(TrustedBase):
        async def handle(self, action, payload):
            return {"status": "ok"}

    p = ConcretePlugin.__new__(ConcretePlugin)
    p.ctx = ctx
    return p


class TestTrustedBaseProperties:
    def test_metrics_with_ctx(self):
        ctx = MagicMock()
        ctx.metrics = MagicMock()
        p = _make_plugin(ctx)
        assert p.metrics is ctx.metrics

    def test_tracer_with_ctx(self):
        ctx = MagicMock()
        ctx.tracer = MagicMock()
        p = _make_plugin(ctx)
        assert p.tracer is ctx.tracer

    def test_health_with_ctx(self):
        ctx = MagicMock()
        ctx.health = MagicMock()
        p = _make_plugin(ctx)
        assert p.health is ctx.health

    def test_logger_with_ctx(self):
        ctx = MagicMock()
        ctx.name = "test_plugin"
        p = _make_plugin(ctx)
        log = p.logger
        assert log is not None
        assert "test_plugin" in log.name

    def test_logger_no_ctx(self):
        p = _make_plugin(ctx=None)
        log = p.logger
        assert log is not None

    def test_metrics_no_ctx(self):
        from unittest.mock import MagicMock as MM
        ctx2 = MM(spec=[])  # no attributes
        p = _make_plugin(ctx2)
        assert p.metrics is None

    @pytest.mark.asyncio
    async def test_call_plugin_no_ctx(self):
        p = _make_plugin(ctx=None)
        with pytest.raises(RuntimeError, match="contexte"):
            await p.call_plugin("other", "ping")

    @pytest.mark.asyncio
    async def test_call_plugin_no_caller(self):
        ctx = MagicMock()
        ctx.caller = None
        p = _make_plugin(ctx)
        with pytest.raises(RuntimeError, match="caller"):
            await p.call_plugin("other", "ping")

    @pytest.mark.asyncio
    async def test_call_plugin_with_caller(self):
        ctx = MagicMock()
        ctx.name = "my_plugin"
        ctx.tenant_id = "default"
        ctx.caller = AsyncMock(return_value={"status": "ok"})
        p = _make_plugin(ctx)
        result = await p.call_plugin("other", "ping", {"key": "val"})
        assert result["status"] == "ok"
        ctx.caller.assert_called_once()

    def test_get_service_as_wrong_type(self):
        ctx = MagicMock()
        ctx.get_service.return_value = "a_string"
        p = _make_plugin(ctx)
        with pytest.raises(TypeError, match="str"):
            p.get_service_as("db", int)

    def test_get_service_as_correct_type(self):
        ctx = MagicMock()
        ctx.get_service.return_value = "a_string"
        p = _make_plugin(ctx)
        result = p.get_service_as("db", str)
        assert result == "a_string"

    def test_add_state_default(self):
        p = _make_plugin()
        assert p.add_state() == {}

    def test_get_router_default(self):
        p = _make_plugin()
        assert p.get_router() is None

    @pytest.mark.asyncio
    async def test_lifecycle_hooks(self):
        p = _make_plugin()
        # These are no-ops but should not raise
        await p.on_init()
        await p.on_load()
        await p.on_start()
        await p.on_reload()
        await p.on_stop()
        await p.on_unload()
