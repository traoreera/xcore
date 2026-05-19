"""
registry.py — Décorateur @task et registre des tâches Celery.

Usage :
    from extensions.worker.registry import task, task_registry

    @task(queue="submissions", bind=True, max_retries=3)
    def process_submission(self, submission_id: str, ...):
        ...

    # Envoyer depuis FastAPI (non bloquant) :
    task_registry["marketplace.process_submission"].apply_async(kwargs={...}, queue="submissions")
"""

from __future__ import annotations

import logging
from functools import wraps
from typing import Any, Callable

from ...configurations.sections import WorkerConfig

logger = logging.getLogger("xcore.worker.registry")

_app: Any = None
task_registry: dict[str, Any] = {}
_pending_tasks: list[Callable] = []


def set_app(app: Any) -> None:
    global _app
    _app = app


def get_app() -> Any:
    if _app is None:
        raise RuntimeError(
            "WorkerService non initialisé — "
            "vérifier que l'extension 'worker' est déclarée dans integration.yaml"
        )
    return _app


def build_app(cfg: "WorkerConfig") -> Any:
    """Construit ou reconfigure l'app Celery depuis un WorkerConfig."""
    from celery import Celery  # type: ignore[import]
    from kombu import Queue  # type: ignore[import]

    queues = [Queue(q) for q in cfg.queues]

    _app_instance = Celery(
        cfg.name,
        broker=cfg.broker_url,
        backend=cfg.result_backend,
    )
    _app_instance.conf.update(
        task_serializer=cfg.task_serializer,
        result_serializer=cfg.result_serializer,
        accept_content=cfg.accept_content,
        task_soft_time_limit=cfg.task_soft_time_limit,
        task_time_limit=cfg.task_time_limit,
        result_expires=cfg.result_expires,
        broker_connection_retry_on_startup=cfg.broker_connection_retry_on_startup,
        task_default_queue=cfg.task_default_queue,
        task_queues=queues,
        include=list(cfg.modules),
    )

    # Enregistre les tâches @task() après que `include` les a importées
    from celery.signals import worker_ready

    @worker_ready.connect(weak=False)
    def _on_worker_ready(sender, **kwargs):
        register_pending_tasks(_app_instance)

    return _app_instance


def register_pending_tasks(app: Any) -> None:
    """Enregistre toutes les tâches décorées avec @task() dans l'app Celery."""
    for fn in _pending_tasks:
        meta = fn._celery_task_meta  # type: ignore[attr-defined]
        registered = app.task(
            fn,
            name=meta["name"],
            bind=meta["bind"],
            max_retries=meta["max_retries"],
            default_retry_delay=meta["default_retry_delay"],
            **meta.get("celery_kwargs", {}),
        )
        task_registry[meta["name"]] = registered
        logger.debug("Tâche enregistrée : %s → queue=%s", meta["name"], meta["queue"])


def task(
    name: str | None = None,
    queue: str = "default",
    bind: bool = False,
    max_retries: int = 3,
    default_retry_delay: int = 60,
    **celery_kwargs: Any,
) -> Callable:
    """
    Décorateur — marque une fonction comme tâche Celery.

        @task(name="marketplace.process_submission", queue="submissions", bind=True)
        def process_submission(self, submission_id, ...):
            ...
    """

    def decorator(fn: Callable) -> Callable:
        task_name = name or fn.__qualname__

        meta = {
            "name": task_name,
            "queue": queue,
            "bind": bind,
            "max_retries": max_retries,
            "default_retry_delay": default_retry_delay,
            "celery_kwargs": celery_kwargs,
        }

        fn._celery_task_meta = meta  # type: ignore[attr-defined]

        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return fn(*args, **kwargs)

        wrapper._celery_task_meta = meta  # type: ignore[attr-defined]
        _pending_tasks.append(wrapper)

        # Si l'app Celery est déjà initialisée (import via `include` au démarrage
        # du worker), on enregistre directement — sinon register_pending_tasks()
        # le fera plus tard.
        if _app is not None:
            registered = _app.task(
                wrapper,
                name=task_name,
                bind=bind,
                max_retries=max_retries,
                default_retry_delay=default_retry_delay,
                **celery_kwargs,
            )
            task_registry[task_name] = registered
            logger.debug("Tâche enregistrée immédiatement : %s", task_name)

        return wrapper

    return decorator
