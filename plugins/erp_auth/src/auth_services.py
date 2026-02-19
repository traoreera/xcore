"""
erp_auth/src/services.py
─────────────────────────
Logique JWT pure — sans dépendance vers FastAPI.

JWT fait maison (HMAC-SHA256) pour éviter une dépendance python-jose.
Format : header.payload.signature en base64url.
Pour la production, remplace par PyJWT ou python-jose.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from auth_models import RefreshToken
from auth_schemas import LoginRequest, TokenPair, TokenPayload, UserIdentity
from sqlalchemy.orm import Session

logger = logging.getLogger("erp_auth.services")

# ── Durées par défaut ─────────────────────────────────────────────
ACCESS_TOKEN_TTL = timedelta(minutes=30)
REFRESH_TOKEN_TTL = timedelta(days=7)


# ══════════════════════════════════════════════════════════════════
# JWT maison — HMAC-SHA256
# ══════════════════════════════════════════════════════════════════


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + "=" * padding)


def _make_jwt(payload: dict, secret: bytes) -> str:
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = _b64url_encode(json.dumps(payload).encode())
    sig_input = f"{header}.{body}".encode()
    sig = _b64url_encode(hmac.new(secret, sig_input, hashlib.sha256).digest())
    return f"{header}.{body}.{sig}"


def _verify_jwt(token: str, secret: bytes) -> dict | None:
    """Retourne le payload si valide, None si signature invalide ou expiré."""
    try:
        header, body, sig = token.split(".")
    except ValueError:
        return None
    expected_sig = _b64url_encode(
        hmac.new(secret, f"{header}.{body}".encode(), hashlib.sha256).digest()
    )
    if not hmac.compare_digest(sig, expected_sig):
        return None
    payload = json.loads(_b64url_decode(body))
    if payload.get("exp", 0) < datetime.now(timezone.utc).timestamp():
        return None
    return payload


def _hash_token(token: str) -> str:
    """Hash SHA256 du refresh token pour stockage sécurisé en DB."""
    return hashlib.sha256(token.encode()).hexdigest()


# ══════════════════════════════════════════════════════════════════
# AuthService — façade exposée aux autres plugins
# ══════════════════════════════════════════════════════════════════


class AuthService:
    """
    Service principal d'erp_auth.

    Injecté dans les autres plugins via :
        auth = self.get_service("auth")
        user = auth.get_current_user(token)   ← pour la validation manuelle
        depends = auth.require_roles("admin") ← pour les Depends() FastAPI
    """

    def __init__(self, db: Session, secret: bytes) -> None:
        self.db = db
        self.secret = secret

    # ── Login ────────────────────────────────────

    def login(
        self,
        data: LoginRequest,
        core_service: Any,  # CoreService d'erp_core
        ip_address: str | None = None,
    ) -> TokenPair:
        """
        Vérifie les credentials et retourne une paire access/refresh token.
        Lève ValueError si credentials invalides.
        """
        user = core_service.verify_password(data.email, data.password)
        if user is None:
            raise ValueError("Email ou mot de passe incorrect")

        now = datetime.now(timezone.utc)

        # Access token (courte durée)
        access_payload = {
            "sub": user.id,
            "email": user.email,
            "role": user.role,
            "company_id": user.company_id,
            "exp": int((now + ACCESS_TOKEN_TTL).timestamp()),
            "type": "access",
        }
        access_token = _make_jwt(access_payload, self.secret)

        # Refresh token (longue durée, stocké en DB)
        import secrets as _secrets

        raw_refresh = _secrets.token_urlsafe(48)
        refresh_payload = {
            "sub": user.id,
            "jti": raw_refresh[:16],  # identifiant unique
            "exp": int((now + REFRESH_TOKEN_TTL).timestamp()),
            "type": "refresh",
        }
        refresh_token = _make_jwt(refresh_payload, self.secret)

        # Stocke le hash en DB
        db_token = RefreshToken(
            user_id=user.id,
            token_hash=_hash_token(refresh_token),
            device=data.device,
            ip_address=ip_address,
            expires_at=now + REFRESH_TOKEN_TTL,
        )
        self.db.add(db_token)
        self.db.commit()

        logger.info(f"Login réussi : {user.email} (id={user.id})")
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=int(ACCESS_TOKEN_TTL.total_seconds()),
        )

    # ── Vérification token ────────────────────────

    def verify_access_token(self, token: str) -> UserIdentity | None:
        """
        Vérifie et décode un access token.
        Retourne UserIdentity si valide, None sinon.
        Appelé par get_current_user() dans le router.
        """
        payload = _verify_jwt(token, self.secret)
        if payload is None or payload.get("type") != "access":
            return None
        return UserIdentity(
            user_id=payload["sub"],
            email=payload["email"],
            role=payload["role"],
            company_id=payload["company_id"],
        )

    # ── Refresh ───────────────────────────────────

    def refresh(self, refresh_token: str) -> TokenPair | None:
        """
        Échange un refresh token valide contre une nouvelle paire.
        Révoque l'ancien refresh token (rotation).
        """
        payload = _verify_jwt(refresh_token, self.secret)
        if payload is None or payload.get("type") != "refresh":
            return None

        token_hash = _hash_token(refresh_token)
        db_token = (
            self.db.query(RefreshToken)
            .filter(RefreshToken.token_hash == token_hash)
            .first()
        )
        if db_token is None or not db_token.is_valid():
            return None

        # Révocation de l'ancien token (rotation)
        db_token.revoked = True
        self.db.commit()

        # Nouveau login sans vérifier le mot de passe
        from schemas import LoginRequest as LR

        dummy = LR(email="", password="")
        # On reconstruit manuellement pour éviter de re-vérifier le mot de passe
        return self._issue_tokens(payload["sub"])

    def _issue_tokens(self, user_id: int) -> TokenPair | None:
        """Émet une nouvelle paire pour un user_id déjà authentifié."""
        from sqlalchemy import text

        row = self.db.execute(
            text("SELECT id, email, role, company_id FROM core_users WHERE id = :id"),
            {"id": user_id},
        ).fetchone()
        if row is None:
            return None

        now = datetime.now(timezone.utc)
        access_payload = {
            "sub": row[0],
            "email": row[1],
            "role": row[2],
            "company_id": row[3],
            "exp": int((now + ACCESS_TOKEN_TTL).timestamp()),
            "type": "access",
        }
        access_token = _make_jwt(access_payload, self.secret)

        import secrets as _secrets

        raw_refresh = _secrets.token_urlsafe(48)
        refresh_payload = {
            "sub": row[0],
            "jti": raw_refresh[:16],
            "exp": int((now + REFRESH_TOKEN_TTL).timestamp()),
            "type": "refresh",
        }
        refresh_token = _make_jwt(refresh_payload, self.secret)

        db_token = RefreshToken(
            user_id=row[0],
            token_hash=_hash_token(refresh_token),
            expires_at=now + REFRESH_TOKEN_TTL,
        )
        self.db.add(db_token)
        self.db.commit()

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=int(ACCESS_TOKEN_TTL.total_seconds()),
        )

    # ── Logout ────────────────────────────────────

    def logout(self, refresh_token: str) -> bool:
        token_hash = _hash_token(refresh_token)
        db_token = (
            self.db.query(RefreshToken)
            .filter(RefreshToken.token_hash == token_hash)
            .first()
        )
        if db_token:
            db_token.revoked = True
            self.db.commit()
            return True
        return False

    def logout_all(self, user_id: int) -> int:
        """Révoque tous les refresh tokens de l'utilisateur (tous les appareils)."""
        count = (
            self.db.query(RefreshToken)
            .filter(RefreshToken.user_id == user_id, RefreshToken.revoked == False)
            .update({"revoked": True})
        )
        self.db.commit()
        return count
