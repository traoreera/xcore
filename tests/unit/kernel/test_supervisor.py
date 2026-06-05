"""Tests for PluginSupervisor pre-boot and utility methods."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_ctx():
    ctx = MagicMock()
    ctx.config.tenancy = None
    ctx.config.directory = "/nonexistent/plugins"
    ctx.config.strict_trusted = False
    ctx.config.secret_key = b"test"
    ctx.services.as_dict.return_value = {}
    ctx.events = MagicMock()
    ctx.events.subscribe = MagicMock()
    ctx.events.emit = AsyncMock()
    ctx.hooks = MagicMock()
    ctx.registry = MagicMock()
    ctx.metrics = MagicMock()
    ctx.tracer = MagicMock()
    ctx.health = MagicMock()
    return ctx


class TestPluginSupervisorPreBoot:
    def _make(self):
        from xcore.kernel.runtime.supervisor import PluginSupervisor
        return PluginSupervisor(_make_ctx())

    @pytest.mark.asyncio
    async def test_call_not_ready(self):
        sup = self._make()
        result = await sup.call("plugin", "action", {})
        assert result["status"] == "error"
        assert result["code"] == "not_ready"

    def test_status_before_boot(self):
        sup = self._make()
        s = sup.status()
        assert s["count"] == 0
        assert s["plugins"] == []

    def test_list_plugins_before_boot(self):
        sup = self._make()
        assert sup.list_plugins() == []

    def test_collect_plugin_routers_before_boot(self):
        sup = self._make()
        assert sup.collect_plugin_routers() == []

    def test_collect_app_state_before_boot(self):
        sup = self._make()
        assert sup.collect_app_state() == []

    def test_get_active_middlewares_before_boot(self):
        sup = self._make()
        # pipeline is None before boot
        assert sup.get_active_middlewares() == []

    def test_permissions_status(self):
        sup = self._make()
        s = sup.permissions_status()
        assert s is not None

    def test_permissions_audit(self):
        sup = self._make()
        result = sup.permissions_audit()
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_shutdown_before_boot(self):
        sup = self._make()
        await sup.shutdown()  # should not raise

    def test_err_static(self):
        from xcore.kernel.runtime.supervisor import PluginSupervisor
        result = PluginSupervisor._err("something", "my_code")
        assert result["status"] == "error"
        assert result["code"] == "my_code"

    def test_register_middleware_before_boot_raises(self):
        sup = self._make()
        mw = MagicMock()
        with pytest.raises(RuntimeError, match="boot"):
            sup.register_middleware(mw)

    @pytest.mark.asyncio
    async def test_boot_empty_plugin_dir(self):
        import tempfile, os
        from xcore.kernel.runtime.supervisor import PluginSupervisor
        ctx = _make_ctx()
        with tempfile.TemporaryDirectory() as tmp:
            ctx.config.directory = tmp
            sup = PluginSupervisor(ctx)
            await sup.boot()
            assert sup.list_plugins() == ["xcore"]  # only kernel handler

    @pytest.mark.asyncio
    async def test_call_plugin_not_found_after_boot(self):
        import tempfile
        from xcore.kernel.runtime.supervisor import PluginSupervisor
        ctx = _make_ctx()
        with tempfile.TemporaryDirectory() as tmp:
            ctx.config.directory = tmp
            sup = PluginSupervisor(ctx)
            await sup.boot()
            result = await sup.call("nonexistent", "ping", {})
            assert result["status"] == "error"
            assert result["code"] == "not_found"

    @pytest.mark.asyncio
    async def test_load_unload_after_boot(self):
        import tempfile
        from xcore.kernel.runtime.supervisor import PluginSupervisor
        ctx = _make_ctx()
        with tempfile.TemporaryDirectory() as tmp:
            ctx.config.directory = tmp
            sup = PluginSupervisor(ctx)
            await sup.boot()
            # FileNotFoundError expected — just verify no crash from supervisor
            try:
                await sup.load("nonexistent")
            except FileNotFoundError:
                pass
            try:
                await sup.unload("nonexistent")
            except (FileNotFoundError, KeyError):
                pass
            try:
                await sup.reload("nonexistent")
            except (FileNotFoundError, KeyError):
                pass
