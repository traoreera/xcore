"""
container.py — Conteneur de services avec injection de dépendances et cycle de vie.

Ordre d'init : database → cache → scheduler → extensions
Ordre de shutdown : inverse (extensions → scheduler → cache → database)
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..configurations.sections import ServicesConfig

from .base import BaseService, ServiceStatus

logger = logging.getLogger("xcore.services.container")


class ServiceContainer:
    """
    Conteneur centralisé de tous les services xcore.

    Les plugins accèdent aux services via :
        self.ctx.services.get("db")     → DatabaseManager
        self.ctx.services.get("cache")  → CacheService
        self.ctx.services.get("scheduler") → SchedulerService

    Usage:
        container = ServiceContainer(config)
        await container.init()

        db    = container.get("db")
        cache = container.get("cache")

        await container.shutdown()
    """

    INIT_ORDER = ["database", "cache", "scheduler", "extensions"]

    def __init__(self, config: "ServicesConfig") -> None:
        self._config = config
        self._services: dict[str, BaseService] = {}
        self._raw: dict[str, Any] = {}  # dict exposé aux plugins

    async def init(self) -> None:
        """Initialise tous les services dans l'ordre."""
        await self._init_databases()
        await self._init_cache()
        await self._init_scheduler()
        await self._init_extensions()
        logger.info(f"✅ Services initialisés : {sorted(self._raw.keys())}")

    # ── Initialisation par couche ──────────────────────────────

    async def _init_databases(self) -> None:
        if not self._config.databases:
            return
        from .database.manager import DatabaseManager

        mgr = DatabaseManager(self._config.databases)
        await mgr.init()
        self._services["database"] = mgr
        # Expose chaque connexion nommée ET un alias "db" pour la première
        for name, adapter in mgr.adapters.items():
            self._raw[name] = adapter
        if mgr.adapters:
            first = next(iter(mgr.adapters.values()))
            self._raw.setdefault("db", first)
        logger.info(f"Database : {list(mgr.adapters.keys())}")

    async def _init_cache(self) -> None:
        cfg = self._config.cache
        from .cache.service import CacheService

        svc = CacheService(cfg)
        await svc.init()
        self._services["cache_service"] = svc
        self._raw["cache"] = svc
        logger.info(f"Cache : backend={cfg.backend}")

    async def _init_scheduler(self) -> None:
        cfg = self._config.scheduler
        if not cfg.enabled:
            return
        from .scheduler.service import SchedulerService

        svc = SchedulerService(cfg)
        await svc.init()
        self._services["scheduler_service"] = svc
        self._raw["scheduler"] = svc
        logger.info("Scheduler : prêt")

    async def _init_extensions(self) -> None:
        if not self._config.extensions:
            return
        from .extensions.loader import ExtensionLoader

        loader = ExtensionLoader(self._config.extensions)
        await loader.init()
        self._services["extensions"] = loader
        for name, ext in loader.extensions.items():
            self._raw[f"ext.{name}"] = ext
        logger.info(f"Extensions : {list(loader.extensions.keys())}")

    # ── Accès ─────────────────────────────────────────────────

    def get(self, name: str) -> Any:
        """Retourne un service par nom. KeyError si absent."""
        if name in self._raw:
            return self._raw[name]
        raise KeyError(
            f"Service '{name}' indisponible. "
            f"Disponibles : {sorted(self._raw.keys())}"
        )

    def get_or_none(self, name: str) -> Any | None:
        return self._raw.get(name)

    def has(self, name: str) -> bool:
        return name in self._raw

    def as_dict(self) -> dict[str, Any]:
        """Retourne une référence au dict interne (partagé avec les plugins)."""
        return self._raw

    # ── Cycle de vie ──────────────────────────────────────────

    async def shutdown(self) -> None:
        """Arrête les services en ordre inverse."""
        names = list(self._services.keys())
        for name in reversed(names):
            svc = self._services[name]
            try:
                await asyncio.wait_for(svc.shutdown(), timeout=10.0)
                logger.info(f"Service '{name}' arrêté")
            except asyncio.TimeoutError:
                logger.error(f"Service '{name}' : timeout shutdown")
            except Exception as e:
                logger.error(f"Service '{name}' : erreur shutdown : {e}")
        self._services.clear()
        self._raw.clear()

    # ── Health ────────────────────────────────────────────────

    async def health(self) -> dict[str, Any]:
        results = {}
        for name, svc in self._services.items():
            try:
                ok, msg = await asyncio.wait_for(svc.health_check(), timeout=3.0)
                results[name] = {"ok": ok, "msg": msg}
            except Exception as e:
                results[name] = {"ok": False, "msg": str(e)}
        overall = all(v["ok"] for v in results.values()) if results else True
        return {"ok": overall, "services": results}

    def status(self) -> dict[str, Any]:
        return {
            "services": {name: svc.status() for name, svc in self._services.items()},
            "registered_keys": sorted(self._raw.keys()),
        }
