# xcore/kernel/api/rbac.py
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .auth import AuthPayload, get_auth_backend

bearer = HTTPBearer(auto_error=False)


# ── Helpers internes ──────────────────────────────────────────────────────────
async def _resolve_user(request: Request) -> AuthPayload:
    """
    Résout l'utilisateur courant depuis request.state (cache) ou via le backend.
    Utilisé par get_current_user et RBACChecker pour éviter un double décodage.
    """
    # Cache : RBACChecker a déjà décodé le token sur cette requête
    cached = getattr(request.state, "user", None)
    if cached is not None:
        return cached

    backend = get_auth_backend()
    if backend is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth backend non disponible — plugin auth non chargé",
        )

    token = await backend.extract_token(request)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token manquant",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await backend.decode_token(token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
        )

    request.state.user = user
    return user


# ── Dépendances publiques ─────────────────────────────────────────────────────


async def get_current_user(
    request: Request,
    _: HTTPAuthorizationCredentials | None = Depends(
        bearer
    ),  # déclenche le header Bearer dans OpenAPI
) -> AuthPayload:
    """
    Dépendance FastAPI — retourne le payload de l'utilisateur authentifié.

    Usage dans une méthode @route :
        @route("/me", method="GET")
        async def me(self, user: AuthPayload = Depends(get_current_user)):
            return {"sub": user["sub"], "roles": user.get("roles", [])}
    """
    return await _resolve_user(request)


async def get_user_session_id(
    user: AuthPayload = Depends(get_current_user),
) -> str:
    """
    Dépendance FastAPI — retourne uniquement le `sub` (identifiant de session/user).

    Usage dans une méthode @route :
        @route("/session", method="GET")
        async def session_info(self, session_id: str = Depends(get_user_session_id)):
            return {"session_id": session_id}
    """
    sub = user.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Payload invalide : champ 'sub' manquant",
        )
    return sub


# ── RBAC ──────────────────────────────────────────────────────────────────────


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
    ) -> AuthPayload:
        backend = get_auth_backend()

        # Pas de backend enregistré
        if backend is None:
            if self._strict:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Auth backend non disponible — plugin auth non chargé",
                )
            # Dev mode : passe sans user
            return {}  # type: ignore[return-value]

        # Réutilise le cache ou décode (évite un double appel si get_current_user
        # est aussi déclaré sur la même route)
        user = await _resolve_user(request)

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

        return user


def require_role(*roles: str, strict: bool = True) -> RBACChecker:
    return RBACChecker(list(roles), strict=strict)


def require_permission(*perms: str, strict: bool = True) -> RBACChecker:
    return RBACChecker(list(perms), strict=strict)
