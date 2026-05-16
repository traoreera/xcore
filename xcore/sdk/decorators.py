"""
decorators.py — Décorateurs utilitaires pour les plugins xcore v2.

Usage:
```python
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
    ```
"""

from __future__ import annotations

import functools
import inspect
import logging
from typing import Any, Callable, Literal, Type

from pydantic import BaseModel, ValidationError, create_model

from ..kernel.api.contract import error

logger = logging.getLogger("xcore.sdk.decorators")


def _type_name(t: Any) -> str:
    """Convertit un type Python en nom lisible pour le SchemaRegistry."""
    if isinstance(t, str):
        return t
    # Tuple pydantic (type, default) — ex: (str, ...) ou (int, 0)
    if isinstance(t, tuple) and len(t) == 2:
        return _type_name(t[0])
    if hasattr(t, "__name__"):
        return t.__name__  # type: ignore
    # Literal, Optional, Union…
    return str(t)


def schema(
    version: str,
    input: dict[str, Any] | None = None,
    output: dict[str, Any] | None = None,
    deprecated_fields: dict[str, str] | None = None,
    breaking_since: str | None = None,
    description: str = "",
    validate: bool = True,
    type_response: Literal["dict", "model", "_"] = "_",
    unset: bool = False,
):
    """
    Déclare le schéma versionné d'une action, l'enregistre dans le SchemaRegistry,
    et applique automatiquement la validation du payload (validate=True par défaut).

    Le format du dict `input` suit la convention pydantic create_model :
      - type seul          → champ requis       : {"email": str}
      - (type, ...)        → champ requis       : {"email": (str, ...)}
      - (type, default)    → champ optionnel    : {"role": (str, "user")}

    Usage :
        @action("create_user")
        @schema(
            version="2.0",
            input={"email": (str, ...), "role": (str, "user")},
            output={"user_id": int, "created_at": str},
            deprecated_fields={"username": "Supprimé en v2.0 — utiliser email"},
            breaking_since="2.0",
            type_response:Literal['dict', 'model', "_"]= "_",
            unset:bool=False,
        )
        async def create_user(self, payload: dict) -> dict:
            # payload est déjà validé — email et role sont garantis
            ...
    """

    def decorator(fn: Callable) -> Callable:
        # Normalise les types simples en tuples pydantic (type, ...)
        input_fields = {}
        for k, v in (input or {}).items():
            input_fields[k] = v if isinstance(v, tuple) else (v, ...)

        # Applique validate_payload automatiquement si input est défini
        wrapped = (
            validate_payload(
                schema=input_fields, type_response=type_response, unset=unset
            )(fn)
            if validate and input_fields and type_response != "_"
            else fn
        )

        wrapped._xcore_schema = {
            "version": version,
            "input": {k: _type_name(v) for k, v in input_fields.items()},
            "output": {k: _type_name(v) for k, v in (output or {}).items()},
            "deprecated_fields": deprecated_fields or {},
            "breaking_since": breaking_since,
            "description": description,
        }
        return wrapped

    return decorator


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
    schema: Type[BaseModel] | dict,
    type_response: Literal["dict", "model"] = "dict",
    unset: bool = True,
):
    """
    schema:
      - classe Pydantic
      - dict dynamique
    """

    if isinstance(schema, dict):
        Model = create_model("DynamicSchema", **schema)

    elif isinstance(schema, type) and issubclass(schema, BaseModel):
        Model = schema

    else:
        raise TypeError("schema must be dict or BaseModel class")

    def decorator(f: Callable):
        @functools.wraps(f)
        async def wrapper(self, payload: dict, *args, **kwargs):
            try:
                validated = Model(**payload)

            except ValidationError as e:
                return error(
                    "Validation error",
                    "validation_error",
                    errors=e.errors(),
                )

            data = (
                validated
                if type_response == "model"
                else validated.model_dump(exclude_unset=unset)
            )

            return await f(self, data, *args, **kwargs)

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
    dependencies: list | None = None,  # ← FastAPI Depends() par route
    # ← RBAC déclaratif ["admin", "read:users"]
    permissions: list[str] | None = None,
    scopes: list[str] | None = None,  # ← OAuth2 scopes si besoin
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
            "dependencies": dependencies or [],
            "permissions": permissions or [],
            "scopes": scopes or [],
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

    # xcore/sdk/decorators.py — méthode RouterIn de RoutedPlugin

    def RouterIn(self):
        from fastapi import APIRouter, Depends

        from xcore.kernel.api.rbac import RBACChecker

        router = APIRouter()

        for attr_name in dir(self.__class__):
            method = getattr(self.__class__, attr_name, None)
            route_info = getattr(method, "_xcore_route", None)
            if not route_info:
                continue

            bound = getattr(self, attr_name)

            # ── Construit les dependencies ──────────────────────────
            route_deps = list(route_info.get("dependencies", []))

            # RBAC automatique depuis `permissions`
            required_perms = route_info.get("permissions", [])
            if required_perms:
                route_deps.append(Depends(RBACChecker(required_perms)))

            # ── Handler ────────────────────────────────────────────
            def make_handler(fn):
                @functools.wraps(fn)
                async def handler(**kwargs):
                    return (
                        await fn(**kwargs)
                        if inspect.iscoroutinefunction(fn)
                        else fn(**kwargs)
                    )

                sig = inspect.signature(fn)
                params = [p for name, p in sig.parameters.items() if name != "self"]
                handler.__signature__ = sig.replace(parameters=params)
                return handler

            handler = make_handler(bound)

            router.add_api_route(
                path=route_info["path"],
                endpoint=handler,
                methods=[route_info["method"]],
                tags=route_info["tags"],
                summary=route_info["summary"],
                status_code=route_info["status_code"],
                response_model=route_info["response_model"],
                dependencies=route_deps,  # ← ici, par route
            )

        return router if router.routes else None
