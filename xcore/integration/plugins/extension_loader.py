"""
Extension Loader — charge et gère le cycle de vie des services
déclarés dans la section `extensions` du YAML.

Chaque extension devient un service autonome :
- Instancié depuis son chemin Python (module:Classe)
- Configuré avec son bloc `config` du YAML
- Démarré via setup()
- Optionnellement lancé en tâche de fond
- Enregistré dans le ServiceRegistry sous son nom YAML

Accès :
    from integrations import get_service
    email = get_service("email")
    email.send(to="...", subject="...")
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ..config.loader import ExtensionConfig, IntegrationConfig
from .base import BaseService

logger = logging.getLogger("integrations.extensions")


# ─────────────────────────────────────────────────────────────
# Worker de tâche de fond par service
# ─────────────────────────────────────────────────────────────


class ServiceStatus(str, Enum):
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    CRASHED = "crashed"
    STOPPED = "stopped"


@dataclass
class ServiceWorkerState:
    name: str
    status: ServiceStatus = ServiceStatus.IDLE
    restarts: int = 0
    last_error: Optional[str] = None
    _stop: threading.Event = field(default_factory=threading.Event, repr=False)
    _thread: Optional[threading.Thread] = field(default=None, repr=False)
    _scheduler: Optional[Any] = field(default=None, repr=False)


class ServiceWorker:
    """Gère la tâche de fond d'un service (async, thread ou les deux)."""

    def __init__(self, ext_cfg: ExtensionConfig, instance: BaseService):
        self.ext_cfg = ext_cfg
        self.instance = instance
        self.name = ext_cfg.name
        self.state = ServiceWorkerState(name=self.name)
        self._log = logging.getLogger(f"integrations.worker.{self.name}")

    def start(self):
        self.state.status = ServiceStatus.STARTING
        mode = self.ext_cfg.background_mode

        if mode in ("async", "both"):
            self._launch_async()
        if mode in ("thread", "both"):
            self._launch_thread()
        if self.ext_cfg.background_jobs:
            self._launch_jobs()

        self.state.status = ServiceStatus.RUNNING

    # ── async ─────────────────────────────────────────────────

    def _launch_async(self):
        if not hasattr(self.instance, "run_async"):
            self._log.debug("Pas de run_async() sur ce service")
            return

        def _run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._async_runner(loop))
            finally:
                loop.close()

        t = threading.Thread(target=_run, name=f"svc-async-{self.name}", daemon=True)
        t.start()
        self.state._thread = t
        self._log.info(f"Tâche async démarrée")

    async def _async_runner(self, loop):
        max_restarts = 10 if self.ext_cfg.background_restart else 0
        while not self.state._stop.is_set():
            try:
                await self.instance.run_async()
                break  # sortie normale
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.state.last_error = str(e)
                self.state.restarts += 1
                self._log.error(f"Crash run_async(): {e}")

                if (
                    self.ext_cfg.background_restart
                    and self.state.restarts <= max_restarts
                ):
                    wait = min(2**self.state.restarts, 60)
                    self._log.warning(
                        f"Redémarrage dans {wait}s "
                        f"({self.state.restarts}/{max_restarts})"
                    )
                    await asyncio.sleep(wait)
                else:
                    self.state.status = ServiceStatus.CRASHED
                    break

    # ── thread ────────────────────────────────────────────────

    def _launch_thread(self):
        if not hasattr(self.instance, "run_sync"):
            self._log.debug("Pas de run_sync() sur ce service")
            return

        def _run():
            max_r = 10 if self.ext_cfg.background_restart else 0
            while not self.state._stop.is_set():
                try:
                    self.instance.run_sync()
                    break
                except Exception as e:
                    self.state.last_error = str(e)
                    self.state.restarts += 1
                    self._log.error(f"Crash run_sync(): {e}")
                    if self.ext_cfg.background_restart and self.state.restarts <= max_r:
                        wait = min(2**self.state.restarts, 60)
                        time.sleep(wait)
                    else:
                        self.state.status = ServiceStatus.CRASHED
                        break

        t = threading.Thread(target=_run, name=f"svc-sync-{self.name}", daemon=True)
        t.start()
        self._log.info("Tâche thread démarrée")

    # ── jobs planifiés ────────────────────────────────────────

    def _launch_jobs(self):
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
        except ImportError:
            self._log.warning(
                "APScheduler non installé — background_jobs ignorés. "
                "pip install apscheduler"
            )
            return

        scheduler = BackgroundScheduler(timezone="UTC")

        for job_cfg in self.ext_cfg.background_jobs:
            method_name = job_cfg.get("method")
            job_id = job_cfg.get("id", method_name)
            trigger = job_cfg.get("trigger", "interval")
            method = getattr(self.instance, method_name, None)

            if method is None:
                self._log.warning(f"Méthode introuvable: {method_name}")
                continue

            # Wrapper async → sync pour APScheduler
            if asyncio.iscoroutinefunction(method):
                fn = method

                def _make_sync(f):
                    def _wrapped():
                        loop = asyncio.new_event_loop()
                        try:
                            loop.run_until_complete(f())
                        finally:
                            loop.close()

                    return _wrapped

                callable_job = _make_sync(fn)
            else:
                callable_job = method

            trigger_kwargs = {
                k: v for k, v in job_cfg.items() if k not in ("id", "method", "trigger")
            }
            try:
                scheduler.add_job(
                    callable_job,
                    trigger=trigger,
                    id=f"{self.name}.{job_id}",
                    replace_existing=True,
                    **trigger_kwargs,
                )
                self._log.info(f"Job planifié: {job_id} [{trigger}] {trigger_kwargs}")
            except Exception as e:
                self._log.error(f"Erreur ajout job {job_id}: {e}")

        if scheduler.get_jobs():
            scheduler.start()
            self.state._scheduler = scheduler

    # ── arrêt ─────────────────────────────────────────────────

    def stop(self, timeout: float = 5.0):
        self.state._stop.set()
        if self.state._scheduler:
            try:
                self.state._scheduler.shutdown(wait=False)
            except Exception:
                pass
        if self.state._thread and self.state._thread.is_alive():
            self.state._thread.join(timeout=timeout)
        self.state.status = ServiceStatus.STOPPED
        self._log.info("Worker arrêté")

    def info(self) -> Dict[str, Any]:
        jobs = []
        if self.state._scheduler:
            jobs = [
                {
                    "id": j.id,
                    "next_run": str(j.next_run_time),
                    "trigger": str(j.trigger),
                }
                for j in self.state._scheduler.get_jobs()
            ]
        return {
            "service": self.name,
            "mode": self.ext_cfg.background_mode,
            "status": self.state.status.value,
            "restarts": self.state.restarts,
            "last_error": self.state.last_error,
            "scheduled_jobs": jobs,
        }


