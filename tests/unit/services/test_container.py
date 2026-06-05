"""Tests for ServiceContainer."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from xcore.services.container import ServiceContainer
from xcore.services.base import BaseService, BaseServiceProvider


def _make_config(**kwargs):
    cfg = MagicMock()
    cfg.databases = {}
    cfg.cache = None
    cfg.scheduler = None
    cfg.xworker = None
    cfg.extensions = {}
    for k, v in kwargs.items():
        setattr(cfg, k, v)
    return cfg


class TestServiceContainer:
    def test_init_empty(self):
        container = ServiceContainer(_make_config())
        assert container._raw == {}
        assert container._services == {}

    def test_register_service(self):
        container = ServiceContainer(_make_config())
        svc = MagicMock(spec=BaseService)
        container.register_service("cache", svc)
        assert container.get("cache") is svc

    def test_register_non_base_service(self):
        container = ServiceContainer(_make_config())
        container.register_service("custom", "raw_value")
        assert container.get("custom") == "raw_value"
        assert "custom" not in container._services

    def test_get_missing_raises(self):
        container = ServiceContainer(_make_config())
        with pytest.raises(KeyError, match="Service"):
            container.get("missing")

    def test_get_or_none_returns_none(self):
        container = ServiceContainer(_make_config())
        assert container.get_or_none("missing") is None

    def test_get_or_none_returns_value(self):
        container = ServiceContainer(_make_config())
        container.register_service("db", "mydb")
        assert container.get_or_none("db") == "mydb"

    def test_has_true(self):
        container = ServiceContainer(_make_config())
        container.register_service("db", "mydb")
        assert container.has("db") is True

    def test_has_false(self):
        container = ServiceContainer(_make_config())
        assert container.has("db") is False

    def test_as_dict(self):
        container = ServiceContainer(_make_config())
        container.register_service("db", "mydb")
        d = container.as_dict()
        assert "db" in d
        assert d is container._raw

    def test_get_as_correct_type(self):
        container = ServiceContainer(_make_config())
        container.register_service("db", "mydb")
        result = container.get_as("db", str)
        assert result == "mydb"

    def test_get_as_wrong_type_raises(self):
        container = ServiceContainer(_make_config())
        container.register_service("db", "mydb")
        with pytest.raises(TypeError, match="str"):
            container.get_as("db", int)

    def test_add_provider(self):
        container = ServiceContainer(_make_config())
        provider = MagicMock(spec=BaseServiceProvider)
        container.add_provider(provider)
        assert provider in container._providers

    def test_register_provider(self):
        container = ServiceContainer(_make_config())
        provider = MagicMock()
        container.register_provider("myext", provider)
        assert "myext" in container._lazy_providers

    def test_get_via_lazy_provider(self):
        container = ServiceContainer(_make_config())
        provider = MagicMock()
        provider.provide.return_value = "lazy_svc"
        container.register_provider("myext", provider)
        result = container.get("myext")
        assert result == "lazy_svc"

    def test_get_lazy_provider_returns_none_raises(self):
        container = ServiceContainer(_make_config())
        provider = MagicMock()
        provider.provide.return_value = None
        container.register_provider("myext", provider)
        with pytest.raises(KeyError):
            container.get("myext")

    @pytest.mark.asyncio
    async def test_init_with_providers(self):
        container = ServiceContainer(_make_config())
        provider = MagicMock(spec=BaseServiceProvider)
        provider.init = AsyncMock()
        await container.init(providers=[provider])
        provider.init.assert_called_once_with(container)

    @pytest.mark.asyncio
    async def test_init_empty_providers(self):
        container = ServiceContainer(_make_config())
        await container.init(providers=[])

    @pytest.mark.asyncio
    async def test_shutdown_stops_services(self):
        container = ServiceContainer(_make_config())
        svc = MagicMock(spec=BaseService)
        svc.shutdown = AsyncMock()
        container.register_service("cache", svc)
        await container.shutdown()
        svc.shutdown.assert_called_once()
        assert container._raw == {}
        assert container._services == {}

    @pytest.mark.asyncio
    async def test_shutdown_handles_exception(self):
        container = ServiceContainer(_make_config())
        svc = MagicMock(spec=BaseService)
        svc.shutdown = AsyncMock(side_effect=RuntimeError("boom"))
        container.register_service("cache", svc)
        await container.shutdown()  # should not raise

    def test_load_default_providers(self):
        container = ServiceContainer(_make_config())
        container.load_default_providers()
        assert len(container._providers) == 5

    @pytest.mark.asyncio
    async def test_health_empty(self):
        container = ServiceContainer(_make_config())
        result = await container.health()
        assert result["ok"] is True
        assert result["services"] == {}

    @pytest.mark.asyncio
    async def test_health_with_services(self):
        container = ServiceContainer(_make_config())
        svc = MagicMock(spec=BaseService)
        svc.health_check = AsyncMock(return_value=(True, "ok"))
        svc.status = MagicMock(return_value={"name": "db"})
        container.register_service("db", svc)
        result = await container.health()
        assert result["ok"] is True
        assert "db" in result["services"]

    @pytest.mark.asyncio
    async def test_health_service_exception(self):
        container = ServiceContainer(_make_config())
        svc = MagicMock(spec=BaseService)
        svc.health_check = AsyncMock(side_effect=RuntimeError("broken"))
        container.register_service("broken_svc", svc)
        result = await container.health()
        assert result["ok"] is False

    def test_status(self):
        container = ServiceContainer(_make_config())
        svc = MagicMock(spec=BaseService)
        svc.status = MagicMock(return_value={"name": "db", "status": "ready"})
        container.register_service("db", svc)
        s = container.status()
        assert "services" in s
        assert "db" in s["services"]

    @pytest.mark.asyncio
    async def test_shutdown_logs_success(self):
        container = ServiceContainer(_make_config())
        svc = MagicMock(spec=BaseService)
        svc.shutdown = AsyncMock()
        container.register_service("db", svc)
        await container.shutdown()
        svc.shutdown.assert_called_once()


class TestServiceProviders:
    @pytest.mark.asyncio
    async def test_database_provider_no_databases(self):
        from xcore.services.container import DatabaseServiceProvider
        container = ServiceContainer(_make_config(databases={}))
        provider = DatabaseServiceProvider()
        await provider.init(container)  # should return early, no error

    @pytest.mark.asyncio
    async def test_cache_provider_no_cache(self):
        from xcore.services.container import CacheServiceProvider
        container = ServiceContainer(_make_config(cache=None))
        provider = CacheServiceProvider()
        await provider.init(container)  # should return early, no error

    @pytest.mark.asyncio
    async def test_scheduler_provider_no_config(self):
        from xcore.services.container import SchedulerServiceProvider
        container = ServiceContainer(_make_config(scheduler=None))
        provider = SchedulerServiceProvider()
        await provider.init(container)  # should return early, no error

    @pytest.mark.asyncio
    async def test_scheduler_provider_disabled(self):
        from xcore.services.container import SchedulerServiceProvider
        cfg = _make_config()
        sched_cfg = MagicMock()
        sched_cfg.enabled = False
        cfg.scheduler = sched_cfg
        container = ServiceContainer(cfg)
        provider = SchedulerServiceProvider()
        await provider.init(container)  # should return early
        assert "scheduler" not in container._raw

    @pytest.mark.asyncio
    async def test_xworker_provider_no_config(self):
        from xcore.services.container import XWorkerServiceProvider
        container = ServiceContainer(_make_config(xworker=None))
        provider = XWorkerServiceProvider()
        await provider.init(container)  # should return early, no error

    @pytest.mark.asyncio
    async def test_xworker_provider_disabled(self):
        from xcore.services.container import XWorkerServiceProvider
        cfg = _make_config()
        worker_cfg = MagicMock()
        worker_cfg.enabled = False
        cfg.xworker = worker_cfg
        container = ServiceContainer(cfg)
        provider = XWorkerServiceProvider()
        await provider.init(container)  # should return early

    @pytest.mark.asyncio
    async def test_extension_provider_no_extensions(self):
        from xcore.services.container import ExtensionServiceProvider
        container = ServiceContainer(_make_config(extensions={}))
        provider = ExtensionServiceProvider()
        await provider.init(container)  # should return early, no error
