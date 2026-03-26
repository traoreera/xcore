# xcore/kernel/api/auth.py
from __future__ import annotations
from typing import Protocol, runtime_checkable, TypedDict, NotRequired, List


class AuthPayload(TypedDict):
    sub: str
    roles: NotRequired[List[str]]
    permissions: NotRequired[List[str]]


class RequestAdapter(Protocol):
    headers: dict
    cookies: dict
    query_params: dict


@runtime_checkable
class AuthBackend(Protocol):

    async def decode_token(self, token: str) -> AuthPayload | None:
        ...

    async def extract_token(self, request: RequestAdapter) -> str | None:
        ...

    async def has_permission(
        self,
        payload: AuthPayload,
        permission: str
    ) -> bool:
        ...



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