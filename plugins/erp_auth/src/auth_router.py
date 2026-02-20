"""
erp_auth/src/router.py
───────────────────────
Routes d'authentification + dépendance get_current_user.

USAGE DANS LES AUTRES PLUGINS :
    # Dans erp_crm/src/router.py
    from fastapi import Depends
    # La dépendance est injectée dynamiquement au on_load() de erp_auth
    # via un module partagé accessible sans importer erp_auth directement.
    # Voir: get_current_user() ci-dessous et l'injection dans main.py.
"""

from __future__ import annotations

from auth_schemas import LoginRequest, RefreshRequest, TokenPair, UserIdentity
from auth_services import AuthService
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

# ── Dépendances injectées par Plugin.on_load() ────────────────────
_db_dependency = None  # callable () → Session
_auth_secret = None  # bytes
_core_service_fn = None  # callable () → CoreService

_bearer = HTTPBearer(auto_error=False)


def get_db() -> Session:
    if _db_dependency is None:
        raise RuntimeError("Auth DB non initialisée")
    yield from _db_dependency()


def get_auth(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db, _auth_secret)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> UserIdentity:
    """
    Dépendance FastAPI principale — injectée dans tous les plugins ERP via
    get_service("get_current_user").

    ✅ Pattern proxy : la DB et le secret sont lus au moment de l'APPEL
    (pas à la définition), donc cette fonction est sûre même si elle est
    déclarée avant que _db_dependency et _auth_secret soient injectés.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token manquant",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if _db_dependency is None or _auth_secret is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service auth non initialisé",
        )
    db = next(_db_dependency())
    AuthService(db, _auth_secret)
    identity = None  # auth.verify_access_token(credentials.credentials)
    print(credentials)
    db.close()
    if identity is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return identity


def require_roles(*roles: str):
    """
    Factory de dépendance — vérifie le rôle.

    Usage dans un plugin :
        require_roles = self.get_service("require_roles")

        @router.delete("/items/{id}")
        def delete(current_user=Depends(require_roles("admin"))):
            ...
    """

    def _check(current_user: UserIdentity = Depends(get_current_user)) -> UserIdentity:
        if not current_user.can(*roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Rôle requis : {' ou '.join(roles)}. "
                f"Votre rôle : {current_user.role}",
            )
        return current_user

    return _check


# ── Router ────────────────────────────────────────────────────────

router = APIRouter(prefix="/auth", tags=["ERP — Auth"])


@router.post("/login", response_model=TokenPair)
def login(
    data: LoginRequest,
    request: Request,
):
    """Authentifie un utilisateur et retourne access + refresh tokens."""
    if _db_dependency is None or _auth_secret is None or _core_service_fn is None:
        raise HTTPException(status_code=503, detail="Service auth non initialisé")
    try:
        db = next(_db_dependency())
        auth = AuthService(db, _auth_secret)
        core = _core_service_fn()
        result = auth.login(
            data,
            core_service=core,
            ip_address=request.client.host if request.client else None,
        )
        db.close()
        return result
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/refresh", response_model=TokenPair)
def refresh_token(data: RefreshRequest):
    """Échange un refresh token contre une nouvelle paire (rotation)."""
    if _db_dependency is None or _auth_secret is None:
        raise HTTPException(status_code=503, detail="Service auth non initialisé")
    db = next(_db_dependency())
    auth = AuthService(db, _auth_secret)
    result = auth.refresh(data.refresh_token)
    db.close()
    if result is None:
        raise HTTPException(status_code=401, detail="Refresh token invalide ou révoqué")
    return result


@router.post("/logout")
def logout(data: RefreshRequest):
    """Révoque le refresh token (déconnexion de l'appareil courant)."""
    if _db_dependency is None or _auth_secret is None:
        raise HTTPException(status_code=503, detail="Service auth non initialisé")
    db = next(_db_dependency())
    auth = AuthService(db, _auth_secret)
    auth.logout(data.refresh_token)
    db.close()
    return {"status": "ok", "msg": "Déconnecté"}


@router.post("/logout-all")
def logout_all(current_user: UserIdentity = Depends(get_current_user)):
    """Révoque tous les refresh tokens de l'utilisateur (tous les appareils)."""
    if _db_dependency is None or _auth_secret is None:
        raise HTTPException(status_code=503, detail="Service auth non initialisé")
    db = next(_db_dependency())
    auth = AuthService(db, _auth_secret)
    count = auth.logout_all(current_user.user_id)
    db.close()
    return {"status": "ok", "msg": f"{count} session(s) révoquée(s)"}


@router.get("/me", response_model=UserIdentity)
def me(current_user: UserIdentity = Depends(get_current_user)):
    """Retourne l'identité de l'utilisateur connecté."""
    return current_user
