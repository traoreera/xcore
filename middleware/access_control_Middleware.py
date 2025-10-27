from typing import Any, Dict, List, Optional

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from auth.models import User
from database.db import get_db
from security.token import Token


class AccessControlMiddleware(BaseHTTPMiddleware):
    """
    Middleware de contrôle d'accès basé sur JWT, rôles, permissions et méthodes HTTP.
    """

    def __init__(self, app, access_rules: Optional[Dict[str, Any]] = None):
        super().__init__(app)
        self.access_rules = access_rules or {}
        self.token = Token()

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method.upper()

        # Trouve la règle correspondante à la route + méthode
        rule = self._match_rule(path, method)
        if not rule:
            return await call_next(request)

        # Extraction du token JWT
        token = self._get_token_from_header(request)
        if not token:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing or invalid Authorization header"},
            )

        try:
            payload = self.token.verify(token, HTTPException)
        except Exception:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid or expired token"},
            )

        db = next(get_db())
        user = db.query(User).filter(User.email == payload.get("sub")).first()

        if not user or not user.is_active:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Inactive or unknown user"},
            )

        # Récupération des rôles et permissions
        user_roles = [r.name for r in user.roles]
        user_permissions = {p.name for r in user.roles for p in r.permissions}

        required_roles: List[str] = rule.get("roles", [])
        required_perms: List[str] = rule.get("permissions", [])

        # Vérification des rôles
        if required_roles and not any(r in user_roles for r in required_roles):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "detail": f"Access denied. Missing required role(s): {required_roles}"
                },
            )

        # Vérification des permissions
        if required_perms and not any(p in user_permissions for p in required_perms):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "detail": f"Access denied. Missing required permission(s): {required_perms}"
                },
            )

        # Si tout est OK → continuer
        return await call_next(request)

    # ------------------------------------------------------
    # Utils
    # ------------------------------------------------------

    def _get_token_from_header(self, request: Request) -> Optional[str]:
        """Récupère le token Bearer dans le header Authorization"""
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None
        return auth_header.split(" ")[1]

    def _match_rule(self, path: str, method: str) -> Optional[Dict[str, Any]]:
        """
        Retourne la règle correspondante à une route + méthode HTTP.
        Supporte :
        - Correspondance stricte ou par préfixe (ex: /admin/*)
        - Règle spécifique à une méthode (GET, POST, DELETE)
        """
        for rule_path, rule_data in self.access_rules.items():
            if self._path_match(path, rule_path):
                rule_method = rule_data.get("method")
                if not rule_method or rule_method.upper() == method:
                    return rule_data
        return None

    def _path_match(self, path: str, rule_path: str) -> bool:
        """Supporte les wildcard `*` dans les chemins de règles."""
        if rule_path.endswith("*"):
            return path.startswith(rule_path[:-1])
        return path == rule_path
