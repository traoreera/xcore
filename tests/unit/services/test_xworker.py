"""
Tests unitaires pour le service xworker (Celery).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from xcore.configurations.sections import WorkerConfig
from xcore.services.base import ServiceStatus

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_config(**overrides: Any) -> WorkerConfig:
    defaults = dict(
        enabled=True,
        name="test-worker",
        broker_url="memory://",
        result_backend="cache+memory://",
        queues=["default", "high"],
        modules=[],
        concurrency=2,
    )
    defaults.update(overrides)
    return WorkerConfig(**defaults)


def _mock_celery_app(broker_ok: bool = True) -> MagicMock:
    """Crée un faux objet Celery."""
    app = MagicMock()
    conn = MagicMock()
    if not broker_ok:
        conn.ensure_connection.side_effect = ConnectionRefusedError("broker down")
    app.connection_for_read.return_value = conn
    app.tasks = {"xcore.ping": MagicMock(), "xcore.add": MagicMock()}
    return app


# ---------------------------------------------------------------------------
# WorkerConfig
# ---------------------------------------------------------------------------


class TestWorkerConfig:
    def test_defaults(self):
        cfg = WorkerConfig()
        assert cfg.enabled is False
        assert cfg.broker_url == "redis://localhost:6379/0"
        assert cfg.queues == ["default"]
        assert cfg.concurrency == 4

    def test_from_dict_ignores_unknown_keys(self):
        cfg = WorkerConfig.from_dict({"broker_url": "memory://", "unknown_key": "x"})
        assert cfg.broker_url == "memory://"

    def test_from_dict_partial(self):
        cfg = WorkerConfig.from_dict({"enabled": True, "concurrency": 8})
        assert cfg.enabled is True
        assert cfg.concurrency == 8
        # les autres gardent leurs valeurs par défaut
        assert cfg.queues == ["default"]

    def test_to_payload_keys(self):
        cfg = _make_config()
        payload = cfg.to_payload()
        assert "broker_url" in payload
        assert "result_backend" in payload
        assert "concurrency" in payload
        assert "task_queues" in payload


# ---------------------------------------------------------------------------
# registry — build_app / set_app / get_app
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_build_app_returns_celery_instance(self):
        from celery import Celery

        from xcore.services.xworker.registry import build_app

        cfg = _make_config()
        app = build_app(cfg)
        assert isinstance(app, Celery)

    def test_build_app_configures_queues(self):
        from xcore.services.xworker.registry import build_app

        cfg = _make_config(queues=["alpha", "beta"])
        app = build_app(cfg)
        queue_names = {q.name for q in app.conf.task_queues}
        assert "alpha" in queue_names
        assert "beta" in queue_names

    def test_set_and_get_app(self):
        from xcore.services.xworker import registry

        fake = MagicMock()
        original = registry._app
        try:
            registry.set_app(fake)
            assert registry.get_app() is fake
        finally:
            registry._app = original

    def test_get_app_raises_when_none(self):
        from xcore.services.xworker import registry

        original = registry._app
        try:
            registry._app = None
            with pytest.raises(RuntimeError, match="WorkerService non initialisé"):
                registry.get_app()
        finally:
            registry._app = original


# ---------------------------------------------------------------------------
# registry — décorateur @task
# ---------------------------------------------------------------------------


class TestTaskDecorator:
    def test_decorator_attaches_meta(self):
        from xcore.services.xworker.registry import _pending_tasks, task

        before = len(_pending_tasks)

        @task(name="test.my_task", queue="high", bind=True, max_retries=5)
        def my_task(self, x: int) -> int:
            return x * 2

        assert hasattr(my_task, "_celery_task_meta")
        meta = my_task._celery_task_meta
        assert meta["name"] == "test.my_task"
        assert meta["queue"] == "high"
        assert meta["bind"] is True
        assert meta["max_retries"] == 5
        assert len(_pending_tasks) == before + 1

        # nettoyage
        _pending_tasks.remove(my_task)

    def test_decorator_default_name(self):
        from xcore.services.xworker.registry import _pending_tasks, task

        @task()
        def simple_task() -> None:
            pass

        assert simple_task._celery_task_meta["name"].endswith("simple_task")
        _pending_tasks.remove(simple_task)

    def test_wrapper_preserves_return_value(self):
        from xcore.services.xworker.registry import _pending_tasks, task

        @task(name="test.add")
        def add(a: int, b: int) -> int:
            return a + b

        assert add(3, 4) == 7
        _pending_tasks.remove(add)

    def test_register_pending_tasks(self):
        from xcore.services.xworker.registry import (
            _pending_tasks,
            register_pending_tasks,
            task,
            task_registry,
        )

        @task(name="test.register_demo", queue="default")
        def register_demo() -> str:
            return "ok"

        fake_app = MagicMock()
        registered_task = MagicMock()
        fake_app.task.return_value = registered_task

        register_pending_tasks(fake_app)

        assert "test.register_demo" in task_registry
        fake_app.task.assert_any_call(
            register_demo,
            name="test.register_demo",
            bind=False,
            max_retries=3,
            default_retry_delay=60,
        )

        # nettoyage
        _pending_tasks.remove(register_demo)
        del task_registry["test.register_demo"]


# ---------------------------------------------------------------------------
# WorkerService
# ---------------------------------------------------------------------------


class TestWorkerService:
    def _build_service(self, broker_ok: bool = True) -> Any:
        from xcore.services.xworker.xworker import WorkerService

        cfg = _make_config()
        fake_app = _mock_celery_app(broker_ok=broker_ok)

        with patch(
            "xcore.services.xworker.xworker._make_app_from_env", return_value=fake_app
        ):
            svc = WorkerService(cfg.__dict__)

        return svc, fake_app

    def test_init_sets_status_to_initializing_then_ready(self):
        from xcore.services.xworker.xworker import WorkerService

        cfg = _make_config()
        fake_app = _mock_celery_app()

        with (
            patch(
                "xcore.services.xworker.xworker._make_app_from_env",
                return_value=fake_app,
            ),
            patch("xcore.services.xworker.xworker.set_app"),
            patch("xcore.services.xworker.xworker.register_pending_tasks"),
        ):
            svc = WorkerService(cfg.__dict__)

        assert svc is not None

    @pytest.mark.asyncio
    async def test_init_ready_when_broker_ok(self):
        from xcore.services.xworker.xworker import WorkerService, _celery_worker

        cfg = _make_config()
        fake_app = _mock_celery_app(broker_ok=True)

        with (
            patch(
                "xcore.services.xworker.xworker._make_app_from_env",
                return_value=fake_app,
            ),
            patch("xcore.services.xworker.xworker.set_app"),
            patch("xcore.services.xworker.xworker.register_pending_tasks"),
            patch("xcore.services.xworker.xworker.build_app", return_value=fake_app),
            patch(
                "xcore.services.xworker.xworker._celery_worker",
                fake_app,
                create=True,
            ),
        ):
            svc = WorkerService.__new__(WorkerService)
            svc._cfg = cfg
            svc._status = ServiceStatus.INITIALIZING
            await svc.init()

        assert svc._status == ServiceStatus.READY

    @pytest.mark.asyncio
    async def test_init_degraded_when_broker_down(self):
        from xcore.services.xworker.xworker import WorkerService

        cfg = _make_config()
        fake_app = _mock_celery_app(broker_ok=False)

        with (
            patch("xcore.services.xworker.xworker.build_app", return_value=fake_app),
            patch("xcore.services.xworker.xworker.set_app"),
            patch("xcore.services.xworker.xworker.register_pending_tasks"),
            patch(
                "xcore.services.xworker.xworker._celery_worker",
                fake_app,
                create=True,
            ),
        ):
            svc = WorkerService.__new__(WorkerService)
            svc._cfg = cfg
            svc._status = ServiceStatus.INITIALIZING
            await svc.init()

        assert svc._status == ServiceStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_init_failed_when_celery_missing(self):
        from xcore.services.xworker.xworker import WorkerService

        cfg = _make_config()

        with (
            patch("xcore.services.xworker.xworker.build_app", return_value=None),
            patch("xcore.services.xworker.xworker.set_app"),
            patch("xcore.services.xworker.xworker.register_pending_tasks"),
            patch("xcore.services.xworker.xworker._celery_worker", None, create=True),
        ):
            svc = WorkerService.__new__(WorkerService)
            svc._cfg = cfg
            svc._status = ServiceStatus.INITIALIZING
            await svc.init()

        assert svc._status == ServiceStatus.FAILED

    @pytest.mark.asyncio
    async def test_shutdown_sets_stopped(self):
        from xcore.services.xworker.xworker import WorkerService

        svc = WorkerService.__new__(WorkerService)
        svc._status = ServiceStatus.READY
        await svc.shutdown()
        assert svc._status == ServiceStatus.STOPPED

    @pytest.mark.asyncio
    async def test_health_check_ok(self):
        from xcore.services.xworker.xworker import WorkerService

        fake_app = _mock_celery_app(broker_ok=True)
        cfg = _make_config()

        svc = WorkerService.__new__(WorkerService)
        svc._cfg = cfg

        with patch("xcore.services.xworker.xworker._celery_worker", fake_app):
            ok, msg = await svc.health_check()

        assert ok is True
        assert "accessible" in msg

    @pytest.mark.asyncio
    async def test_health_check_fails_when_broker_down(self):
        from xcore.services.xworker.xworker import WorkerService

        fake_app = _mock_celery_app(broker_ok=False)
        cfg = _make_config()

        svc = WorkerService.__new__(WorkerService)
        svc._cfg = cfg

        with patch("xcore.services.xworker.xworker._celery_worker", fake_app):
            ok, msg = await svc.health_check()

        assert ok is False
        assert "inaccessible" in msg

    @pytest.mark.asyncio
    async def test_health_check_fails_when_no_app(self):
        from xcore.services.xworker.xworker import WorkerService

        svc = WorkerService.__new__(WorkerService)
        svc._cfg = _make_config()

        with patch("xcore.services.xworker.xworker._celery_worker", None):
            ok, msg = await svc.health_check()

        assert ok is False

    def test_status_returns_dict(self):
        from xcore.services.xworker.xworker import WorkerService

        fake_app = _mock_celery_app()
        cfg = _make_config()

        svc = WorkerService.__new__(WorkerService)
        svc._cfg = cfg
        svc._status = ServiceStatus.READY

        with patch("xcore.services.xworker.xworker._celery_worker", fake_app):
            result = svc.status()

        assert result["name"] == "worker"
        assert result["status"] == ServiceStatus.READY.value
        assert "registered_tasks" in result
        assert isinstance(result["registered_tasks"], list)

    def test_send_dispatches_task(self):
        from xcore.services.xworker.xworker import WorkerService

        fake_app = _mock_celery_app()
        svc = WorkerService.__new__(WorkerService)
        svc._cfg = _make_config()

        with patch("xcore.services.xworker.xworker._celery_worker", fake_app):
            svc.send("xcore.add", 1, 2, queue="high")

        fake_app.send_task.assert_called_once_with(
            "xcore.add", args=(1, 2), kwargs={}, queue="high"
        )

    def test_send_raises_when_not_initialized(self):
        from xcore.services.xworker.xworker import WorkerService

        svc = WorkerService.__new__(WorkerService)
        svc._cfg = _make_config()

        with (
            patch("xcore.services.xworker.xworker._celery_worker", None),
            pytest.raises(RuntimeError, match="WorkerService not initialized"),
        ):
            svc.send("xcore.ping")

    def test_get_result_returns_async_result(self):
        from xcore.services.xworker.xworker import WorkerService

        fake_app = _mock_celery_app()
        fake_result = MagicMock()
        fake_app.AsyncResult.return_value = fake_result

        svc = WorkerService.__new__(WorkerService)
        svc._cfg = _make_config()

        with patch("xcore.services.xworker.xworker._celery_worker", fake_app):
            result = svc.get_result("abc-123")

        fake_app.AsyncResult.assert_called_once_with("abc-123")
        assert result is fake_result
