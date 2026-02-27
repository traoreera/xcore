"""
contract.py — Contrats d'interface pour les plugins v2.

BasePlugin  : Protocol structurel (duck typing, pas d'héritage requis).
TrustedBase : ABC avec injection de contexte riche.
ExecutionMode : enum des modes d'exécution.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class ExecutionMode(str, Enum):
    TRUSTED = "trusted"
    SANDBOXED = "sandboxed"
    LEGACY = "legacy"


@runtime_checkable
class BasePlugin(Protocol):
    """
    Contrat minimal. Duck typing — pas besoin d'hériter.

    Le plugin doit exposer :
        async def handle(self, action: str, payload: dict) -> dict
    """

    async def handle(self, action: str, payload: dict) -> dict: ...


class TrustedBase(ABC):
    """
    Classe de base optionnelle pour les plugins Trusted.

    Fournit :
      - self.ctx           → PluginContext (services, events, hooks, env, config)
      - self.get_service() → accès typé à un service
      - Hooks de cycle de vie (on_load, on_unload, on_reload)
      - get_router()       → expose des routes HTTP FastAPI custom (optionnel)

    Exemple avec routes custom :
        from fastapi import APIRouter
        from xcore.sdk import TrustedBase, ok

        class Plugin(TrustedBase):

            async def on_load(self):
                self.db = self.get_service("db")

            def get_router(self) -> APIRouter:
                router = APIRouter(prefix="/users", tags=["users"])

                @router.get("/")
                async def list_users():
                    with self.db.session() as s:
                        return s.execute(...).fetchall()

                @router.post("/")
                async def create_user(data: dict):
                    ...

                return router

            async def handle(self, action: str, payload: dict) -> dict:
                ...

    Les routes sont montées automatiquement sur l'app FastAPI au boot
    sous le préfixe /{plugin_prefix}/<plugin_name>/ + le préfixe déclaré dans get_router().
    """

    def __init__(self) -> None:
        self.ctx: Any = None  # injecté par LifecycleManager._inject_context()

    async def _inject_context(self, ctx: Any) -> None:
        """Appelé par le framework — ne pas overrider sauf raison valable."""
        self.ctx = ctx
        # Rétro-compatibilité v1 : expose _services directement
        self._services = ctx.services if ctx else {}

    def get_service(self, name: str) -> Any:
        if self.ctx is None:
            raise RuntimeError("Contexte non injecté — plugin non encore chargé.")
        svc = self.ctx.services.get(name)
        if svc is None:
            raise KeyError(
                f"Service '{name}' indisponible. "
                f"Disponibles : {list(self.ctx.services.keys())}"
            )
        return svc

    def get_router(self) -> "Any | None":
        """
        Override cette méthode pour exposer des routes HTTP FastAPI custom.

        Retourne un APIRouter ou None (défaut = pas de routes custom).
        Le router est monté automatiquement sous /plugins/<name>/<ton_prefix>.

        Exemple:
            def get_router(self):
                from fastapi import APIRouter
                router = APIRouter(prefix="/items", tags=["items"])

                @router.get("/")
                async def list_items():
                    return [...]

                return router
        """
        return None

    @abstractmethod
    async def handle(self, action: str, payload: dict) -> dict: ...

    # Hooks de cycle de vie (optionnels)
    async def on_load(self) -> None: ...
    async def on_unload(self) -> None: ...
    async def on_reload(self) -> None: ...


# ── Réponses standardisées ────────────────────────────────────


def ok(data: dict | None = None, **kwargs) -> dict:
    """Construit une réponse succès."""
    return {"status": "ok", **(data or {}), **kwargs}


def error(msg: str, code: str | None = None, **kwargs) -> dict:
    """Construit une réponse erreur."""
    r = {"status": "error", "msg": msg}
    if code:
        r["code"] = code
    r |= kwargs
    return r
