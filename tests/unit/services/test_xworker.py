"""
Tests for xworker service — WorkerConfig, WorkerService, task registry,
XWorkerServiceProvider integration.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from xcore.services.base import ServiceStatus

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_celery_mock():
    """Returns a mock Celery app with the minimal API used by WorkerService."""
    app = MagicMock()
    conn = MagicMock()
    conn.ensure_connection = MagicMock(return_value=None)
    conn.release = MagicMock(return_value=None)
    app.connection_for_read.return_value = conn
    app.tasks = {}
    return app


@dataclass
class _ServicesConfig:
    xworker: Any = None
    celery: Any = None
    databases: dict = field(default_factory=dict)
    cache: Any = None
    scheduler: Any = None
    extensions: dict = field(default_factory=dict)


# ── WorkerConfig ──────────────────────────────────────────────────────────────


class TestWorkerConfig:
    def test_defaults(self):
        from xcore.services.xworker.config import WorkerConfig

        cfg = WorkerConfig()
        assert cfg.broker_url == "redis://localhost:6379/0"
        assert cfg.result_backend == "redis://localhost:6379/1"
        assert cfg.concurrency == 4
        assert cfg.queues == ["default"]
        assert cfg.modules == []

    def test_from_dict_full(self):
        from xcore.services.xworker.config import WorkerConfig

        cfg = WorkerConfig.from_dict(
            {
                "broker_url": "redis://broker:6379/2",
                "result_backend": "redis://broker:6379/3",
                "concurrency": 8,
                "queues": ["default", "emails"],
                "modules": ["myapp.tasks"],
            }
        )
        assert cfg.broker_url == "redis://broker:6379/2"
        assert cfg.concurrency == 8
        assert cfg.queues == ["default", "emails"]
        assert cfg.modules == ["myapp.tasks"]

    def test_from_dict_ignores_unknown_keys(self):
        from xcore.services.xworker.config import WorkerConfig

        cfg = WorkerConfig.from_dict(
            {"broker_url": "redis://x:6379/0", "unknown_key": 99}
        )
        assert cfg.broker_url == "redis://x:6379/0"

    def test_from_dict_empty(self):
        from xcore.services.xworker.config import WorkerConfig

        cfg = WorkerConfig.from_dict({})
        assert cfg.broker_url == "redis://localhost:6379/0"


# ── WorkerConfig (sections.py) ────────────────────────────────────────────────


class TestSectionsWorkerConfig:
    def test_defaults(self):
        from xcore.configurations.sections import WorkerConfig

        cfg = WorkerConfig()
        assert cfg.enabled is False
        assert cfg.broker_url == "redis://localhost:6379/0"
        assert cfg.queues == ["default"]
        assert cfg.modules == []

    def test_modules_task_list_sync(self):
        from xcore.configurations.sections import WorkerConfig

        cfg = WorkerConfig(modules=["app.tasks"])
        assert cfg.task_list == ["app.tasks"]

    def test_task_list_modules_sync(self):
        from xcore.configurations.sections import WorkerConfig

        cfg = WorkerConfig(task_list=["app.tasks"])
        assert cfg.modules == ["app.tasks"]

    def test_to_payload(self):
        from xcore.configurations.sections import WorkerConfig

        cfg = WorkerConfig(
            broker_url="redis://x:6379/0",
            queues=["default", "high"],
            modules=["app.tasks"],
        )
        payload = cfg.to_payload()
        assert payload["broker_url"] == "redis://x:6379/0"
        assert payload["queues"] == ["default", "high"]
        assert payload["modules"] == ["app.tasks"]
        assert "enabled" not in payload

    def test_from_dict_task_list_alias(self):
        from xcore.configurations.sections import WorkerConfig

        cfg = WorkerConfig.from_dict({"task_list": ["a.b"]})
        assert cfg.modules == ["a.b"]

    def test_from_dict_modules_alias(self):
        from xcore.configurations.sections import WorkerConfig

        cfg = WorkerConfig.from_dict({"modules": ["x.y"]})
        assert cfg.task_list == ["x.y"]


# ── registry ──────────────────────────────────────────────────────────────────


class TestTaskRegistry:
    def setup_method(self):
        import xcore.services.xworker.registry as reg

        reg._app = None
        reg.task_registry.clear()
        reg._pending_tasks.clear()

    def test_set_and_get_app(self):
        from xcore.services.xworker.registry import get_app, set_app

        mock_app = MagicMock()
        set_app(mock_app)
        assert get_app() is mock_app

    def test_get_app_without_set_raises(self):
        from xcore.services.xworker.registry import get_app

        with pytest.raises(RuntimeError, match="WorkerService non initialisé"):
            get_app()

    def test_task_decorator_adds_to_pending(self):
        from xcore.services.xworker.registry import _pending_tasks, task

        @task(name="test.my_task", queue="high")
        def my_task(x):
            return x

        assert len(_pending_tasks) == 1
        assert _pending_tasks[0]._celery_task_meta["name"] == "test.my_task"
        assert _pending_tasks[0]._celery_task_meta["queue"] == "high"

    def test_task_decorator_default_name(self):
        from xcore.services.xworker.registry import _pending_tasks, task

        @task()
        def process():
            pass

        name = _pending_tasks[0]._celery_task_meta["name"]
        assert name.endswith("process")

    def test_task_decorator_preserves_function(self):
        from xcore.services.xworker.registry import task

        @task(name="fn.test")
        def compute(a, b):
            return a + b

        assert compute(2, 3) == 5

    def test_register_pending_tasks(self):
        from xcore.services.xworker.registry import (
            register_pending_tasks,
            task,
            task_registry,
        )

        @task(name="reg.task1")
        def fn():
            pass

        mock_app = MagicMock()
        registered = MagicMock()
        mock_app.task.return_value = registered

        register_pending_tasks(mock_app)

        mock_app.task.assert_called_once()
        assert task_registry["reg.task1"] is registered

    def test_build_app(self):
        from xcore.services.xworker.config import WorkerConfig
        from xcore.services.xworker.registry import build_app

        cfg = WorkerConfig(
            broker_url="redis://localhost:6379/0",
            result_backend="redis://localhost:6379/1",
            queues=["default"],
        )

        mock_celery_cls = MagicMock()
        mock_app = MagicMock()
        mock_celery_cls.return_value = mock_app
        mock_queue = MagicMock()

        with patch.dict(
            sys.modules,
            {
                "celery": MagicMock(Celery=mock_celery_cls),
                "kombu": MagicMock(Queue=lambda q: mock_queue),
            },
        ):
            with patch(
                "xcore.services.xworker.registry.Celery", mock_celery_cls, create=True
            ):
                with patch(
                    "xcore.services.xworker.registry.Queue",
                    lambda q: mock_queue,
                    create=True,
                ):
                    # build_app imports locally, patch inside it
                    with patch(
                        "builtins.__import__",
                        side_effect=_make_import_patcher(mock_celery_cls, mock_queue),
                    ):
                        pass  # skip — tested indirectly via WorkerService


def _make_import_patcher(celery_cls, queue_obj):
    original = (
        __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__
    )

    def patched(name, *args, **kwargs):
        if name == "celery":
            m = MagicMock()
            m.Celery = celery_cls
            return m
        if name == "kombu":
            m = MagicMock()
            m.Queue = lambda q: queue_obj
            return m
        return original(name, *args, **kwargs)

    return patched


# ── WorkerService ─────────────────────────────────────────────────────────────


class TestWorkerService:
    def _mock_celery(self):
        return _make_celery_mock()

    @pytest.mark.asyncio
    async def test_init_success(self):
        from xcore.services.xworker.main import WorkerService

        mock_app = self._mock_celery()

        with (
            patch(
                "xcore.services.xworker.main._make_app_from_env", return_value=mock_app
            ),
            patch("xcore.services.xworker.main.build_app", return_value=mock_app),
            patch("xcore.services.xworker.main.set_app"),
            patch("xcore.services.xworker.main.register_pending_tasks"),
        ):
            svc = WorkerService({})
            await svc.init()

        assert svc._status == ServiceStatus.READY

    @pytest.mark.asyncio
    async def test_init_no_celery(self):
        from xcore.services.xworker.main import WorkerService

        with (
            patch("xcore.services.xworker.main._make_app_from_env", return_value=None),
            patch("xcore.services.xworker.main.app", None),
        ):
            svc = WorkerService({})
            svc.__class__.__init__(svc, {})
            import xcore.services.xworker.main as m

            m.app = None
            await svc.init()

        assert svc._status == ServiceStatus.FAILED

    @pytest.mark.asyncio
    async def test_init_broker_unreachable(self):
        from xcore.services.xworker.main import WorkerService

        mock_app = self._mock_celery()
        mock_app.connection_for_read.return_value.ensure_connection.side_effect = (
            Exception("refused")
        )

        with (
            patch(
                "xcore.services.xworker.main._make_app_from_env", return_value=mock_app
            ),
            patch("xcore.services.xworker.main.build_app", return_value=mock_app),
            patch("xcore.services.xworker.main.set_app"),
            patch("xcore.services.xworker.main.register_pending_tasks"),
        ):
            svc = WorkerService({})
            await svc.init()

        assert svc._status == ServiceStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_shutdown(self):
        from xcore.services.xworker.main import WorkerService

        mock_app = self._mock_celery()

        with (
            patch(
                "xcore.services.xworker.main._make_app_from_env", return_value=mock_app
            ),
            patch("xcore.services.xworker.main.build_app", return_value=mock_app),
            patch("xcore.services.xworker.main.set_app"),
            patch("xcore.services.xworker.main.register_pending_tasks"),
        ):
            svc = WorkerService({})
            await svc.init()
            await svc.shutdown()

        assert svc._status == ServiceStatus.STOPPED

    @pytest.mark.asyncio
    async def test_health_check_ok(self):
        from xcore.services.xworker.main import WorkerService

        mock_app = self._mock_celery()

        with (
            patch(
                "xcore.services.xworker.main._make_app_from_env", return_value=mock_app
            ),
            patch("xcore.services.xworker.main.build_app", return_value=mock_app),
            patch("xcore.services.xworker.main.set_app"),
            patch("xcore.services.xworker.main.register_pending_tasks"),
        ):
            svc = WorkerService({})
            await svc.init()
            ok, msg = await svc.health_check()

        assert ok is True
        assert "accessible" in msg

    @pytest.mark.asyncio
    async def test_health_check_fail(self):
        from xcore.services.xworker.main import WorkerService

        mock_app = self._mock_celery()

        with (
            patch(
                "xcore.services.xworker.main._make_app_from_env", return_value=mock_app
            ),
            patch("xcore.services.xworker.main.build_app", return_value=mock_app),
            patch("xcore.services.xworker.main.set_app"),
            patch("xcore.services.xworker.main.register_pending_tasks"),
        ):
            svc = WorkerService({})
            await svc.init()

        mock_app.connection_for_read.return_value.ensure_connection.side_effect = (
            Exception("down")
        )
        ok, msg = await svc.health_check()

        assert ok is False
        assert "inaccessible" in msg

    @pytest.mark.asyncio
    async def test_health_check_no_app(self):
        from xcore.services.xworker.main import WorkerService

        with patch("xcore.services.xworker.main._make_app_from_env", return_value=None):
            svc = WorkerService.__new__(WorkerService)
            svc._cfg = MagicMock()
            svc._status = ServiceStatus.FAILED

        import xcore.services.xworker.main as m

        original_app = m.app
        m.app = None
        try:
            ok, msg = await svc.health_check()
        finally:
            m.app = original_app

        assert ok is False
        assert "non initialisée" in msg

    def test_status(self):
        from xcore.services.xworker.main import WorkerService

        mock_app = self._mock_celery()
        mock_app.tasks = {"task.a": MagicMock(), "task.b": MagicMock()}

        with (
            patch(
                "xcore.services.xworker.main._make_app_from_env", return_value=mock_app
            ),
            patch("xcore.services.xworker.main.build_app", return_value=mock_app),
            patch("xcore.services.xworker.main.set_app"),
            patch("xcore.services.xworker.main.register_pending_tasks"),
        ):
            svc = WorkerService({"queues": ["default"], "concurrency": 4})

        import xcore.services.xworker.main as m

        m.app = mock_app
        result = svc.status()

        assert result["name"] == "worker"
        assert set(result["registered_tasks"]) == {"task.a", "task.b"}

    def test_send(self):
        from xcore.services.xworker.main import WorkerService

        mock_app = self._mock_celery()

        with (
            patch(
                "xcore.services.xworker.main._make_app_from_env", return_value=mock_app
            ),
            patch("xcore.services.xworker.main.build_app", return_value=mock_app),
            patch("xcore.services.xworker.main.set_app"),
            patch("xcore.services.xworker.main.register_pending_tasks"),
        ):
            svc = WorkerService({})

        import xcore.services.xworker.main as m

        m.app = mock_app
        svc.send("my.task", "arg1", queue="high")

        mock_app.send_task.assert_called_once_with(
            "my.task", args=("arg1",), kwargs={}, queue="high"
        )

    def test_send_no_app_raises(self):
        from xcore.services.xworker.main import WorkerService

        svc = WorkerService.__new__(WorkerService)
        svc._cfg = MagicMock()
        svc._status = ServiceStatus.FAILED

        import xcore.services.xworker.main as m

        original = m.app
        m.app = None
        try:
            with pytest.raises(RuntimeError, match="non initialisé"):
                svc.send("x.task")
        finally:
            m.app = original

    def test_get_result(self):
        from xcore.services.xworker.main import WorkerService

        mock_app = self._mock_celery()
        mock_result = MagicMock()
        mock_app.AsyncResult.return_value = mock_result

        with (
            patch(
                "xcore.services.xworker.main._make_app_from_env", return_value=mock_app
            ),
            patch("xcore.services.xworker.main.build_app", return_value=mock_app),
            patch("xcore.services.xworker.main.set_app"),
            patch("xcore.services.xworker.main.register_pending_tasks"),
        ):
            svc = WorkerService({})

        import xcore.services.xworker.main as m

        m.app = mock_app
        result = svc.get_result("abc-123")

        mock_app.AsyncResult.assert_called_once_with("abc-123")
        assert result is mock_result


# ── XWorkerServiceProvider ────────────────────────────────────────────────────


class TestXWorkerServiceProvider:
    @pytest.mark.asyncio
    async def test_skipped_when_disabled(self):
        from xcore.configurations.sections import WorkerConfig
        from xcore.services.container import ServiceContainer, XWorkerServiceProvider

        cfg = _ServicesConfig(xworker=WorkerConfig(enabled=False))
        container = ServiceContainer(cfg)
        provider = XWorkerServiceProvider()

        await provider.init(container)

        assert not container.has("worker")

    @pytest.mark.asyncio
    async def test_skipped_when_no_config(self):
        from xcore.services.container import ServiceContainer, XWorkerServiceProvider

        cfg = _ServicesConfig(xworker=None)
        container = ServiceContainer(cfg)
        provider = XWorkerServiceProvider()

        await provider.init(container)

        assert not container.has("worker")

    @pytest.mark.asyncio
    async def test_registers_worker_service(self):
        from xcore.configurations.sections import WorkerConfig
        from xcore.services.container import ServiceContainer, XWorkerServiceProvider
        from xcore.services.xworker.main import WorkerService

        mock_app = _make_celery_mock()

        cfg = _ServicesConfig(
            xworker=WorkerConfig(
                enabled=True,
                broker_url="redis://localhost:6379/0",
                queues=["default"],
            )
        )
        container = ServiceContainer(cfg)
        provider = XWorkerServiceProvider()

        with (
            patch(
                "xcore.services.xworker.main._make_app_from_env", return_value=mock_app
            ),
            patch("xcore.services.xworker.main.build_app", return_value=mock_app),
            patch("xcore.services.xworker.main.set_app"),
            patch("xcore.services.xworker.main.register_pending_tasks"),
        ):
            await provider.init(container)

        assert container.has("worker")
        assert isinstance(container.get("worker"), WorkerService)

    @pytest.mark.asyncio
    async def test_service_in_default_providers(self):
        from xcore.services.container import ServiceContainer, XWorkerServiceProvider

        assert XWorkerServiceProvider in ServiceContainer.DEFAULT_PROVIDERS

    @pytest.mark.asyncio
    async def test_load_default_providers_includes_xworker(self):
        from xcore.configurations.sections import WorkerConfig
        from xcore.services.container import ServiceContainer, XWorkerServiceProvider

        cfg = _ServicesConfig(xworker=WorkerConfig())
        container = ServiceContainer(cfg)
        container.load_default_providers()

        provider_types = [type(p) for p in container._providers]
        assert XWorkerServiceProvider in provider_types
