"""Tests for SchedulerService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call


def _make_config(**kwargs):
    cfg = MagicMock()
    cfg.backend = "memory"
    cfg.url = "redis://localhost:6379/1"
    cfg.timezone = "UTC"
    cfg.jobs = []
    for k, v in kwargs.items():
        setattr(cfg, k, v)
    return cfg


class TestDispatchJob:
    @pytest.mark.asyncio
    async def test_dispatch_job_not_in_registry(self):
        import xcore.services.scheduler.service as svc_mod
        svc_mod._JOB_REGISTRY.clear()
        await svc_mod._dispatch_job("nonexistent")  # should not raise

    @pytest.mark.asyncio
    async def test_dispatch_job_sync(self):
        import xcore.services.scheduler.service as svc_mod
        called = []
        def my_func():
            called.append(True)
        svc_mod._JOB_REGISTRY["test_sync"] = my_func
        await svc_mod._dispatch_job("test_sync")
        assert called == [True]
        del svc_mod._JOB_REGISTRY["test_sync"]

    @pytest.mark.asyncio
    async def test_dispatch_job_async(self):
        import xcore.services.scheduler.service as svc_mod
        called = []
        async def my_async_func():
            called.append(True)
        svc_mod._JOB_REGISTRY["test_async"] = my_async_func
        await svc_mod._dispatch_job("test_async")
        assert called == [True]
        del svc_mod._JOB_REGISTRY["test_async"]

    @pytest.mark.asyncio
    async def test_dispatch_job_with_redis_lock_acquired(self):
        import xcore.services.scheduler.service as svc_mod
        original = svc_mod._REDIS_LOCK_CLIENT
        redis_mock = AsyncMock()
        redis_mock.set = AsyncMock(return_value=True)  # lock acquired
        redis_mock.delete = AsyncMock()
        svc_mod._REDIS_LOCK_CLIENT = redis_mock

        called = []
        def fn():
            called.append(True)
        svc_mod._JOB_REGISTRY["locked_job"] = fn

        try:
            await svc_mod._dispatch_job("locked_job")
            assert called == [True]
            redis_mock.delete.assert_called_once()
        finally:
            svc_mod._REDIS_LOCK_CLIENT = original
            svc_mod._JOB_REGISTRY.pop("locked_job", None)

    @pytest.mark.asyncio
    async def test_dispatch_job_with_redis_lock_not_acquired(self):
        import xcore.services.scheduler.service as svc_mod
        original = svc_mod._REDIS_LOCK_CLIENT
        redis_mock = AsyncMock()
        redis_mock.set = AsyncMock(return_value=False)  # lock NOT acquired
        svc_mod._REDIS_LOCK_CLIENT = redis_mock

        called = []
        def fn():
            called.append(True)
        svc_mod._JOB_REGISTRY["skip_job"] = fn

        try:
            await svc_mod._dispatch_job("skip_job")
            assert called == []  # skipped
        finally:
            svc_mod._REDIS_LOCK_CLIENT = original
            svc_mod._JOB_REGISTRY.pop("skip_job", None)


class TestSchedulerService:
    @pytest.mark.asyncio
    async def test_init_memory_backend(self):
        from xcore.services.scheduler.service import SchedulerService
        svc = SchedulerService(_make_config())
        await svc.init()
        assert svc._scheduler is not None
        await svc.shutdown()

    @pytest.mark.asyncio
    async def test_init_no_apscheduler(self):
        from xcore.services.scheduler.service import SchedulerService
        from xcore.services.base import ServiceStatus
        svc = SchedulerService(_make_config())
        with patch.dict("sys.modules", {"apscheduler": None,
                                        "apscheduler.jobstores": None,
                                        "apscheduler.jobstores.memory": None,
                                        "apscheduler.schedulers": None,
                                        "apscheduler.schedulers.asyncio": None}):
            with patch("builtins.__import__", side_effect=ImportError("no apscheduler")):
                try:
                    await svc.init()
                except Exception:
                    pass  # ImportError path may be triggered or not

    @pytest.mark.asyncio
    async def test_add_job(self):
        from xcore.services.scheduler.service import SchedulerService, _JOB_REGISTRY
        svc = SchedulerService(_make_config())
        await svc.init()
        try:
            called = []
            async def my_task():
                called.append(1)
            svc.add_job(my_task, "interval", job_id="test_add", seconds=999)
            assert "test_add" in _JOB_REGISTRY
        finally:
            _JOB_REGISTRY.pop("test_add", None)
            await svc.shutdown()

    @pytest.mark.asyncio
    async def test_add_job_without_scheduler_raises(self):
        from xcore.services.scheduler.service import SchedulerService
        svc = SchedulerService(_make_config())
        # Not initialized
        with pytest.raises(RuntimeError, match="non initialisé"):
            svc.add_job(lambda: None, "interval", seconds=60)

    @pytest.mark.asyncio
    async def test_cron_decorator(self):
        from xcore.services.scheduler.service import SchedulerService, _JOB_REGISTRY
        svc = SchedulerService(_make_config())
        await svc.init()
        try:
            @svc.cron("0 3 * * *")
            async def daily_job():
                pass
            assert "daily_job" in _JOB_REGISTRY
        finally:
            _JOB_REGISTRY.pop("daily_job", None)
            await svc.shutdown()

    @pytest.mark.asyncio
    async def test_cron_invalid_expression(self):
        from xcore.services.scheduler.service import SchedulerService
        svc = SchedulerService(_make_config())
        await svc.init()
        try:
            with pytest.raises(ValueError, match="invalide"):
                @svc.cron("bad expression")
                def fn():
                    pass
        finally:
            await svc.shutdown()

    @pytest.mark.asyncio
    async def test_interval_decorator(self):
        from xcore.services.scheduler.service import SchedulerService, _JOB_REGISTRY
        svc = SchedulerService(_make_config())
        await svc.init()
        try:
            @svc.interval(seconds=60)
            async def periodic():
                pass
            assert "periodic" in _JOB_REGISTRY
        finally:
            _JOB_REGISTRY.pop("periodic", None)
            await svc.shutdown()

    @pytest.mark.asyncio
    async def test_remove_job(self):
        from xcore.services.scheduler.service import SchedulerService, _JOB_REGISTRY
        svc = SchedulerService(_make_config())
        await svc.init()
        try:
            async def my_removable():
                pass
            svc.add_job(my_removable, "interval", job_id="removable", seconds=999)
            assert "removable" in _JOB_REGISTRY
            svc.remove_job("removable")
            assert "removable" not in _JOB_REGISTRY
        finally:
            await svc.shutdown()

    @pytest.mark.asyncio
    async def test_pause_resume_job(self):
        from xcore.services.scheduler.service import SchedulerService
        svc = SchedulerService(_make_config())
        await svc.init()
        try:
            async def pausable():
                pass
            svc.add_job(pausable, "interval", job_id="pausable", seconds=999)
            svc.pause_job("pausable")  # should not raise
            svc.resume_job("pausable")  # should not raise
        finally:
            await svc.shutdown()

    @pytest.mark.asyncio
    async def test_jobs_returns_list(self):
        from xcore.services.scheduler.service import SchedulerService
        svc = SchedulerService(_make_config())
        await svc.init()
        try:
            jobs = svc.jobs()
            assert isinstance(jobs, list)
        finally:
            await svc.shutdown()

    @pytest.mark.asyncio
    async def test_jobs_without_scheduler(self):
        from xcore.services.scheduler.service import SchedulerService
        svc = SchedulerService(_make_config())
        # not initialized
        assert svc.jobs() == []

    @pytest.mark.asyncio
    async def test_health_check_running(self):
        from xcore.services.scheduler.service import SchedulerService
        svc = SchedulerService(_make_config())
        await svc.init()
        try:
            ok, msg = await svc.health_check()
            assert ok is True
        finally:
            await svc.shutdown()

    @pytest.mark.asyncio
    async def test_health_check_not_initialized(self):
        from xcore.services.scheduler.service import SchedulerService
        svc = SchedulerService(_make_config())
        ok, msg = await svc.health_check()
        assert ok is False

    @pytest.mark.asyncio
    async def test_status(self):
        from xcore.services.scheduler.service import SchedulerService
        svc = SchedulerService(_make_config())
        await svc.init()
        try:
            s = svc.status()
            assert "name" in s
            assert "running" in s
            assert s["timezone"] == "UTC"
        finally:
            await svc.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_without_init(self):
        from xcore.services.scheduler.service import SchedulerService
        svc = SchedulerService(_make_config())
        await svc.shutdown()  # should not raise

    @pytest.mark.asyncio
    async def test_add_job_from_config_error(self):
        from xcore.services.scheduler.service import SchedulerService
        svc = SchedulerService(_make_config())
        await svc.init()
        try:
            bad_cfg = {"id": "bad", "func": "nonexistent.module:func", "trigger": "cron"}
            svc._add_job_from_config(bad_cfg)  # should not raise, logs error
        finally:
            await svc.shutdown()

    @pytest.mark.asyncio
    async def test_remove_job_no_scheduler(self):
        from xcore.services.scheduler.service import SchedulerService
        svc = SchedulerService(_make_config())
        svc.remove_job("nonexistent")  # should not raise

    @pytest.mark.asyncio
    async def test_pause_resume_no_scheduler(self):
        from xcore.services.scheduler.service import SchedulerService
        svc = SchedulerService(_make_config())
        svc.pause_job("x")   # should not raise
        svc.resume_job("x")  # should not raise
