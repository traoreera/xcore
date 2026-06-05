"""Coverage gap tests for auth, metrics, tenancy, cache."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestAuthBackend:
    def test_has_auth_backend_false(self):
        from xcore.kernel.api import auth
        from xcore.kernel.api.auth import has_auth_backend, unregister_auth_backend
        unregister_auth_backend()
        assert has_auth_backend() is False

    def test_has_auth_backend_true(self):
        from xcore.kernel.api.auth import (
            register_auth_backend, unregister_auth_backend, has_auth_backend
        )
        backend = AsyncMock()
        backend.decode_token = AsyncMock()
        backend.extract_token = AsyncMock()
        backend.has_permission = AsyncMock()
        register_auth_backend(backend)
        assert has_auth_backend() is True
        unregister_auth_backend()

    def test_register_invalid_backend_raises(self):
        from xcore.kernel.api.auth import register_auth_backend
        with pytest.raises(TypeError):
            register_auth_backend("not_a_backend")


class TestPrometheusMetricsHistogram:
    def test_histogram_reuse(self):
        try:
            from xcore.kernel.observability.metrics import PrometheusMetricsRegistry
            reg = PrometheusMetricsRegistry()
            h1 = reg.histogram("test_hist_reuse_yz1")
            h2 = reg.histogram("test_hist_reuse_yz1")
            assert h1 is h2
        except ImportError:
            pytest.skip("prometheus_client not installed")


class TestCacheServiceMset:
    @pytest.mark.asyncio
    async def test_mset(self):
        from xcore.services.cache.service import CacheService
        cfg = MagicMock()
        cfg.backend = "memory"
        cfg.url = None
        cfg.ttl = 300
        cfg.max_size = 1000
        svc = CacheService(cfg)
        await svc.init()
        await svc.mset({"k1": "v1", "k2": "v2"})
        assert await svc.get("k1") == "v1"
        await svc.shutdown()


class TestSchedulerRedisPath:
    @pytest.mark.asyncio
    async def test_init_redis_backend_import_error(self):
        """Test scheduler with redis backend when redis not importable."""
        from xcore.services.scheduler.service import SchedulerService
        cfg = MagicMock()
        cfg.backend = "redis"
        cfg.url = "redis://localhost:6379/0"
        cfg.timezone = "UTC"
        cfg.jobs = []
        svc = SchedulerService(cfg)

        with patch.dict("sys.modules", {
            "redis": None,
            "redis.asyncio": None,
            "apscheduler.jobstores.redis": None,
        }):
            # Falls back to memory store gracefully
            await svc.init()
        assert svc._scheduler is not None
        await svc.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_with_redis_lock_client(self):
        """Test shutdown cleans up redis lock client."""
        import xcore.services.scheduler.service as svc_mod
        from xcore.services.scheduler.service import SchedulerService
        cfg = MagicMock()
        cfg.backend = "memory"
        cfg.url = "redis://localhost:6379/0"
        cfg.timezone = "UTC"
        cfg.jobs = []
        svc = SchedulerService(cfg)
        await svc.init()

        # Simulate a redis lock client
        mock_redis = AsyncMock()
        mock_redis.aclose = AsyncMock()
        original = svc_mod._REDIS_LOCK_CLIENT
        svc_mod._REDIS_LOCK_CLIENT = mock_redis

        try:
            await svc.shutdown()
            mock_redis.aclose.assert_called_once()
            assert svc_mod._REDIS_LOCK_CLIENT is None
        finally:
            svc_mod._REDIS_LOCK_CLIENT = original


class TestConfigurationsLoader:
    def test_load_yaml_with_extra_options(self, tmp_path):
        from xcore.configurations.loader import ConfigLoader
        cfg_file = tmp_path / "integration.yaml"
        cfg_file.write_text(
            "app:\n  name: test\n  env: production\n"
            "services:\n  scheduler:\n    enabled: false\n"
        )
        config = ConfigLoader.load(str(cfg_file))
        assert config is not None
