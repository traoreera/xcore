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
    async def test_enable_before_boot_raises(self):
        sup = self._make()
        with pytest.raises(RuntimeError):
            await sup.enable("shop")

    @pytest.mark.asyncio
    async def test_disable_before_boot_raises(self):
        sup = self._make()
        with pytest.raises(RuntimeError):
            await sup.disable("shop")

    def test_registry_table_before_boot_empty(self):
        sup = self._make()
        assert sup.registry_table() == []

    def test_ipc_audit_before_boot_empty(self):
        sup = self._make()
        assert sup.ipc_audit() == []
        assert sup.ipc_stats() == {"entries": 0, "by_plugin": {}}

    def test_events_activity_no_bus(self):
        ctx = _make_ctx()
        ctx.events = None
        ctx.hooks = None
        from xcore.kernel.runtime.supervisor import PluginSupervisor

        sup = PluginSupervisor(ctx)
        assert sup.events_activity() == {"recent": [], "stats": {}}
        assert sup.hooks_activity() == {"recent": [], "metrics": {}}

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


class TestIPCSupervision:
    """L'appel IPC 'xcore' (KernelHandler) est déjà monté au boot — pas besoin
    d'un vrai plugin sur disque pour observer l'audit trail."""

    @pytest.mark.asyncio
    async def test_call_is_audited(self):
        import tempfile
        from xcore.kernel.runtime.supervisor import PluginSupervisor

        ctx = _make_ctx()
        with tempfile.TemporaryDirectory() as tmp:
            ctx.config.directory = tmp
            sup = PluginSupervisor(ctx)
            await sup.boot()

            await sup.call(
                "xcore", "plugin.list", {}, caller="test_caller", tenant_id="acme"
            )

            audit = sup.ipc_audit()
            assert len(audit) == 1
            entry = audit[0]
            assert entry["plugin"] == "xcore"
            assert entry["action"] == "plugin.list"
            assert entry["caller"] == "test_caller"
            assert entry["tenant_id"] == "acme"
            assert entry["status"] == "ok"
            assert entry["duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_not_found_call_is_audited(self):
        import tempfile
        from xcore.kernel.runtime.supervisor import PluginSupervisor

        ctx = _make_ctx()
        with tempfile.TemporaryDirectory() as tmp:
            ctx.config.directory = tmp
            sup = PluginSupervisor(ctx)
            await sup.boot()

            await sup.call("ghost", "ping", {})

            audit = sup.ipc_audit()
            assert audit[-1]["plugin"] == "ghost"
            assert audit[-1]["status"] == "error"
            assert audit[-1]["code"] == "not_found"

    @pytest.mark.asyncio
    async def test_ipc_audit_filters_by_plugin(self):
        import tempfile
        from xcore.kernel.runtime.supervisor import PluginSupervisor

        ctx = _make_ctx()
        with tempfile.TemporaryDirectory() as tmp:
            ctx.config.directory = tmp
            sup = PluginSupervisor(ctx)
            await sup.boot()

            await sup.call("xcore", "plugin.list", {})
            await sup.call("ghost", "ping", {})

            audit = sup.ipc_audit(plugin_name="xcore")
            assert len(audit) == 1
            assert audit[0]["plugin"] == "xcore"

    @pytest.mark.asyncio
    async def test_ipc_stats_aggregates(self):
        import tempfile
        from xcore.kernel.runtime.supervisor import PluginSupervisor

        ctx = _make_ctx()
        with tempfile.TemporaryDirectory() as tmp:
            ctx.config.directory = tmp
            sup = PluginSupervisor(ctx)
            await sup.boot()

            await sup.call("xcore", "plugin.list", {})
            await sup.call("xcore", "plugin.list", {})
            await sup.call("ghost", "ping", {})

            stats = sup.ipc_stats()
            assert stats["entries"] == 3
            assert stats["by_plugin"]["xcore"]["calls"] == 2
            assert stats["by_plugin"]["xcore"]["errors"] == 0
            assert stats["by_plugin"]["ghost"]["errors"] == 1


class TestEventsAndHooksSupervision:
    @pytest.mark.asyncio
    async def test_events_activity_reflects_real_bus(self):
        import tempfile
        from xcore.kernel.events.bus import EventBus
        from xcore.kernel.events.hooks import HookManager
        from xcore.kernel.runtime.supervisor import PluginSupervisor

        ctx = _make_ctx()
        ctx.events = EventBus()
        ctx.hooks = HookManager()
        with tempfile.TemporaryDirectory() as tmp:
            ctx.config.directory = tmp
            sup = PluginSupervisor(ctx)
            await sup.boot()

            await ctx.events.emit("custom.event", {"x": 1}, source="test")
            await ctx.hooks.emit("custom.hook", {"x": 1})

            events = sup.events_activity()
            assert events["stats"]["custom.event"]["emissions"] >= 1

            hooks = sup.hooks_activity()
            assert any(e["event"] == "custom.hook" for e in hooks["recent"])

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
