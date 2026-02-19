"""
erp_core/src/schemas.py
────────────────────────
Schémas Pydantic pour la validation des données en entrée/sortie.
Utilisés par le router FastAPI ET retournés dans les réponses handle().
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

# ══════════════════════════════════════════════
# Company
# ══════════════════════════════════════════════


class CompanyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    legal_name: Optional[str] = None
    tax_id: Optional[str] = None
    country: str = "FR"
    currency: str = "EUR"
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None


class CompanyOut(BaseModel):
    id: int
    name: str
    legal_name: Optional[str]
    tax_id: Optional[str]
    country: str
    currency: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════
# User
# ══════════════════════════════════════════════


class UserCreate(BaseModel):
    company_id: int
    email: str = Field(..., min_length=3, max_length=200)
    username: str = Field(..., min_length=2, max_length=80)
    full_name: Optional[str] = None
    password: str = Field(..., min_length=8)
    role: str = "user"


class UserOut(BaseModel):
    id: int
    company_id: int
    email: str
    username: str
    full_name: Optional[str]
    role: str
    is_active: bool
    last_login: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════
# Currency
# ══════════════════════════════════════════════


class CurrencyCreate(BaseModel):
    company_id: int
    code: str = Field(..., min_length=3, max_length=3)
    name: str
    symbol: Optional[str] = None
    rate_to_base: float = 1.0
    is_base: bool = False


class CurrencyOut(BaseModel):
    id: int
    company_id: int
    code: str
    name: str
    symbol: Optional[str]
    rate_to_base: float
    is_base: bool
    is_active: bool

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════
# Country
# ══════════════════════════════════════════════


class CountryOut(BaseModel):
    id: int
    iso2: str
    iso3: str
    name_fr: str
    name_en: str
    phone_prefix: Optional[str]
    currency: Optional[str]

    model_config = {"from_attributes": True}
