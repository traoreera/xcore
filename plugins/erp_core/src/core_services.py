"""
erp_core/src/services.py
─────────────────────────
Logique métier pure — aucune dépendance vers FastAPI.
Appelé depuis handle() ET depuis le router.
Tous les autres plugins ERP utilisent ces services via get_service("core").
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from core_models import Company, Country, Currency, User
from core_schemas import (
    CompanyCreate,
    CompanyOut,
    CurrencyCreate,
    CurrencyOut,
    UserCreate,
    UserOut,
)
from sqlalchemy.orm import Session

logger = logging.getLogger("erp_core.services")


# ══════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════


def _hash_password(plain: str) -> str:
    """Hash SHA-256 simple — remplace par bcrypt en production."""
    return hashlib.sha256(plain.encode()).hexdigest()


# ══════════════════════════════════════════════
# CoreService — façade exposée aux autres plugins
# ══════════════════════════════════════════════


class CoreService:
    """
    Service principal d'erp_core.
    Injecté dans les autres plugins via :
        core = self.get_service("core")
        user = core.get_user(db, user_id=1)
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Company ───────────────────────────────

    def create_company(self, data: CompanyCreate) -> CompanyOut:
        company = Company(**data.model_dump())
        self.db.add(company)
        self.db.commit()
        self.db.refresh(company)
        logger.info(f"Société créée : {company.name} (id={company.id})")
        return CompanyOut.model_validate(company)

    def get_company(self, company_id: int) -> CompanyOut | None:
        row = self.db.get(Company, company_id)
        return CompanyOut.model_validate(row) if row else None

    def list_companies(self, active_only: bool = True) -> list[CompanyOut]:
        q = self.db.query(Company)
        if active_only:
            q = q.filter(Company.is_active == True)
        return [CompanyOut.model_validate(c) for c in q.all()]

    # ── User ──────────────────────────────────

    def create_user(self, data: UserCreate) -> UserOut:
        hashed = _hash_password(data.password)
        user = User(
            company_id=data.company_id,
            email=data.email,
            username=data.username,
            full_name=data.full_name,
            hashed_pwd=hashed,
            role=data.role,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        logger.info(f"Utilisateur créé : {user.email} (id={user.id})")
        return UserOut.model_validate(user)

    def get_user(self, user_id: int) -> UserOut | None:
        row = self.db.get(User, user_id)
        return UserOut.model_validate(row) if row else None

    def get_user_by_email(self, email: str) -> UserOut | None:
        row = self.db.query(User).filter(User.email == email).first()
        return UserOut.model_validate(row) if row else None

    def list_users(self, company_id: int) -> list[UserOut]:
        rows = (
            self.db.query(User)
            .filter(User.company_id == company_id, User.is_active == True)
            .all()
        )
        return [UserOut.model_validate(u) for u in rows]

    def verify_password(self, email: str, plain_password: str) -> UserOut | None:
        """Vérifie les credentials — retourne l'user si valide, None sinon."""
        row = self.db.query(User).filter(User.email == email).first()
        if not row:
            return None
        if row.hashed_pwd != _hash_password(plain_password):
            return None
        return UserOut.model_validate(row)

    # ── Currency ──────────────────────────────

    def create_currency(self, data: CurrencyCreate) -> CurrencyOut:
        currency = Currency(**data.model_dump())
        self.db.add(currency)
        self.db.commit()
        self.db.refresh(currency)
        return CurrencyOut.model_validate(currency)

    def list_currencies(self, company_id: int) -> list[CurrencyOut]:
        rows = (
            self.db.query(Currency)
            .filter(Currency.company_id == company_id, Currency.is_active == True)
            .all()
        )
        return [CurrencyOut.model_validate(c) for c in rows]

    def get_exchange_rate(self, company_id: int, from_code: str, to_code: str) -> float:
        """Retourne le taux de change from → to via la devise de base."""
        currencies = {
            c.code: c
            for c in self.db.query(Currency)
            .filter(Currency.company_id == company_id)
            .all()
        }
        if from_code not in currencies or to_code not in currencies:
            raise ValueError(f"Devise inconnue : {from_code} ou {to_code}")
        rate_from = currencies[from_code].rate_to_base
        rate_to = currencies[to_code].rate_to_base
        if rate_from == 0:
            raise ValueError(f"Taux de change zéro pour {from_code}")
        return round(rate_to / rate_from, 6)

    # ── Country ───────────────────────────────

    def list_countries(self) -> list[dict[str, Any]]:
        return [
            {
                "iso2": c.iso2,
                "iso3": c.iso3,
                "name_fr": c.name_fr,
                "name_en": c.name_en,
                "phone_prefix": c.phone_prefix,
                "currency": c.currency,
            }
            for c in self.db.query(Country).order_by(Country.name_fr).all()
        ]

    def get_country(self, iso2: str) -> dict[str, Any] | None:
        row = self.db.query(Country).filter(Country.iso2 == iso2.upper()).first()
        if not row:
            return None
        return {
            "iso2": row.iso2,
            "iso3": row.iso3,
            "name_fr": row.name_fr,
            "name_en": row.name_en,
            "phone_prefix": row.phone_prefix,
            "currency": row.currency,
        }
