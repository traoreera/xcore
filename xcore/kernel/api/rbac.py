# xcore/kernel/api/rbac.py
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .auth import get_auth_backend

bearer = HTTPBearer(auto_error=False)


class RBACChecker:
    """
    Dependency FastAPI injectable par route.
    Délègue entièrement au plugin auth enregistré.
    Si aucun backend enregistré → comportement configurable (strict ou permissif).
    """

    def __init__(
        self,
        required_permissions: list[str],
        strict: bool = True,  # False = skip si pas de backend (dev mode)
    ) -> None:
        self._required = set(required_permissions)
        self._strict = strict

    async def __call__(
        self,
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> dict:
        backend = get_auth_backend()

        # Pas de backend enregistré
        if backend is None:
            if self._strict:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Auth backend non disponible — plugin auth non chargé",
                )
            # Dev mode : passe sans user
            return {}

        # Extraction du token — le backend décide (Header, Cookie, etc.)
        token = await backend.extract_token(request)

        if token is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token manquant",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Décodage et validation — le backend gère JWT, sessions, etc.
        user = await backend.decode_token(token)

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalide ou expiré",
            )

        # Vérification des permissions
        if self._required:
            user_roles: set[str] = set(user.get("roles", []))
            user_perms: set[str] = set(user.get("permissions", []))
            granted = user_roles | user_perms

            if missing := self._required - granted:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permissions manquantes : {sorted(missing)}",
                )

        request.state.user = user
        return user


def require_role(*roles: str, strict: bool = True) -> RBACChecker:
    return RBACChecker(list(roles), strict=strict)


def require_permission(*perms: str, strict: bool = True) -> RBACChecker:
    return RBACChecker(list(perms), strict=strict)
