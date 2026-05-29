"""
task Scheduler  with APScheduler (asyncio).

Support : cron, interval, date (one-shot).
Backend : memory (defaut), redis, database.

Usage:
    ```python
    scheduler = SchedulerService(config)
    await scheduler.init()

    # with decorator
    @scheduler.cron("0 9 * * MON-FRI")
    async def morning_sync():
        await do_sync()

    # with direct call
    scheduler.add_job(
        my_function,
        trigger="interval",
        seconds=30,
        id="my_job",
    )
    ```

```yaml
    # form a yaml configuration :
    services:
    scheduler:
        enabled: true
        jobs:
        - id: cleanup
            func: myapp.tasks:cleanup
            trigger: cron
            hour: 3
            minute: 0
    ```

Scaling multi-workers
---------------------
Chaque worker enregistre ses jobs au démarrage (via ScheduledMixin.on_load).
Quand le backend est Redis, un lock distribué (`xcore:sched:lock:<job_id>`)
garantit qu'un seul worker exécute le job même si tous reçoivent le déclenchement.
Les autres workers voient le lock occupé et skippent silencieusement.
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from ...configurations.sections import SchedulerConfig

from ...kernel.observability import get_logger
from ..base import BaseService, ServiceStatus

logger = get_logger("xcore.services.scheduler")

# Registre module-level : job_id → callable réel (bound method ou fonction).
# APScheduler ne stocke que la référence textuelle vers _dispatch_job ;
# le vrai callable est résolu ici à l'exécution.
_JOB_REGISTRY: dict[str, Callable] = {}

# Client Redis asyncio partagé pour les locks distribués.
# Initialisé uniquement quand backend=redis.
_REDIS_LOCK_CLIENT: Any = None

# TTL du lock en secondes — suffisant pour les jobs les plus longs.
# Si un job dépasse cette durée, le lock expire et un autre worker peut prendre la main.
_LOCK_TTL = 300


async def _dispatch_job(job_id: str) -> None:
    fn = _JOB_REGISTRY.get(job_id)
    if fn is None:
        logger.warning(
            "job introuvable dans le registre",
            job_id=job_id,
            raison="plugin déchargé ?",
        )
        return

    if _REDIS_LOCK_CLIENT is not None:
        lock_key = f"xcore:sched:lock:{job_id}"
        acquired = await _REDIS_LOCK_CLIENT.set(lock_key, "1", nx=True, ex=_LOCK_TTL)
        if not acquired:
            logger.debug(
                "job ignoré — déjà en cours sur un autre worker", job_id=job_id
            )
            return
        try:
            result = fn()
            if inspect.isawaitable(result):
                await result
        finally:
            await _REDIS_LOCK_CLIENT.delete(lock_key)
    else:
        result = fn()
        if inspect.isawaitable(result):
            await result


class SchedulerService(BaseService):
    name = "scheduler"

    def __init__(self, config: "SchedulerConfig") -> None:
        super().__init__()
        self._config = config
        self._scheduler = None

    async def init(self) -> None:
        global _REDIS_LOCK_CLIENT
        self._status = ServiceStatus.INITIALIZING
        try:
            from apscheduler.jobstores.memory import MemoryJobStore
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
        except ImportError:
            logger.warning(
                "APScheduler non installé", conseil="pip install apscheduler"
            )
            self._status = ServiceStatus.DEGRADED
            return

        jobstores: dict = {"default": MemoryJobStore()}

        if self._config.backend == "redis":
            try:
                from urllib.parse import urlparse

                import redis.asyncio as aioredis
                from apscheduler.jobstores.redis import RedisJobStore

                parsed = urlparse(self._config.url)
                jobstores["default"] = RedisJobStore(
                    host=parsed.hostname or "localhost",
                    port=parsed.port or 6379,
                    db=int(parsed.path.lstrip("/") or 0),
                    password=parsed.password or None,
                    pickle_protocol=5,
                )
                _REDIS_LOCK_CLIENT = aioredis.from_url(
                    self._config.url,
                    encoding="utf-8",
                    decode_responses=True,
                )
                logger.debug("lock distribué activé", backend="redis")
            except ImportError:
                logger.warning("apscheduler[redis] non installé — repli sur mémoire")

        self._scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            job_defaults={
                "coalesce": True,  # fusionne les déclenchements manqués en un seul
                "max_instances": 1,  # pas d'exécutions parallèles du même job
                "misfire_grace_time": 60,
            },
            timezone=self._config.timezone,
        )

        for job_cfg in self._config.jobs:
            self._add_job_from_config(job_cfg)

        self._scheduler.start()
        self._status = ServiceStatus.READY
        logger.info(
            "scheduler démarré",
            timezone=self._config.timezone,
            backend=self._config.backend,
        )

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
            logger.error(
                "impossible de charger le job depuis la config",
                job=job_cfg.get("id"),
                erreur=str(e),
            )

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

        effective_id = job_id or getattr(func, "__name__", repr(func))

        # Enregistrer le callable réel localement.
        # APScheduler stocke uniquement la référence textuelle vers _dispatch_job
        # + le job_id en args — 100 % sérialisable par Redis, sans aucun bound method.
        _JOB_REGISTRY[effective_id] = func

        return self._scheduler.add_job(
            "xcore.services.scheduler.service:_dispatch_job",
            trigger=trigger,
            id=effective_id,
            replace_existing=replace_existing,
            args=[effective_id],
            **trigger_args,
        )

    def cron(self, expression: str, job_id: str | None = None) -> Callable:
        """Décorator @scheduler.cron("0 * * * *")"""

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
        """Décorator @scheduler.interval(seconds=30)"""

        def decorator(fn: Callable) -> Callable:
            self.add_job(fn, "interval", job_id=fn.__name__, **kwargs)
            return fn

        return decorator

    def remove_job(self, job_id: str) -> None:
        _JOB_REGISTRY.pop(job_id, None)
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
        global _REDIS_LOCK_CLIENT
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
        if _REDIS_LOCK_CLIENT is not None:
            await _REDIS_LOCK_CLIENT.aclose()
            _REDIS_LOCK_CLIENT = None
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
            "distributed_lock": _REDIS_LOCK_CLIENT is not None,
        }
