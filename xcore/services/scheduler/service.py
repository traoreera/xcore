"""
service.py — Scheduler de tâches via APScheduler (asyncio).

Supporte : cron, interval, date (one-shot).
Backend : memory (défaut), redis, database.

Usage:
    scheduler = SchedulerService(config)
    await scheduler.init()

    # Via décorateur
    @scheduler.cron("0 9 * * MON-FRI")
    async def morning_sync():
        await do_sync()

    # Via appel direct
    scheduler.add_job(
        my_function,
        trigger="interval",
        seconds=30,
        id="my_job",
    )

    # Depuis la config YAML :
    # services:
    #   scheduler:
    #     enabled: true
    #     jobs:
    #       - id: cleanup
    #         func: myapp.tasks:cleanup
    #         trigger: cron
    #         hour: 3
    #         minute: 0
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from ...configurations.sections import SchedulerConfig

from ..base import BaseService, ServiceStatus

logger = logging.getLogger("xcore.services.scheduler")


class SchedulerService(BaseService):
    name = "scheduler"

    def __init__(self, config: "SchedulerConfig") -> None:
        super().__init__()
        self._config = config
        self._scheduler = None

    async def init(self) -> None:
        self._status = ServiceStatus.INITIALIZING
        try:
            from apscheduler.jobstores.memory import MemoryJobStore
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
        except ImportError:
            logger.warning("APScheduler non installé — pip install apscheduler")
            self._status = ServiceStatus.DEGRADED
            return

        jobstores = {"default": MemoryJobStore()}

        # Backend Redis si configuré
        if self._config.backend == "redis":
            try:
                from apscheduler.jobstores.redis import RedisJobStore

                jobstores["default"] = RedisJobStore()
            except ImportError:
                logger.warning("apscheduler[redis] non installé — fallback memory")

        self._scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            timezone=self._config.timezone,
        )

        # Chargement des jobs depuis la config
        for job_cfg in self._config.jobs:
            self._add_job_from_config(job_cfg)

        self._scheduler.start()
        self._status = ServiceStatus.READY
        logger.info(f"Scheduler démarré (timezone={self._config.timezone})")

    def _add_job_from_config(self, job_cfg: dict) -> None:
        try:
            import importlib

            func_path = job_cfg.get("func", "")
            module_path, func_name = func_path.rsplit(":", 1)
            module = importlib.import_module(module_path)
            func = getattr(module, func_name)

            kwargs = {
                k: v for k, v in job_cfg.items() if k not in ("func", "id", "trigger")
            }
            self.add_job(
                func,
                trigger=job_cfg.get("trigger", "cron"),
                job_id=job_cfg.get("id"),
                **kwargs,
            )
        except Exception as e:
            logger.error(f"Impossible de charger le job '{job_cfg.get('id')}' : {e}")

    # ── API publique ──────────────────────────────────────────

    def add_job(
        self,
        func: Callable,
        trigger: str = "cron",
        job_id: str | None = None,
        replace_existing: bool = True,
        **trigger_args,
    ) -> Any:
        if self._scheduler is None:
            raise RuntimeError("Scheduler non initialisé")
        return self._scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            replace_existing=replace_existing,
            **trigger_args,
        )

    def cron(self, expression: str, job_id: str | None = None) -> Callable:
        """Décorateur @scheduler.cron("0 * * * *")"""

        def decorator(fn: Callable) -> Callable:
            parts = expression.split()
            if len(parts) == 5:
                minute, hour, day, month, day_of_week = parts
                self.add_job(
                    fn,
                    "cron",
                    job_id=job_id or fn.__name__,
                    minute=minute,
                    hour=hour,
                    day=day,
                    month=month,
                    day_of_week=day_of_week,
                )
            else:
                raise ValueError(f"Expression cron invalide : {expression!r}")
            return fn

        return decorator

    def interval(self, **kwargs) -> Callable:
        """Décorateur @scheduler.interval(seconds=30)"""

        def decorator(fn: Callable) -> Callable:
            self.add_job(fn, "interval", job_id=fn.__name__, **kwargs)
            return fn

        return decorator

    def remove_job(self, job_id: str) -> None:
        if self._scheduler:
            self._scheduler.remove_job(job_id)

    def pause_job(self, job_id: str) -> None:
        if self._scheduler:
            self._scheduler.pause_job(job_id)

    def resume_job(self, job_id: str) -> None:
        if self._scheduler:
            self._scheduler.resume_job(job_id)

    def jobs(self) -> list[dict]:
        if not self._scheduler:
            return []
        return [
            {"id": j.id, "name": j.name, "next_run": str(j.next_run_time)}
            for j in self._scheduler.get_jobs()
        ]

    # ── Cycle de vie ──────────────────────────────────────────

    async def shutdown(self) -> None:
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
        self._status = ServiceStatus.STOPPED

    async def health_check(self) -> tuple[bool, str]:
        if self._scheduler is None:
            return False, "Scheduler non initialisé"
        return self._scheduler.running, "ok" if self._scheduler.running else "stopped"

    def status(self) -> dict:
        return {
            "name": self.name,
            "status": self._status.value,
            "running": self._scheduler.running if self._scheduler else False,
            "jobs": len(self.jobs()),
            "timezone": self._config.timezone,
        }
