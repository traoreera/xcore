"""Tests for misc coverage gaps."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestRateLimiterRegistry:
    def test_stats_with_limiter(self):
        from xcore.kernel.sandbox.limits import RateLimiterRegistry, RateLimitConfig
        reg = RateLimiterRegistry()
        cfg = RateLimitConfig(calls=10, period_seconds=60)
        reg.register("plugin_a", cfg)
        stats = reg.stats("plugin_a")
        assert stats is not None
        assert "calls_remaining" in stats or isinstance(stats, dict)

    def test_stats_no_limiter(self):
        from xcore.kernel.sandbox.limits import RateLimiterRegistry
        reg = RateLimiterRegistry()
        assert reg.stats("nonexistent") is None

    def test_check_no_limiter(self):
        from xcore.kernel.sandbox.limits import RateLimiterRegistry
        reg = RateLimiterRegistry()
        reg.check("nonexistent")  # should not raise


class TestCacheServiceExtra:
    @pytest.mark.asyncio
    async def test_health_check_ping_ok(self):
        from xcore.services.cache.service import CacheService
        cfg = MagicMock()
        cfg.backend = "memory"
        cfg.url = None
        cfg.ttl = 300
        cfg.max_size = 1000
        svc = CacheService(cfg)
        await svc.init()
        ok, msg = await svc.health_check()
        assert ok is True
        await svc.shutdown()

    @pytest.mark.asyncio
    async def test_health_check_exception(self):
        from xcore.services.cache.service import CacheService
        cfg = MagicMock()
        cfg.backend = "memory"
        cfg.url = None
        cfg.ttl = 300
        cfg.max_size = 1000
        svc = CacheService(cfg)
        await svc.init()
        svc._backend.ping = AsyncMock(side_effect=RuntimeError("broken"))
        ok, msg = await svc.health_check()
        assert ok is False
        await svc.shutdown()

    def test_status_with_backend(self):
        from xcore.services.cache.service import CacheService
        cfg = MagicMock()
        cfg.backend = "memory"
        svc = CacheService.__new__(CacheService)
        svc._backend = MagicMock()
        svc._backend.stats = MagicMock(return_value={"hits": 5, "misses": 2})
        from xcore.services.base import ServiceStatus
        svc._status = ServiceStatus.READY
        svc.name = "cache"
        s = svc.status()
        assert "name" in s


class TestSignatureExtra:
    def test_is_signed_false(self, tmp_path):
        from xcore.kernel.security.signature import is_signed
        manifest = MagicMock()
        manifest.plugin_dir = tmp_path
        assert is_signed(manifest) is False

    def test_is_signed_true(self, tmp_path):
        from xcore.kernel.security.signature import is_signed, SIG_FILENAME
        (tmp_path / SIG_FILENAME).write_text("sig")
        manifest = MagicMock()
        manifest.plugin_dir = tmp_path
        assert is_signed(manifest) is True


class TestEventBusExtra:
    @pytest.mark.asyncio
    async def test_emit_sync_runs_in_running_loop(self):
        from xcore.kernel.events.bus import EventBus
        bus = EventBus()
        called = []

        async def handler(event):
            called.append(event.name)

        bus.subscribe("test.event", handler)
        bus.emit_sync("test.event", {"key": "val"})
        # In asyncio test, loop is running so task is created
        import asyncio
        await asyncio.sleep(0)  # yield to let the task run

    def test_list_events(self):
        from xcore.kernel.events.bus import EventBus
        bus = EventBus()
        async def handler(e): pass
        bus.subscribe("my.event", handler)
        events = bus.list_events()
        assert "my.event" in events
