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

from .base import BaseService, BaseServiceProvider, ServiceStatus

logger = logging.getLogger("xcore.services.container")

T = TypeVar("T")


class DatabaseServiceProvider(BaseServiceProvider):
    async def init(self, container: ServiceContainer) -> None:
        if not container._config.databases:
            return
        from .database.manager import DatabaseManager

        mgr = DatabaseManager(container._config.databases)
        await mgr.init()
        container._services["database"] = mgr
        for name, adapter in mgr.adapters.items():
            container._raw[name] = adapter
        if mgr.adapters:
            first = next(iter(mgr.adapters.values()))
            container._raw.setdefault("db", first)
        logger.info(f"Database : {list(mgr.adapters.keys())}")


class CacheServiceProvider(BaseServiceProvider):
    async def init(self, container: ServiceContainer) -> None:
        cfg = container._config.cache
        if not cfg:
            return
        from .cache.service import CacheService

        svc = CacheService(cfg)
        await svc.init()
        container._services["cache_service"] = svc
        container._raw["cache"] = svc
        logger.info(f"Cache : backend={cfg.backend}")


class SchedulerServiceProvider(BaseServiceProvider):
    async def init(self, container: ServiceContainer) -> None:
        cfg = container._config.scheduler
        if not cfg or not cfg.enabled:
            return
        from .scheduler.service import SchedulerService

        svc = SchedulerService(cfg)
        await svc.init()
        container._services["scheduler_service"] = svc
        container._raw["scheduler"] = svc
        logger.info("Scheduler : prêt")


class ExtensionServiceProvider(BaseServiceProvider):
    async def init(self, container: ServiceContainer) -> None:
        if not container._config.extensions:
            return
        from .extensions.loader import ExtensionLoader

        loader = ExtensionLoader(container._config.extensions)
        await loader.init()
        container._services["extensions"] = loader
        for name, ext in loader.extensions.items():
            container._raw[f"ext.{name}"] = ext
        logger.info(f"Extensions : {list(loader.extensions.keys())}")


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

    def __init__(
        self, config: "ServicesConfig", providers: list[BaseServiceProvider] | None = None
    ) -> None:
        self._config = config
        self._services: dict[str, BaseService] = {}
        self._raw: dict[str, Any] = {}
        self._lazy_providers: dict[str, Any] = {}

        # If no providers are provided, we use the default set
        if providers is None:
            self._providers = self._get_default_providers()
        else:
            self._providers = providers

    @staticmethod
    def _get_default_providers() -> list[BaseServiceProvider]:
        """Returns the default list of core service providers."""
        return [
            DatabaseServiceProvider(),
            CacheServiceProvider(),
            SchedulerServiceProvider(),
            ExtensionServiceProvider(),
        ]

    def add_provider(self, provider: BaseServiceProvider) -> None:
        """Ajoute un fournisseur de services à la liste d'initialisation."""
        self._providers.append(provider)
        logger.debug(f"Provider '{provider.__class__.__name__}' ajouté")

    def register_provider(self, name: str, provider: Any) -> None:
        """Enregistre un fournisseur de services dynamique (lazy)."""
        self._lazy_providers[name] = provider
        logger.debug(f"Lazy Provider '{name}' enregistré")

    def register_service(self, name: str, service: Any) -> None:
        """Enregistre manuellement un service dans le conteneur."""
        self._raw[name] = service
        if isinstance(service, BaseService):
            self._services[name] = service
        logger.debug(f"Service '{name}' enregistré manuellement")

    async def init(self, providers: list[BaseServiceProvider] | None = None) -> None:
        """Initialise tous les services via les providers."""
        if providers is None:
            providers = self._providers

        for provider in providers:
            await provider.init(self)

        logger.info(f"✅ Services initialisés : {sorted(self._raw.keys())}")

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
            return self._raw[name]

        # Recherche dans les providers (Lazy loading)
        for provider_name, provider in self._lazy_providers.items():
            if hasattr(provider, "provide"):
                svc = provider.provide(name)
                if svc is not None:
                    # Cache le service pour les prochains appels
                    self._raw[name] = svc
                    return svc

        raise KeyError(
            f"Service '{name}' indisponible.\n"
            f"  Disponibles : {sorted(self._raw.keys())}\n"
            f"  Providers actifs : {list(self._lazy_providers.keys())}\n"
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
            "lazy_providers": list(self._lazy_providers.keys()),
        }
