"""
erp_core/src/models.py
───────────────────────
Tables SQLAlchemy du module core.
Convention : préfixe "core_" sur toutes les tables pour éviter les collisions.

Ces modèles sont enregistrés sur le Base partagé injecté par le PluginManager
(service "base") — tous les autres plugins ERP peuvent y faire des FK.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship

# ── Base partagée ─────────────────────────────────────────────────
# Sera remplacée par le Base injecté par le PluginManager au on_load.
# On la déclare ici pour que les modèles soient importables en standalone.


class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ══════════════════════════════════════════════════════════════════
# Société (Company)
# ══════════════════════════════════════════════════════════════════


class Company(Base):
    __tablename__ = "core_companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    legal_name = Column(String(200))
    tax_id = Column(String(50), unique=True)  # SIRET / VAT
    country = Column(String(2), default="FR")  # ISO 3166-1 alpha-2
    currency = Column(String(3), default="EUR")  # ISO 4217
    address = Column(Text)
    phone = Column(String(30))
    email = Column(String(120))
    website = Column(String(200))
    logo_url = Column(String(500))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    users = relationship("User", back_populates="company")
    currencies = relationship("Currency", back_populates="company")

    def __repr__(self) -> str:
        return f"<Company {self.name!r}>"


# ══════════════════════════════════════════════════════════════════
# Utilisateur (User)
# ══════════════════════════════════════════════════════════════════


class User(Base):
    __tablename__ = "core_users"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("core_companies.id"), nullable=False)
    email = Column(String(200), nullable=False, index=True)
    username = Column(String(80), nullable=False)
    full_name = Column(String(200))
    hashed_pwd = Column(String(200), nullable=False)
    role = Column(String(50), default="user")  # admin | manager | user
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    company = relationship("Company", back_populates="users")

    __table_args__ = (
        UniqueConstraint("company_id", "email", name="uq_user_company_email"),
    )

    def __repr__(self) -> str:
        return f"<User {self.email!r} [{self.role}]>"


# ══════════════════════════════════════════════════════════════════
# Devise (Currency)
# ══════════════════════════════════════════════════════════════════


class Currency(Base):
    __tablename__ = "core_currencies"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("core_companies.id"), nullable=False)
    code = Column(String(3), nullable=False)  # EUR, USD, XOF…
    name = Column(String(60), nullable=False)
    symbol = Column(String(5))
    rate_to_base = Column(Float, default=1.0)  # taux vs devise de base société
    is_base = Column(Boolean, default=False)  # devise de référence ?
    is_active = Column(Boolean, default=True)

    company = relationship("Company", back_populates="currencies")

    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_currency_company_code"),
    )

    def __repr__(self) -> str:
        return f"<Currency {self.code} ({self.rate_to_base})>"


# ══════════════════════════════════════════════════════════════════
# Pays (Country) — table de référence, pas liée à une société
# ══════════════════════════════════════════════════════════════════


class Country(Base):
    __tablename__ = "core_countries"

    id = Column(Integer, primary_key=True)
    iso2 = Column(String(2), nullable=False, unique=True)  # FR, BF, US…
    iso3 = Column(String(3), nullable=False, unique=True)  # FRA, BFA, USA…
    name_fr = Column(String(100), nullable=False)
    name_en = Column(String(100), nullable=False)
    phone_prefix = Column(String(10))  # +33, +226…
    currency = Column(String(3))  # devise locale ISO 4217

    def __repr__(self) -> str:
        return f"<Country {self.iso2} — {self.name_fr}>"
