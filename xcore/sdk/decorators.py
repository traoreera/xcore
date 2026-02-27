"""
decorators.py — Décorateurs utilitaires pour les plugins xcore v2.

Usage:
    from xcore.sdk import TrustedBase, action, require_service

    class Plugin(TrustedBase):

        @action("greet")
        async def greet(self, payload: dict) -> dict:
            name = payload.get("name", "world")
            return ok(message=f"Hello {name}!")

        @action("save")
        @require_service("db")
        async def save(self, payload: dict) -> dict:
            db = self.get_service("db")
            ...
"""

from __future__ import annotations

import asyncio
import functools
import logging
from typing import Any, Callable

logger = logging.getLogger("xcore.sdk.decorators")


def action(name: str):
    """
    Marque une méthode comme handler d'action.
    Génère automatiquement un dispatch dans handle() si utilisé avec AutoDispatchMixin.
    """

    def decorator(fn: Callable) -> Callable:
        fn._xcore_action = name
        return fn

    return decorator


def trusted(fn: Callable) -> Callable:
    """Marque une méthode comme ne devant s'exécuter qu'en mode Trusted."""
    fn._xcore_trusted_only = True
    return fn


def sandboxed(fn: Callable) -> Callable:
    """Marque une méthode comme compatible mode Sandboxed."""
    fn._xcore_sandboxed = True
    return fn


def require_service(*service_names: str):
    """
    Vérifie que les services requis sont disponibles avant d'exécuter la méthode.
    Lève KeyError avec un message clair si un service est absent.
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(self, *args, **kwargs):
            for svc_name in service_names:
                if not hasattr(self, "get_service"):
                    break
                self.get_service(svc_name)  # lève KeyError si absent
            return await fn(self, *args, **kwargs)

        wrapper._requires_services = list(service_names)
        return wrapper

    return decorator


def validate_payload(**schema: type):
    """
    Valide les types des champs du payload.
    Retourne {"status": "error"} si la validation échoue.

    Usage:
        @validate_payload(name=str, age=int)
        async def create_user(self, payload: dict) -> dict:
            ...
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(self, payload: dict, *args, **kwargs):
            for field, expected_type in schema.items():
                if field not in payload:
                    from ..kernel.api.contract import error

                    return error(
                        f"Champ obligatoire manquant : '{field}'", "validation_error"
                    )
                if not isinstance(payload[field], expected_type):
                    from ..kernel.api.contract import error

                    return error(
                        f"'{field}' doit être de type {expected_type.__name__}, "
                        f"reçu {type(payload[field]).__name__}",
                        "validation_error",
                    )
            return await fn(self, payload, *args, **kwargs)

        return wrapper

    return decorator


def route(
    path: str,
    method: str = "GET",
    *,
    tags: list[str] | None = None,
    summary: str | None = None,
    status_code: int = 200,
    response_model=None,
):
    """
    Décorateur pour déclarer une route HTTP FastAPI directement sur le plugin.

    Usage:
        class Plugin(RoutedPlugin, TrustedBase):

            @route("/items", method="GET", tags=["items"])
            async def list_items(self):
                return [{"id": 1, "name": "foo"}]

            @route("/items/{item_id}", method="GET")
            async def get_item(self, item_id: int):
                return {"id": item_id}

            @route("/items", method="POST", status_code=201)
            async def create_item(self, body: dict):
                return {"created": True}

            async def handle(self, action: str, payload: dict) -> dict:
                return {"status": "ok"}

    Les routes sont montées automatiquement sur l'app FastAPI au boot
    sous /plugins/<plugin_name><path>.
    """

    def decorator(fn: Callable) -> Callable:
        fn._xcore_route = {
            "path": path,
            "method": method.upper(),
            "tags": tags or [],
            "summary": summary or fn.__name__.replace("_", " ").title(),
            "status_code": status_code,
            "response_model": response_model,
        }
        return fn

    return decorator


class RoutedPlugin:
    """
    Mixin qui génère automatiquement get_router() à partir des méthodes @route.

    Usage:
        class Plugin(RoutedPlugin, TrustedBase):

            @route("/ping", method="GET")
            async def ping(self):
                return {"pong": True}

    Combine avec AutoDispatchMixin pour avoir à la fois @action et @route :

        class Plugin(RoutedPlugin, AutoDispatchMixin, TrustedBase):

            @action("status")
            async def status_action(self, payload: dict) -> dict:
                return ok(status="running")

            @route("/status", method="GET")
            async def status_http(self):
                return {"status": "running"}
    """

    def get_router(self) -> "Any":
        try:
            from fastapi import APIRouter
        except ImportError as e:
            raise ImportError("fastapi non installé — pip install fastapi") from e

        router = APIRouter()
        for attr_name in dir(self):
            method = getattr(self.__class__, attr_name, None)
            if method is None or not callable(method):
                continue
            route_info = getattr(method, "_xcore_route", None)
            if not route_info:
                continue

            # Crée un handler lié à self (closure)
            bound = getattr(self, attr_name)

            # fastapi attend une fonction, pas une méthode bound
            import functools

            @functools.wraps(method)
            async def _handler(*args, _fn=bound, **kwargs):
                import inspect

                sig = inspect.signature(_fn)
                # Retire les paramètres FastAPI non présents dans la signature
                filtered = {k: v for k, v in kwargs.items() if k in sig.parameters}
                return (
                    await _fn(**filtered)
                    if asyncio.iscoroutinefunction(_fn)
                    else _fn(**filtered)
                )

            router.add_api_route(
                path=route_info["path"],
                endpoint=_handler,
                methods=[route_info["method"]],
                tags=route_info["tags"],
                summary=route_info["summary"],
                status_code=route_info["status_code"],
                response_model=route_info["response_model"],
            )

        return router if router.routes else None


class AutoDispatchMixin:
    """
    Mixin qui génère automatiquement handle() à partir des méthodes décorées @action.

    Usage:
        class Plugin(AutoDispatchMixin, TrustedBase):

            @action("greet")
            async def greet(self, payload: dict) -> dict:
                return ok(msg="hello")

            @action("bye")
            async def bye(self, payload: dict) -> dict:
                return ok(msg="goodbye")

        # handle("greet", {}) → appelle self.greet({})
        # handle("unknown", {}) → {"status": "error", "code": "unknown_action"}
    """

    async def handle(self, action_name: str, payload: dict) -> dict:
        from ..kernel.api.contract import error

        for attr_name in dir(self):
            method = getattr(self, attr_name, None)
            if (
                callable(method)
                and getattr(method, "_xcore_action", None) == action_name
            ):
                return await method(payload)

        available = [
            getattr(getattr(self, a), "_xcore_action")
            for a in dir(self)
            if callable(getattr(self, a, None))
            and hasattr(getattr(self, a), "_xcore_action")
        ]
        return error(
            f"Action '{action_name}' inconnue. Disponibles : {available}",
            "unknown_action",
        )
