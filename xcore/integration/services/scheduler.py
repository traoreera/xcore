"""
Scheduler — gestion des tâches planifiées (cron, interval, one-shot).
Backend: APScheduler (mémoire, Redis, BDD).
Configurable entièrement via integration.yaml.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any, Callable, Dict, Optional

from ..config.loader import IntegrationConfig, SchedulerConfig, SchedulerJobConfig

logger = logging.getLogger("integrations.scheduler")


def _import_func(dotted_path: str) -> Callable:
    """Importe une fonction depuis son chemin pointé. Ex: 'myapp.tasks:my_task'"""
    if ":" in dotted_path:
        module_path, func_name = dotted_path.rsplit(":", 1)
    else:
        module_path, func_name = dotted_path.rsplit(".", 1)

    module = importlib.import_module(module_path)
    func = getattr(module, func_name)
    return func


class SchedulerService:
    """
    Service de planification de tâches.
    Utilise APScheduler en backend.

    Usage depuis integration.yaml :
        scheduler:
          enabled: true
          jobs:
            - id: "my_job"
              func: "myapp.tasks:my_function"
              trigger: "cron"
              hour: 3
              grace_time: 3

    Usage programmatique :
        scheduler.add_job(
            func=my_function,
            trigger="interval",
            seconds=30,
            job_id="my_job"
        )
    """

    def __init__(self, config: IntegrationConfig):
        self._config = config.scheduler
        self._scheduler = None
        self._jobs: Dict[str, Any] = {}
        self._started = False

    def _build_scheduler(self):
        """Crée l'instance APScheduler selon le backend configuré."""
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from apscheduler.schedulers.background import BackgroundScheduler
        except ImportError:
            raise ImportError(
                "APScheduler non installé. Exécutez: pip install apscheduler"
            )

        backend = self._config.backend
        jobstores = {}
        executors = {
            "default": {"type": "threadpool", "max_workers": 10},
            "processpool": {"type": "processpool", "max_workers": 3},
        }
        job_defaults = {
            "coalesce": False,
            "max_instances": 3,
        }

        if backend == "redis":
            try:
                from apscheduler.jobstores.redis import RedisJobStore

                jobstores["default"] = RedisJobStore()
            except ImportError:
                logger.warning("RedisJobStore non disponible, fallback mémoire.")

        elif backend == "database":
            try:
                from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

                jobstores["default"] = SQLAlchemyJobStore(url="sqlite:///jobs.db")
            except ImportError:
                logger.warning("SQLAlchemyJobStore non disponible, fallback mémoire.")

        return BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone=self._config.timezone,
        )

    def init(self):
        """Initialise et démarre le scheduler avec les jobs configurés."""
        if not self._config.enabled:
            logger.info("Scheduler désactivé dans la configuration.")
            return

        self._scheduler = self._build_scheduler()

        # Chargement des jobs depuis la config YAML
        for job_cfg in self._config.jobs:
            if not job_cfg.enabled:
                logger.debug(f"Job désactivé: {job_cfg.id}")
                continue
            try:
                self._register_job_from_config(job_cfg)
            except Exception as e:
                logger.error(f"Impossible de charger le job '{job_cfg.id}': {e}")

        self._scheduler.start()
        self._started = True
        logger.info(f"Scheduler démarré ({len(self._jobs)} job(s) actifs)")

    def _register_job_from_config(self, job_cfg: SchedulerJobConfig):
        """Enregistre un job depuis sa configuration YAML."""
        func = _import_func(job_cfg.func)

        trigger_kwargs: Dict[str, Any] = {}

        if job_cfg.trigger == "cron":
            if job_cfg.hour is not None:
                trigger_kwargs["hour"] = job_cfg.hour
            if job_cfg.minute is not None:
                trigger_kwargs["minute"] = job_cfg.minute
            if job_cfg.day_of_week is not None:
                trigger_kwargs["day_of_week"] = job_cfg.day_of_week
            if job_cfg.grace_time is not None:
                trigger_kwargs["misfire_grace_time"] = job_cfg.grace_time

        elif job_cfg.trigger == "interval":
            if job_cfg.seconds is not None:
                trigger_kwargs["seconds"] = job_cfg.seconds
            if job_cfg.minutes is not None:
                trigger_kwargs["minutes"] = job_cfg.minutes
            if job_cfg.grace_time is not None:
                trigger_kwargs["misfire_grace_time"] = job_cfg.grace_time

        trigger_kwargs.update(job_cfg.extra)
        self.add_job(func, trigger=job_cfg.trigger, job_id=job_cfg.id, **trigger_kwargs)

    # ── API PUBLIQUE ───────────────────────────────────────────

    def add_job(
        self,
        func: Callable,
        trigger: str = "interval",
        job_id: Optional[str] = None,
        replace_existing: bool = True,
        **trigger_kwargs,
    ) -> Any:
        """Ajoute un job dynamiquement."""
        if not self._scheduler:
            raise RuntimeError("Scheduler non initialisé. Appelez init() d'abord.")

        job = self._scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            replace_existing=replace_existing,
            **trigger_kwargs,
        )
        self._jobs[job.id] = job
        logger.info(f"Job ajouté: {job.id} [{trigger}]")
        return job

    def remove_job(self, job_id: str):
        """Supprime un job."""
        if self._scheduler:
            self._scheduler.remove_job(job_id)
            self._jobs.pop(job_id, None)
            logger.info(f"Job supprimé: {job_id}")

    def pause_job(self, job_id: str):
        """Suspend un job."""
        if self._scheduler:
            self._scheduler.pause_job(job_id)
            logger.info(f"Job suspendu: {job_id}")

    def resume_job(self, job_id: str):
        """Reprend un job suspendu."""
        if self._scheduler:
            self._scheduler.resume_job(job_id)
            logger.info(f"Job repris: {job_id}")

    def list_jobs(self) -> list:
        """Retourne la liste des jobs actifs."""
        if not self._scheduler:
            return []
        return [
            {
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time),
                "trigger": str(job.trigger),
            }
            for job in self._scheduler.get_jobs()
        ]

    def shutdown(self, wait: bool = True):
        """Arrête le scheduler proprement."""
        if self._scheduler and self._started:
            self._scheduler.shutdown(wait=wait)
            self._started = False
            logger.info("Scheduler arrêté.")

    @property
    def is_running(self) -> bool:
        return self._started and self._scheduler is not None
