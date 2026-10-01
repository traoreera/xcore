"""
Détection du code synchrone qui gèle le event loop (`watch_blocking`) et son
branchement dans `LifecycleManager.call` pour les plugins Trusted.
"""

import asyncio
import logging
import time
from types import SimpleNamespace

import pytest

from xcore.configurations.sections import ServicesConfig
from xcore.kernel.context import KernelContext
from xcore.kernel.events.bus import EventBus
from xcore.kernel.events.hooks import HookManager
from xcore.kernel.observability.blocking import watch_blocking
from xcore.kernel.observability.health import HealthChecker
from xcore.kernel.runtime.lifecycle import LifecycleManager
from xcore.registry.index import PluginRegistry
from xcore.services.container import ServiceContainer


def _spin(seconds: float) -> None:
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        pass


class TestWatchBlocking:
    async def test_reports_a_synchronous_step(self):
        seen = []

        async def work():
            _spin(0.06)  # 60 ms sans await
            await asyncio.sleep(0)
            return "done"

        result = await watch_blocking(work(), 30, seen.append)

        assert result == "done"
        assert len(seen) == 1 and seen[0] >= 0.05

    async def test_cooperative_code_is_not_reported(self):
        seen = []

        async def work():
            for _ in range(20):
                await asyncio.sleep(0.001)
            return 1

        assert await watch_blocking(work(), 30, seen.append) == 1
        assert seen == []

    async def test_each_blocking_step_is_reported_separately(self):
        seen = []

        async def work():
            _spin(0.04)
            await asyncio.sleep(0)
            _spin(0.04)

        await watch_blocking(work(), 30, seen.append)

        assert len(seen) == 2

    async def test_exceptions_propagate_unchanged(self):
        async def work():
            await asyncio.sleep(0)
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            await watch_blocking(work(), 30, lambda s: None)

    async def test_blocking_step_before_an_exception_is_still_reported(self):
        seen = []

        async def work():
            _spin(0.05)
            raise ValueError("boom")

        with pytest.raises(ValueError):
            await watch_blocking(work(), 30, seen.append)

        assert len(seen) == 1

    async def test_cancellation_reaches_the_inner_coroutine(self):
        cleaned = []

        async def work():
            try:
                await asyncio.sleep(3600)
            finally:
                cleaned.append(1)

        task = asyncio.create_task(_run(watch_blocking(work(), 30, lambda s: None)))
        await asyncio.sleep(0.01)
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task
        assert cleaned == [1]

    async def test_wait_for_timeout_still_works_through_the_wrapper(self):
        async def work():
            await asyncio.sleep(10)

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(watch_blocking(work(), 30, lambda s: None), 0.05)

    async def test_closing_the_iterator_closes_the_inner_coroutine(self):
        cleaned = []

        async def work():
            try:
                await asyncio.sleep(10)
            finally:
                cleaned.append(1)

        it = watch_blocking(work(), 30, lambda s: None).__await__()
        next(it)  # avance jusqu'au premier await
        it.close()

        assert cleaned == [1]

    async def test_a_failing_report_callback_never_breaks_the_call(self):
        async def work():
            _spin(0.05)
            return "ok"

        def broken(_):
            raise RuntimeError("reporter bug")

        assert await watch_blocking(work(), 30, broken) == "ok"

    async def test_disabled_or_non_awaitable_is_returned_untouched(self):
        async def work():
            return 1

        coro = work()
        assert watch_blocking(coro, 0, lambda s: None) is coro
        assert watch_blocking(42, 30, lambda s: None) == 42
        await coro


async def _run(aw):
    return await aw


PLUGIN_SRC = """
import asyncio, time
from xcore.kernel.api.contract import TrustedBase

class Plugin(TrustedBase):
    async def handle(self, action, payload):
        if action == "spin":
            end = time.perf_counter() + 0.12
            while time.perf_counter() < end:
                pass
        elif action == "sleep":
            await asyncio.sleep(1.0)
        return {"status": "ok"}
"""


def _manager(tmp_path, timeout=10, **config):
    plugin_dir = tmp_path / "p"
    (plugin_dir / "src").mkdir(parents=True)
    (plugin_dir / "src" / "main.py").write_text(PLUGIN_SRC)
    manifest = SimpleNamespace(
        name="p",
        plugin_dir=plugin_dir,
        entry_point="src/main.py",
        resources=SimpleNamespace(timeout_seconds=timeout),
        env={},
        requires=[],
        extra={},
    )
    ctx = KernelContext(
        config=SimpleNamespace(tenancy=None, **config),
        services=ServiceContainer(ServicesConfig()),
        registry=PluginRegistry(),
        events=EventBus(),
        hooks=HookManager(),
        health=HealthChecker(),
    )
    return LifecycleManager(manifest, ctx)


def _block_warnings(caplog):
    return [r for r in caplog.records if "blocked the event loop" in r.getMessage()]


class TestPluginCallReportsLoopBlocking:
    async def test_synchronous_handler_is_reported_with_plugin_and_action(
        self, tmp_path, caplog
    ):
        lm = _manager(tmp_path, loop_block_warn_ms=50)
        await lm.load()

        with caplog.at_level(logging.WARNING):
            assert (await lm.call("spin", {}))["status"] == "ok"

        assert len(_block_warnings(caplog)) == 1
        assert lm.status()["max_loop_block_ms"] >= 100

    async def test_cooperative_handler_is_not_reported(self, tmp_path, caplog):
        lm = _manager(tmp_path, loop_block_warn_ms=50)
        await lm.load()

        with caplog.at_level(logging.WARNING):
            await lm.call("fast", {})

        assert _block_warnings(caplog) == []
        assert lm.status()["max_loop_block_ms"] == 0

    async def test_warnings_are_rate_limited_per_plugin(self, tmp_path, caplog):
        lm = _manager(tmp_path, loop_block_warn_ms=50)
        await lm.load()

        with caplog.at_level(logging.WARNING):
            await lm.call("spin", {})
            await lm.call("spin", {})

        assert len(_block_warnings(caplog)) == 1

    async def test_can_be_disabled(self, tmp_path, caplog):
        lm = _manager(tmp_path, loop_block_warn_ms=0)
        await lm.load()

        with caplog.at_level(logging.WARNING):
            await lm.call("spin", {})

        assert _block_warnings(caplog) == []

    async def test_default_threshold_applies_without_config(self, tmp_path, caplog):
        lm = _manager(tmp_path)  # pas de loop_block_warn_ms → 250 ms : 120 ms passe
        await lm.load()

        with caplog.at_level(logging.WARNING):
            await lm.call("spin", {})

        assert _block_warnings(caplog) == []

    async def test_timeout_still_enforced_for_cooperative_code(self, tmp_path):
        lm = _manager(tmp_path, timeout=0.2, loop_block_warn_ms=50)
        await lm.load()

        result = await lm.call("sleep", {})

        assert result["code"] == "timeout"
