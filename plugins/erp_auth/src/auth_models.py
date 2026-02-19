"""
erp_auth/src/models.py
───────────────────────
Tables SQLAlchemy du module auth.
Préfixe : auth_*

On ne redéclare pas User ici — il est dans erp_core (core_users).
On ajoute uniquement la table des refresh tokens (sessions actives).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase


class LocalBase(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RefreshToken(LocalBase):
    """
    Stocke les refresh tokens actifs.
    Permet la révocation (logout, logout-all-devices).
    """

    __tablename__ = "auth_refresh_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    device = Column(String(200))  # "Chrome / Windows", "iPhone 15"…
    ip_address = Column(String(45))  # IPv4 ou IPv6
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=_now)

    def is_valid(self) -> bool:
        return not self.revoked and datetime.now(timezone.utc) < self.expires_at
