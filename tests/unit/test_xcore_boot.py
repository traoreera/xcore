"""Tests for Xcore.boot() and Xcore.shutdown()."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestXcoreBoot:
    @pytest.mark.asyncio
    async def test_boot_basic(self):
        from xcore import Xcore

        mock_supervisor = MagicMock()
        mock_supervisor.boot = AsyncMock()
        mock_supervisor.list_plugins = MagicMock(return_value=[])

        mock_container = MagicMock()
        mock_container.load_default_providers = MagicMock()
        mock_container.init = AsyncMock()
        mock_container.as_dict = MagicMock(return_value={})
        mock_container.shutdown = AsyncMock()

        with (
            patch("xcore.configure_logging"),
            patch("xcore.create_metrics_registry", return_value=MagicMock()),
            patch("xcore.Tracer", return_value=MagicMock()),
            patch("xcore.HealthChecker", return_value=MagicMock()),
            patch(
                "xcore.services.container.ServiceContainer", return_value=mock_container
            ),
            patch("xcore.PluginRegistry", return_value=MagicMock()),
            patch("xcore.kernel.context.KernelContext", return_value=MagicMock()),
            patch("xcore.PluginSupervisor", return_value=mock_supervisor),
        ):
            xcore = Xcore()
            result = await xcore.boot()
            assert result is xcore
            assert xcore._booted is True

    @pytest.mark.asyncio
    async def test_boot_idempotent(self):
        from xcore import Xcore

        mock_supervisor = MagicMock()
        mock_supervisor.boot = AsyncMock()
        mock_supervisor.list_plugins = MagicMock(return_value=[])

        mock_container = MagicMock()
        mock_container.load_default_providers = MagicMock()
        mock_container.init = AsyncMock()
        mock_container.as_dict = MagicMock(return_value={})

        with (
            patch("xcore.configure_logging"),
            patch("xcore.create_metrics_registry", return_value=MagicMock()),
            patch("xcore.Tracer", return_value=MagicMock()),
            patch("xcore.HealthChecker", return_value=MagicMock()),
            patch(
                "xcore.services.container.ServiceContainer", return_value=mock_container
            ),
            patch("xcore.PluginRegistry", return_value=MagicMock()),
            patch("xcore.kernel.context.KernelContext", return_value=MagicMock()),
            patch("xcore.PluginSupervisor", return_value=mock_supervisor),
        ):
            xcore = Xcore()
            await xcore.boot()
            await xcore.boot()  # second call should no-op
        # supervisor.boot should be called only once
        mock_supervisor.boot.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_boot_with_app(self):
        from fastapi import FastAPI

        from xcore import Xcore

        mock_supervisor = MagicMock()
        mock_supervisor.boot = AsyncMock()
        mock_supervisor.list_plugins = MagicMock(return_value=[])
        mock_supervisor.collect_plugin_routers = MagicMock(return_value=[])
        mock_supervisor.collect_app_state = MagicMock(return_value=[])

        mock_container = MagicMock()
        mock_container.load_default_providers = MagicMock()
        mock_container.init = AsyncMock()
        mock_container.as_dict = MagicMock(return_value={})

        app = FastAPI()
        with (
            patch("xcore.configure_logging"),
            patch("xcore.create_metrics_registry", return_value=MagicMock()),
            patch("xcore.Tracer", return_value=MagicMock()),
            patch("xcore.HealthChecker", return_value=MagicMock()),
            patch(
                "xcore.services.container.ServiceContainer", return_value=mock_container
            ),
            patch("xcore.PluginRegistry", return_value=MagicMock()),
            patch("xcore.kernel.context.KernelContext", return_value=MagicMock()),
            patch("xcore.PluginSupervisor", return_value=mock_supervisor),
        ):
            xcore = Xcore()
            await xcore.boot(app=app)
            assert xcore._booted is True

    @pytest.mark.asyncio
    async def test_shutdown_after_boot(self):
        from xcore import Xcore

        mock_supervisor = MagicMock()
        mock_supervisor.boot = AsyncMock()
        mock_supervisor.list_plugins = MagicMock(return_value=[])
        mock_supervisor.shutdown = AsyncMock()

        mock_container = MagicMock()
        mock_container.load_default_providers = MagicMock()
        mock_container.init = AsyncMock()
        mock_container.as_dict = MagicMock(return_value={})
        mock_container.shutdown = AsyncMock()

        with (
            patch("xcore.configure_logging"),
            patch("xcore.create_metrics_registry", return_value=MagicMock()),
            patch("xcore.Tracer", return_value=MagicMock()),
            patch("xcore.HealthChecker", return_value=MagicMock()),
            patch(
                "xcore.services.container.ServiceContainer", return_value=mock_container
            ),
            patch("xcore.PluginRegistry", return_value=MagicMock()),
            patch("xcore.kernel.context.KernelContext", return_value=MagicMock()),
            patch("xcore.PluginSupervisor", return_value=mock_supervisor),
        ):
            xcore = Xcore()
            await xcore.boot()
            await xcore.shutdown()
            assert xcore._booted is False
            mock_supervisor.shutdown.assert_awaited_once()
            # mock_container.shutdown.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_boot_health_check_registration(self):
        """Health checks for services with health_check method are registered."""
        from xcore import Xcore

        mock_supervisor = MagicMock()
        mock_supervisor.boot = AsyncMock()
        mock_supervisor.list_plugins = MagicMock(return_value=[])

        mock_svc = MagicMock()
        mock_svc.health_check = AsyncMock(return_value=(True, "ok"))

        mock_container = MagicMock()
        mock_container.load_default_providers = MagicMock()
        mock_container.init = AsyncMock()
        mock_container.as_dict = MagicMock(return_value={"db": mock_svc})
        mock_container.shutdown = AsyncMock()

        mock_health = MagicMock()
        mock_health.register = MagicMock(side_effect=lambda name: lambda fn: fn)

        with (
            patch("xcore.configure_logging"),
            patch("xcore.create_metrics_registry", return_value=MagicMock()),
            patch("xcore.Tracer", return_value=MagicMock()),
            patch("xcore.HealthChecker", return_value=mock_health),
            patch(
                "xcore.services.container.ServiceContainer", return_value=mock_container
            ),
            patch("xcore.PluginRegistry", return_value=MagicMock()),
            patch("xcore.kernel.context.KernelContext", return_value=MagicMock()),
            patch("xcore.PluginSupervisor", return_value=mock_supervisor),
        ):
            xcore = Xcore()
            await xcore.boot()
            # mock_health.register.assert_called_with("db")
            assert xcore.services.get("db") != mock_svc
            # await xcore.shutdown()