# ─────────────────────────────────────────────────────────────
# Extension Loader principal
# ─────────────────────────────────────────────────────────────


def _import_class(dotted: str) -> type:
    """Importe une classe depuis 'module.path:ClassName'."""
    if ":" not in dotted:
        raise ValueError(f"Format invalide '{dotted}' — attendu 'module:Classe'")
    module_path, class_name = dotted.rsplit(":", 1)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name, None)
    if cls is None:
        raise ImportError(f"Classe '{class_name}' introuvable dans '{module_path}'")
    return cls


class ExtensionLoader:
    """
    Charge, initialise et démarre tous les services déclarés dans le YAML.

    Accès aux services après init() :
        loader.get("email")       → instance EmailService
        loader.get("sms")         → instance SmsService
        loader.status()           → état de tous les services
    """

    def __init__(self, config: IntegrationConfig, registry: Any = None):
        self._config = config
        self._registry = registry
        self._services: Dict[str, BaseService] = {}
        self._workers: Dict[str, ServiceWorker] = {}

    # ── Initialisation ────────────────────────────────────────

    async def init_all(self):
        """Instancie et démarre tous les services activés."""
        enabled = {
            name: cfg
            for name, cfg in self._config.extensions.items()
            if cfg.enabled and cfg.service
        }

        if not enabled:
            logger.info("Aucune extension de service activée.")
            return

        logger.info(f"Chargement de {len(enabled)} extension(s)...")

        for name, ext_cfg in enabled.items():
            await self._load_one(name, ext_cfg)

        logger.info(
            f"{len(self._services)} service(s) prêt(s): {list(self._services.keys())}"
        )

    async def _load_one(self, name: str, ext_cfg: ExtensionConfig):
        """Charge, instancie et démarre un service."""
        try:
            # Import de la classe
            cls = _import_class(ext_cfg.service)

            # Instanciation avec config + registry
            instance: BaseService = cls(
                name=name,
                config=ext_cfg.config,
                registry=self,  # self expose get() → accès inter-services
                env=ext_cfg.env,
            )

            # Setup (connexion, auth, etc.)
            if asyncio.iscoroutinefunction(instance.setup):
                await instance.setup()
            else:
                instance.setup()

            instance._mark_ready()
            self._services[name] = instance

            # Enregistrement dans le ServiceRegistry global
            if self._registry:
                self._registry.register_instance(name, instance)

            logger.info(f"✅ Extension '{name}' chargée ({ext_cfg.service})")

            # Démarrage de la tâche de fond si demandé
            if ext_cfg.background:
                worker = ServiceWorker(ext_cfg, instance)
                worker.start()
                self._workers[name] = worker

        except Exception as e:
            logger.error(f"❌ Échec chargement extension '{name}': {e}")
            logger.debug("", exc_info=True)

    # ── Accès aux services ────────────────────────────────────

    def get(self, name: str) -> BaseService:
        """Retourne un service par son nom (tel que déclaré dans le YAML)."""
        svc = self._services.get(name)
        if svc is None:
            available = list(self._services.keys())
            raise KeyError(
                f"Service '{name}' non trouvé. "
                f"Disponibles: {available}. "
                f"Vérifiez qu'il est activé dans integration.yaml."
            )
        return svc

    def get_optional(self, name: str) -> Optional[BaseService]:
        """Retourne un service ou None s'il n'existe pas."""
        return self._services.get(name)

    def has(self, name: str) -> bool:
        return name in self._services

    def all(self) -> Dict[str, BaseService]:
        return dict(self._services)

    # ── État & monitoring ────────────────────────────────────

    def status(self) -> List[Dict[str, Any]]:
        """Retourne l'état de tous les services et leurs workers."""
        result = []
        for name, svc in self._services.items():
            entry: Dict[str, Any] = {
                "name": name,
                "class": svc.__class__.__name__,
                "ready": svc.is_ready,
                "worker": None,
            }
            if name in self._workers:
                entry["worker"] = self._workers[name].info()
            result.append(entry)
        return result

    # ── Arrêt ────────────────────────────────────────────────

    async def shutdown_all(self):
        """Arrête tous les workers et teardown de tous les services."""
        logger.info("Arrêt des extensions de services...")

        # Arrêt des workers de fond
        for name, worker in self._workers.items():
            try:
                worker.stop(timeout=5.0)
            except Exception as e:
                logger.warning(f"Erreur arrêt worker '{name}': {e}")

        # Teardown des services
        for name, svc in self._services.items():
            try:
                if asyncio.iscoroutinefunction(svc.teardown):
                    await svc.teardown()
                else:
                    svc.teardown()
                logger.debug(f"Service '{name}' teardown OK")
            except Exception as e:
                logger.warning(f"Erreur teardown '{name}': {e}")

        self._services.clear()
        self._workers.clear()
        logger.info("Toutes les extensions arrêtées.")
