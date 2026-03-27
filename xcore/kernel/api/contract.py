"""
Interface contracts for v2 plugins.
BasePlugin: Structural protocol (duck typing, no inheritance required).
TrustedBase: ABC with rich context injection.
ExecutionMode: Enum of execution modes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Protocol, TypeVar, overload, runtime_checkable

# Literal dispo Python 3.8+
try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal  # type: ignore[assignment]

# Imports TYPE_CHECKING uniquement — pas de dépendance circulaire au runtime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...services.cache.service import CacheService
    from ...services.database.adapters.async_sql import AsyncSQLAdapter
    from ...services.database.adapters.mongodb import MongoDBAdapter
    from ...services.database.adapters.redis import RedisAdapter
    from ...services.database.adapters.sql import SQLAdapter
    from ...services.scheduler.service import SchedulerService

T = TypeVar("T")


class ExecutionMode(str, Enum):
    TRUSTED = "trusted"
    SANDBOXED = "sandboxed"
    LEGACY = "legacy"


@runtime_checkable
class BasePlugin(Protocol):
    """
    Minimal contract. Duck typing — no need for inheritance.
    The plugin must expose:
        async def handle(self, action: str, payload: dict) -> dict
    """

    async def handle(self, action: str, payload: dict) -> dict: ...


@runtime_checkable
class PluginHandler(Protocol):
    """
    Common interface for all plugin managers (Trusted or Sandboxed).
    Ensures they all expose the same lifecycle and call methods.
    """

    @property
    def state(self) -> Any: ...

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def call(self, action: str, payload: dict) -> Any: ...
    def status(self) -> dict[str, Any]: ...


class TrustedBase(ABC):
    """
    Classe de base pour les plugins Trusted.

    Accès disponibles :
      - self.ctx             → PluginContext (services, hooks, env, config)
      - self.get_service()   → accès typé à un service (inférence IDE + mypy)
      - self.get_service_as()→ accès typé pour les connexions nommées
      - Hooks cycle de vie   : on_load, on_unload, on_reload
      - get_router()         → expose des routes HTTP FastAPI (optionnel)

    Exemples :

        class Plugin(TrustedBase):
            async def on_load(self):
                # Type inféré automatiquement par l'IDE
                self.db    = self.get_service("db")        # → AsyncSQLAdapter
                self.cache = self.get_service("cache")     # → CacheService

                # Connexion nommée — get_service_as pour le type exact
                self.analytics = self.get_service_as("analytics", AsyncSQLAdapter)

            async def handle(self, action, payload):
                async with self.db.session() as s:
                    ...
    """

    def __init__(self) -> None:
        self.ctx: Any = None  # injecté par LifecycleManager._inject_context()

    async def _inject_context(self, ctx: Any) -> None:
        """Appelé par le framework — ne pas surcharger sans raison valide."""
        self.ctx = ctx
        # Rétro-compatibilité v1 : expose _services directement
        self._services = ctx.services if ctx else {}

    # xcore/kernel/api/contract.py
    # Ajouter après get_service_as(), avant get_router()

    async def call_plugin(
        self,
        plugin_name: str,
        action: str,
        payload: dict | None = None,
    ) -> dict:
        if self.ctx is None:
            raise RuntimeError("call_plugin appelé avant injection du contexte.")
        if self.ctx.caller is None:
            raise RuntimeError(
                f"[{self.ctx.name}] call_plugin() non disponible "
                "(plugin sandboxed ou test sans caller)."
            )
        return await self.ctx.caller(plugin_name, action, payload or {})

    # ── get_service — overloads typés ─────────────────────────────────────────
    #
    # L'IDE et mypy voient le type de retour précis selon la valeur littérale
    # de `name`. Le fallback (str → Any) couvre les clés dynamiques.

    @overload
    def get_service(self, name: "Literal['db']") -> "AsyncSQLAdapter": ...  # noqa: F811

    @overload
    def get_service(self, name: "Literal['cache']") -> "CacheService": ...  # noqa: F811

    @overload
    def get_service(
        self, name: "Literal['scheduler']"
    ) -> "SchedulerService": ...  # noqa: F811

    @overload
    def get_service(self, name: str) -> Any: ...  # noqa: F811

    def get_service(self, name: str) -> Any:
        """
        Retourne un service du conteneur partagé.

        Clés typées (inférence automatique IDE/mypy) :
            "db"          → AsyncSQLAdapter
            "cache"       → CacheService
            "scheduler"   → SchedulerService
            "<nom>"       → Any  (connexion nommée ou extension)

        Pour un type précis sur une clé custom, utiliser get_service_as().

        Lève RuntimeError si le contexte n'est pas encore injecté.
        Lève KeyError avec message clair si le service est absent.
        """
        if self.ctx is None:
            raise RuntimeError(
                "Context not injected — plugin not yet loaded. "
                "Appeler get_service() depuis on_load() ou handle()."
            )
        svc = self.ctx.services.get(name)
        if svc is None:
            available = sorted(self.ctx.services.keys()) if self.ctx.services else []
            raise KeyError(
                f"Service '{name}' indisponible.\n"
                f"  Disponibles : {available}\n"
                f"  Conseil : vérifiez le nom dans xcore.yaml → databases / services."
            )
        return svc

    def get_service_as(self, name: str, type_: type[T]) -> T:
        """
        Variante fortement typée pour les connexions nommées ou extensions.

        Utile quand le nom n'est pas une des clés standard ("db", "cache"…)
        et que vous voulez que l'IDE connaisse le type exact.

        Exemples :
            analytics = self.get_service_as("analytics", AsyncSQLAdapter)
            mongo     = self.get_service_as("mongo",     MongoDBAdapter)
            rdb       = self.get_service_as("redis_db",  RedisAdapter)

        Lève TypeError si le type réel du service ne correspond pas à type_.
        """
        svc = self.get_service(name)
        if not isinstance(svc, type_):
            raise TypeError(
                f"Service '{name}' est de type {type(svc).__name__!r}, "
                f"attendu {type_.__name__!r}."
            )
        return svc  # type: ignore[return-value]  # isinstance garantit le type

    # ── Router HTTP custom ─────────────────────────────────────────────────────

    def get_router(self) -> "Any | None":
        """
        Surcharger pour exposer des routes HTTP FastAPI custom.
        Retourne un APIRouter ou None (défaut = pas de routes).
        Monté automatiquement sous /plugins/<plugin_name>/<prefix>.

        Exemple :
            def get_router(self):
                from fastapi import APIRouter
                router = APIRouter(prefix="/items", tags=["items"])

                @router.get("/")
                async def list_items():
                    ...

                return router
        """
        return None

    # ── Contrat abstrait ──────────────────────────────────────────────────────

    @abstractmethod
    async def handle(self, action: str, payload: dict) -> dict: ...

    # ── Hooks cycle de vie (optionnels) ───────────────────────────────────────

    async def on_load(self) -> None: ...
    async def on_unload(self) -> None: ...
    async def on_reload(self) -> None: ...


# ── Réponses standardisées ────────────────────────────────────────────────────


def ok(data: dict | None = None, **kwargs) -> dict:
    """Construit une réponse succès standardisée."""
    return {"status": "ok", **(data or {}), **kwargs}


def error(msg: str, code: str | None = None, **kwargs) -> dict:
    """Construit une réponse erreur standardisée."""
    r: dict[str, Any] = {"status": "error", "msg": msg}
    if code:
        r["code"] = code
    r |= kwargs
    return r
