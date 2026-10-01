"""
Les autres sources de code synchrone dans le event loop sont signalées elles
aussi : jobs du scheduler et hooks synchrones qui dépassent leur timeout.
"""

import asyncio
import logging
import threading
import time

from xcore.kernel.events.hooks import HookManager
from xcore.services.scheduler import service as scheduler_module


def _spin(seconds: float) -> None:
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        pass


class TestSchedulerJobs:
    async def test_sync_job_blocking_the_loop_is_reported(self, caplog):
        scheduler_module._JOB_REGISTRY["sync_job"] = lambda: _spin(0.06)
        try:
            scheduler_module._BLOCK_WARN_MS, old = 30, scheduler_module._BLOCK_WARN_MS
            with caplog.at_level(logging.WARNING):
                await scheduler_module._dispatch_job("sync_job")
        finally:
            scheduler_module._BLOCK_WARN_MS = old
            scheduler_module._JOB_REGISTRY.pop("sync_job", None)

        assert any(
            "scheduler job blocked the event loop" in r.getMessage()
            for r in caplog.records
        )

    async def test_blocking_step_inside_an_async_job_is_reported(self, caplog):
        async def job():
            await asyncio.sleep(0)
            _spin(0.06)

        scheduler_module._JOB_REGISTRY["async_job"] = job
        try:
            scheduler_module._BLOCK_WARN_MS, old = 30, scheduler_module._BLOCK_WARN_MS
            with caplog.at_level(logging.WARNING):
                await scheduler_module._dispatch_job("async_job")
        finally:
            scheduler_module._BLOCK_WARN_MS = old
            scheduler_module._JOB_REGISTRY.pop("async_job", None)

        assert any("blocked the event loop" in r.getMessage() for r in caplog.records)

    async def test_cooperative_async_job_is_silent_and_runs(self, caplog):
        ran = []

        async def job():
            await asyncio.sleep(0.001)
            ran.append(1)

        scheduler_module._JOB_REGISTRY["quiet_job"] = job
        try:
            with caplog.at_level(logging.WARNING):
                await scheduler_module._dispatch_job("quiet_job")
        finally:
            scheduler_module._JOB_REGISTRY.pop("quiet_job", None)

        assert ran == [1]
        assert not [r for r in caplog.records if "blocked" in r.getMessage()]


class TestSyncHookTimeout:
    async def test_sync_hook_timeout_warns_that_the_thread_keeps_running(self, caplog):
        release = threading.Event()

        def slow_hook(event):
            release.wait(2)

        hooks = HookManager()
        hooks.register("evt", slow_hook, timeout=0.05)

        try:
            with caplog.at_level(logging.WARNING):
                results = await hooks.emit("evt")
        finally:
            release.set()

        assert results and results[0].error is not None
        assert any(
            "worker thread keeps running" in r.getMessage() for r in caplog.records
        )

    async def test_async_hook_timeout_does_not_emit_the_thread_warning(self, caplog):
        async def slow_hook(event):
            await asyncio.sleep(1)

        hooks = HookManager()
        hooks.register("evt", slow_hook, timeout=0.05)

        with caplog.at_level(logging.WARNING):
            results = await hooks.emit("evt")

        assert results[0].error is not None
        assert not [r for r in caplog.records if "worker thread" in r.getMessage()]
