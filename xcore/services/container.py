"""
container.py — Conteneur de services avec injection de dépendances, cycle de vie,
               et typage fort sur get().

Ordre d'init : database → cache → scheduler → extensions
Ordre de shutdown : inverse (extensions → scheduler → cache → database)

Typage :
    container.get("db")        → AsyncSQLAdapter  (inféré par l'IDE/mypy)
    container.get("cache")     → CacheService
    container.get("scheduler") → SchedulerService
    container.get("myname")    → Any  (connexion nommée ou extension)

    Pour un type précis sur une clé custom :
        container.get_as("mydb", AsyncSQLAdapter)
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, TypeVar, overload

# Literal dispo Python 3.8+, sinon typing_extensions
try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal  # type: ignore[assignment]

if TYPE_CHECKING:
    from ..configurations.sections import ServicesConfig
    from .cache.service import CacheService
    from .database.adapters.async_sql import AsyncSQLAdapter
    from .database.adapters.mongodb import MongoDBAdapter
    from .database.adapters.redis import RedisAdapter
    from .database.adapters.sql import SQLAdapter
    from .scheduler.service import SchedulerService

from .base import BaseService, ServiceStatus

logger = logging.getLogger("xcore.services.container")

T = TypeVar("T")


class ServiceContainer:
    """
    Conteneur centralisé de tous les services xcore.

    Les plugins accèdent aux services via :
        self.ctx.services.get("db")          → AsyncSQLAdapter  ✓ typé
        self.ctx.services.get("cache")       → CacheService      ✓ typé
        self.ctx.services.get("scheduler")   → SchedulerService  ✓ typé
        self.ctx.services.get_as("mydb", AsyncSQLAdapter)        ✓ typé custom

    Usage :
        container = ServiceContainer(config)
        await container.init()

        db    = container.get("db")       # type: AsyncSQLAdapter
        cache = container.get("cache")    # type: CacheService

        await container.shutdown()
    """

    INIT_ORDER = ["database", "cache", "scheduler", "extensions"]

    def __init__(self, config: "ServicesConfig") -> None:
        self._config = config
        self._services: dict[str, BaseService] = {}
        self._raw: dict[str, Any] = {}

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

    # ── Accès typé ────────────────────────────────────────────

    # Les overloads enseignent à mypy/Pylance le type de retour
    # selon la valeur littérale de `name`.
    # L'implémentation réelle (dernier overload) reste Any pour les clés dynamiques.

    @overload
    def get(self, name: "Literal['db']") -> "AsyncSQLAdapter": ...  # noqa: F811

    @overload
    def get(self, name: "Literal['cache']") -> "CacheService": ...  # noqa: F811

    @overload
    def get(self, name: "Literal['scheduler']") -> "SchedulerService": ...  # noqa: F811

    @overload
    def get(self, name: str) -> Any: ...  # noqa: F811

    def get(self, name: str) -> T:
        """
        Retourne un service par nom.

        Clés connues et typées :
            "db"          → AsyncSQLAdapter   (ou SQLAdapter selon config)
            "cache"       → CacheService
            "scheduler"   → SchedulerService
            "<nom_db>"    → adaptateur nommé (AsyncSQLAdapter / SQLAdapter / MongoDB…)
            "ext.<nom>"   → extension custom

        Lève KeyError avec message clair si absent.
        """
        if name in self._raw:
            type(self._raw[name])
            return self._raw[name]
        raise KeyError(
            f"Service '{name}' indisponible.\n"
            f"  Disponibles : {sorted(self._raw.keys())}\n"
            f"  Conseil : vérifiez le nom exact dans votre xcore.yaml → databases / services."
        )

    def get_as(self, name: str, type_: type[T]) -> T:
        """
        Variante fortement typée pour les connexions nommées ou extensions.

        Usage :
            analytics = container.get_as("analytics", AsyncSQLAdapter)
            mongo     = container.get_as("mongo", MongoDBAdapter)

        Lève TypeError si le type réel ne correspond pas.
        """
        svc = self.get(name)
        if not isinstance(svc, type_):
            raise TypeError(
                f"Service '{name}' est de type {type(svc).__name__!r}, "
                f"attendu {type_.__name__!r}."
            )
        return svc

    def get_or_none(self, name: str) -> Any | None:
        """Retourne None si absent, sans lever d'exception."""
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
