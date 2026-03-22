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

import functools
import inspect
import logging
from typing import Callable, Type

from pydantic import BaseModel, ValidationError

from ..kernel.api.contract import error

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


def validate_payload(
    schema: Type[BaseModel], type_reponse: Literal["dict", "BaseModel"] = 'BaseModel', unset:bool=True
):
    """
    Valide un payload via un modèle Pydantic.
    Retourne {"status": "error"} si la validation échoue.

    Usage:
        ```python
        class CreateUserModel(BaseModel):
            name: str
            age: int

        @validate_payload(CreateUserModel)
        async def create_user(self, payload: dict) -> dict:
            ...
        ```
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def warpper(self, payload: dict, *args, **kwargs):
            try:
                validate = schema(**payload)
            except ValidationError as e:
                return error(e.errors(), "validation_error")
            return (
                await fn(self, validate, *args, **kwargs)
                if type_reponse == "pydantic"
                else await fn(self, validate.model_dump(exclude_unset=unset), *args, **kwargs)
            )

        return warpper

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

    def RouterIn(self, *args, **kwargs):

        from fastapi import APIRouter

        router = APIRouter()

        def make_handler(fn):
            @functools.wraps(fn)
            async def handler(**kwargs):
                return (
                    await fn(**kwargs)
                    if inspect.iscoroutinefunction(fn)
                    else fn(**kwargs)
                )

            # IMPORTANT → copie la signature SANS self
            sig = inspect.signature(fn)
            params = [p for name, p in sig.parameters.items() if name != "self"]
            handler.__signature__ = sig.replace(parameters=params)  # type: ignore

            return handler

        for attr_name in dir(self.__class__):
            method = getattr(self.__class__, attr_name, None)

            route_info = getattr(method, "_xcore_route", None)
            if not route_info:
                continue
            bound = getattr(self, attr_name)

            handler = make_handler(bound)

            router.add_api_route(
                path=route_info["path"],
                endpoint=handler,
                methods=[route_info["method"]],
                tags=route_info["tags"],
                summary=route_info["summary"],
                status_code=route_info["status_code"],
                response_model=route_info["response_model"],
                *args,
                **kwargs,
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
