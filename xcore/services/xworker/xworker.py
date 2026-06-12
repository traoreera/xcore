"""
Extension Worker Xcore — file de tâches Celery asynchrones.
"""

from __future__ import annotations

import contextlib
from typing import Any

from xcore.services.base import BaseService, ServiceStatus

from ...configurations.sections import WorkerConfig
from ...kernel.observability import get_logger
from .registry import build_app, register_pending_tasks, set_app

logger = get_logger("xcore.worker")


def _make_app_from_env(cfg: "WorkerConfig") -> Any:
    """Crée l'app Celery depuis un WorkerConfig."""
    try:
        from .registry import build_app

        return build_app(cfg)
    except ImportError:
        return None


def _bootstrap() -> Any:
    """Initialise l'app Celery à l'import pour que `celery -A ...` fonctionne."""
    with contextlib.suppress(Exception):
        from ...configurations.loader import ConfigLoader

        cfg = ConfigLoader.load(None)
        wcfg = cfg.services.xworker
        if wcfg and wcfg.enabled:
            app = build_app(wcfg)
            set_app(
                app
            )  # rend _app disponible pour le décorateur @task lors de l'include
            return app
    return None


_celery_worker = _bootstrap()


class WorkerService(BaseService):
    """
    Service Worker xcore — reconfigure Celery depuis integration.yaml
    et vérifie la connexion au broker au démarrage.
    """

    name = "worker"

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__()
        self._cfg = WorkerConfig.from_dict(config)
        global _celery_worker

        _celery_worker = _make_app_from_env(cfg=self._cfg)

        if _celery_worker is not None:
            set_app(_celery_worker)
            # Importe les modules de tâches AVANT register_pending_tasks
            # pour que les @task() soient dans _pending_tasks
            import importlib

            for module in self._cfg.modules:
                try:
                    importlib.import_module(module)
                    logger.debug("task module loaded", module=module)
                except ImportError:
                    logger.exception("task module not found", module=module)
            register_pending_tasks(_celery_worker)

    async def init(self) -> None:
        global _celery_worker

        self._status = ServiceStatus.INITIALIZING

        if _celery_worker is None:
            logger.error("celery not installed", hint="uv add 'celery[redis]'")
            self._status = ServiceStatus.FAILED
            return

        # Reconfigure depuis integration.yaml (écrase les vars d'env)
        _celery_worker = build_app(self._cfg)
        set_app(_celery_worker)
        register_pending_tasks(_celery_worker)

        try:
            conn = _celery_worker.connection_for_read()
            conn.ensure_connection(max_retries=3)
            conn.release()
            logger.info(
                "worker service ready",
                broker=self._cfg.broker_url,
                queues=self._cfg.queues,
                concurrency=self._cfg.concurrency,
            )
            self._status = ServiceStatus.READY
        except Exception as exc:
            logger.warning("broker unreachable, degraded mode", error=str(exc))
            self._status = ServiceStatus.DEGRADED

    async def shutdown(self) -> None:
        self._status = ServiceStatus.STOPPED
        logger.info("worker service stopped")

    async def health_check(self) -> tuple[bool, str]:
        if _celery_worker is None:
            return False, "_celery_worker not initialized"
        try:
            conn = _celery_worker.connection_for_read()
            conn.ensure_connection(max_retries=1)
            conn.release()
            return True, f"broker {self._cfg.broker_url} accessible"
        except Exception as exc:
            return False, f"broker inaccessible : {exc}"

    def status(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self._status.value,
            "broker_url": self._cfg.broker_url,
            "queues": self._cfg.queues,
            "concurrency": self._cfg.concurrency,
            "registered_tasks": (
                list(_celery_worker.tasks.keys()) if _celery_worker else []
            ),
        }

    def send(
        self, task_name: str, *args: Any, queue: str = "default", **kwargs: Any
    ) -> Any:
        if _celery_worker is None:
            raise RuntimeError("WorkerService not initialized")
        return _celery_worker.send_task(
            task_name, args=args, kwargs=kwargs, queue=queue
        )

    def get_result(self, task_id: str) -> Any:
        if _celery_worker is None:
            raise RuntimeError("WorkerService not initialized")
        return _celery_worker.AsyncResult(task_id)
