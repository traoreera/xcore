"""Tests for xcore public API and Xcore class."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestXcoreImports:
    """Verify public API is importable."""

    def test_version(self):
        from xcore import __version__
        assert isinstance(__version__, str)

    def test_ok_error_functions(self):
        from xcore.kernel.api.contract import ok, error
        r = ok(msg="pong")
        assert r["status"] == "ok"
        e = error("not found")
        assert e["status"] == "error"

    def test_base_plugin_importable(self):
        from xcore import BasePlugin, TrustedBase
        assert BasePlugin is not None
        assert TrustedBase is not None

    def test_event_bus_importable(self):
        from xcore import EventBus
        bus = EventBus()
        assert bus is not None

    def test_hook_manager_importable(self):
        from xcore import HookManager
        hm = HookManager()
        assert hm is not None

    def test_service_container_importable(self):
        from xcore import ServiceContainer
        assert ServiceContainer is not None

    def test_get_logger(self):
        from xcore import get_logger
        logger = get_logger("test")
        assert logger is not None

    def test_metrics_registry(self):
        from xcore import MetricsRegistry
        reg = MetricsRegistry()
        assert reg is not None

    def test_health_checker(self):
        from xcore import HealthChecker
        hc = HealthChecker()
        assert hc is not None

    def test_auth_backend_functions(self):
        from xcore import get_auth_backend, register_auth_backend, unregister_auth_backend
        assert callable(get_auth_backend)
        assert callable(register_auth_backend)
        assert callable(unregister_auth_backend)

    def test_sign_verify_plugin(self):
        from xcore import sign_plugin, verify_plugin
        assert callable(sign_plugin)
        assert callable(verify_plugin)


class TestXcoreClass:
    def test_init_default(self):
        from xcore import Xcore
        xcore = Xcore()
        assert xcore._booted is False
        assert xcore.services is None
        assert xcore.plugins is None

    def test_repr_idle(self):
        from xcore import Xcore
        xcore = Xcore()
        r = repr(xcore)
        assert "idle" in r
        assert "xcore" in r.lower()

    def test_events_initialized(self):
        from xcore import Xcore, EventBus
        xcore = Xcore()
        assert isinstance(xcore.events, EventBus)

    def test_hooks_initialized(self):
        from xcore import Xcore, HookManager
        xcore = Xcore()
        assert isinstance(xcore.hooks, HookManager)

    def test_validate_secret_keys_non_production(self):
        from xcore import Xcore
        xcore = Xcore()
        xcore._config.app.env = "development"
        xcore._validate_secret_keys()  # should not raise

    def test_validate_secret_keys_production_default_raises(self):
        from xcore import Xcore
        xcore = Xcore()
        xcore._config.app.env = "production"
        xcore._config.app.secret_key = b"change-me-in-production"
        xcore._config.app.server_key = b"change-me-in-production"
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            xcore._validate_secret_keys()

    def test_validate_secret_keys_production_plugin_key_raises(self):
        from xcore import Xcore
        xcore = Xcore()
        xcore._config.app.env = "production"
        xcore._config.app.secret_key = b"my-real-secret"
        xcore._config.app.server_key = b"my-real-server"
        xcore._config.plugins.secret_key = b"change-me-in-production"
        with pytest.raises(RuntimeError, match="PLUGIN_SECRET_KEY"):
            xcore._validate_secret_keys()

    @pytest.mark.asyncio
    async def test_shutdown_not_booted_noop(self):
        from xcore import Xcore
        xcore = Xcore()
        await xcore.shutdown()  # should not raise

    def test_setup_adds_middleware(self):
        from xcore import Xcore
        from fastapi import FastAPI
        xcore = Xcore()
        app = FastAPI()
        result = xcore.setup(app)
        assert result is xcore
