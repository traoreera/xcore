# xcore/kernel/api/auth.py
from __future__ import annotations

from contextvars import ContextVar
from typing import List, NotRequired, Protocol, TypedDict, runtime_checkable

from typing_extensions import Any


class AuthPayload(TypedDict):
    sub: str
    roles: NotRequired[List[str]]
    permissions: NotRequired[List[str]]
    user: NotRequired[dict[str, Any]]


class RequestAdapter(Protocol):
    headers: dict
    cookies: dict
    query_params: dict


@runtime_checkable
class AuthBackend(Protocol):
    async def decode_token(self, token: str) -> AuthPayload | None: ...

    async def extract_token(self, request: RequestAdapter) -> str | None: ...

    async def has_permission(self, payload: AuthPayload, permission: str) -> bool: ...


# ── Registry singleton ────────────────────────────────────────
_backend: AuthBackend | None = None


def register_auth_backend(backend: AuthBackend) -> None:
    """
    Appelé par le plugin auth dans on_load().
    Enregistre l'implémentation active.
    """
    global _backend
    if not isinstance(backend, AuthBackend):
        raise TypeError(
            f"{type(backend).__name__} ne respecte pas le protocole AuthBackend. "
            "Implémentez decode_token() et extract_token()."
        )
    _backend = backend


def unregister_auth_backend() -> None:
    """Appelé par le plugin auth dans on_unload()."""
    global _backend
    _backend = None


def get_auth_backend() -> AuthBackend | None:
    return _backend


def has_auth_backend() -> bool:
    return _backend is not None


# ── Résolution de l'utilisateur courant sur l'appel IPC ───────────────────────
# Même pattern que _current_tenant_id (tenancy/services.py) : ContextVar posée
# par PluginSupervisor._dispatch() pour l'appel en cours, jamais une mutation
# d'un objet partagé — chaque tâche asyncio voit sa propre valeur.
_current_principal: ContextVar["AuthPayload | None"] = ContextVar(
    "xcore_current_principal", default=None
)


def get_current_principal() -> AuthPayload | None:
    """
    Principal (sub/roles/permissions) résolu pour l'appel IPC en cours via
    l'AuthBackend enregistré — None si aucun token n'a été transmis ou résolu.
    """
    return _current_principal.get()


async def resolve_principal_from_request(request: RequestAdapter) -> AuthPayload | None:
    """
    Résolution best-effort de l'utilisateur depuis une requête HTTP entrante,
    via l'AuthBackend enregistré. Ne lève jamais : retourne None si aucun
    backend n'est enregistré, si aucun token n'est présent, ou s'il est invalide
    — l'enforcement (401/403) reste la responsabilité de RBACChecker sur les
    routes qui le requièrent explicitement.
    """
    backend = get_auth_backend()
    if backend is None:
        return None
    token = await backend.extract_token(request)
    if token is None:
        return None
    return await backend.decode_token(token)
