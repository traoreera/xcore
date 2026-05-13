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

    _app_instance = Celery(cfg.name)
    _app_instance.conf.update(**cfg.to_payload())
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

        fn._celery_task_meta = {  # type: ignore[attr-defined]
            "name": task_name,
            "queue": queue,
            "bind": bind,
            "max_retries": max_retries,
            "default_retry_delay": default_retry_delay,
            "celery_kwargs": celery_kwargs,
        }

        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return fn(*args, **kwargs)

        wrapper._celery_task_meta = fn._celery_task_meta  # type: ignore[attr-defined]
        _pending_tasks.append(wrapper)
        return wrapper

    return decorator
