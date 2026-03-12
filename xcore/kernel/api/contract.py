"""
Interface contracts for v2 plugins.
BasePlugin: Structural protocol (duck typing, no inheritance required).
TrustedBase: ABC with rich context injection.
ExecutionMode: Enum of execution modes."""

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
    Minimal contract. Duck typing — no need for inheritance.
    The plugin must expose:
    async def handle(self, action: str, payload: dict) -> dict
    """

    async def handle(self, action: str, payload: dict) -> dict: ...


class TrustedBase(ABC):
    """
    Base optional class for trusted plugins.

    given the following access:
      - self.ctx           → PluginContext (services, events, hooks, env, config)
      - self.get_service() → accès typé à un service
      - Hooks de cycle de vie (on_load, on_unload, on_reload)
      - get_router() or router()       → expose des routes HTTP FastAPI custom (optionnel)

    eg with custom routes:
    ```python
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
        ```
    Routes are automatically mounted on the FastAPI app at boot
    under the prefix /{plugin_prefix}/<plugin_name>/ + the prefix declared in get_router().
    """

    def __init__(self) -> None:
        self.ctx: Any = None  # injecté par LifecycleManager._inject_context()

    async def _inject_context(self, ctx: Any) -> None:
        """Called by the framework — do not override unless there is a valid reason."""
        self.ctx = ctx
        # Rétro-compatibilité v1 : expose _services directement
        self._services = ctx.services if ctx else {}

    def get_service(self, name: str) -> Any:
        if self.ctx is None:
            raise RuntimeError("Context not injected — plugin not yet loaded.")
        svc = self.ctx.services.get(name)
        if svc is None:
            raise KeyError(
                f"Service '{name}' indisponible. "
                f"Disponibles : {list(self.ctx.services.keys())}"
            )
        return svc

    def get_router(self) -> "Any | None":
        """
        Override this method to expose custom FastAPI HTTP routes.
        Returns an APIRouter or None (default = no custom routes).
        The router is automatically mounted under /plugins/<name>/<your_prefix>.

        Example:
        ```python
        def get_router(self):
            from fastapi import APIRouter
            router = APIRouter(prefix="/items", tags=["items"])
            @router.get("/")
            async def list_items():
            return router
        ```
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
    """Build success response"""
    return {"status": "ok", **(data or {}), **kwargs}


def error(msg: str, code: str | None = None, **kwargs) -> dict:
    """Build error response."""
    r = {"status": "error", "msg": msg}
    if code:
        r["code"] = code
    r |= kwargs
    return r
