"""
erp_auth/src/schemas.py
────────────────────────
Schémas Pydantic pour l'auth.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str
    device: Optional[str] = None  # "Chrome / Windows"


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # secondes avant expiration access token


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPayload(BaseModel):
    """Contenu décodé du JWT access token."""

    sub: int  # user_id
    email: str
    role: str
    company_id: int
    exp: int  # timestamp expiration


class UserIdentity(BaseModel):
    """
    Objet injecté par get_current_user() dans les routes protégées.
    Disponible via : current_user: UserIdentity = Depends(get_current_user)
    """

    user_id: int
    email: str
    role: str
    company_id: int

    def is_admin(self) -> bool:
        return self.role == "admin"

    def is_manager(self) -> bool:
        return self.role in ("admin", "manager")

    def can(self, *roles: str) -> bool:
        """Vérifie si l'utilisateur a au moins un des rôles requis."""
        return self.role in roles
