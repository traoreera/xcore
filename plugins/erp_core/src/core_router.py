"""
erp_core/src/router.py
───────────────────────
Routes FastAPI du module erp_core.
Ce router est auto-attaché à l'app par le PluginManager via _attach_routes().
Aucun enregistrement manuel requis dans main.py.
"""

from __future__ import annotations

from core_schemas import (
    CompanyCreate,
    CompanyOut,
    CurrencyCreate,
    CurrencyOut,
    UserCreate,
    UserOut,
)
from core_services import CoreService
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

# ── Dépendance DB ─────────────────────────────────────────────────
# La session est injectée par FastAPI via le service "db" du PluginManager.
# On utilise une fonction get_db() classique — à brancher sur ta DB.

_db_dependency = None  # sera injecté par Plugin.on_load()


def get_db() -> Session:
    if _db_dependency is None:
        raise RuntimeError("DB non initialisée — erp_core.on_load() non appelé")
    yield from _db_dependency()


def get_core(db: Session = Depends(get_db)) -> CoreService:
    return CoreService(db)


router = APIRouter(prefix="/core", tags=["ERP — Core"])


# ══════════════════════════════════════════════
# Sociétés
# ══════════════════════════════════════════════


@router.post("/companies", response_model=CompanyOut, status_code=201)
def create_company(
    data: CompanyCreate,
    core: CoreService = Depends(get_core),
):
    return core.create_company(data)


@router.get("/companies", response_model=list[CompanyOut])
def list_companies(core: CoreService = Depends(get_core)):
    return core.list_companies()


@router.get("/companies/{company_id}", response_model=CompanyOut)
def get_company(company_id: int, core: CoreService = Depends(get_core)):
    result = core.get_company(company_id)
    if not result:
        raise HTTPException(status_code=404, detail="Société introuvable")
    return result


# ══════════════════════════════════════════════
# Utilisateurs
# ══════════════════════════════════════════════


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(data: UserCreate, core: CoreService = Depends(get_core)):
    return core.create_user(data)


@router.get("/companies/{company_id}/users", response_model=list[UserOut])
def list_users(company_id: int, core: CoreService = Depends(get_core)):
    return core.list_users(company_id)


@router.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int, core: CoreService = Depends(get_core)):
    result = core.get_user(user_id)
    if not result:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    return result


# ══════════════════════════════════════════════
# Devises
# ══════════════════════════════════════════════


@router.post("/currencies", response_model=CurrencyOut, status_code=201)
def create_currency(data: CurrencyCreate, core: CoreService = Depends(get_core)):
    return core.create_currency(data)


@router.get("/companies/{company_id}/currencies", response_model=list[CurrencyOut])
def list_currencies(company_id: int, core: CoreService = Depends(get_core)):
    return core.list_currencies(company_id)


@router.get("/exchange-rate")
def exchange_rate(
    company_id: int,
    from_code: str,
    to_code: str,
    core: CoreService = Depends(get_core),
):
    try:
        rate = core.get_exchange_rate(company_id, from_code.upper(), to_code.upper())
        return {"from": from_code, "to": to_code, "rate": rate}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ══════════════════════════════════════════════
# Pays
# ══════════════════════════════════════════════


@router.get("/countries", response_model=list[dict])
def list_countries(core: CoreService = Depends(get_core)):
    return core.list_countries()


@router.get("/countries/{iso2}")
def get_country(iso2: str, core: CoreService = Depends(get_core)):
    result = core.get_country(iso2)
    if not result:
        raise HTTPException(status_code=404, detail=f"Pays '{iso2}' introuvable")
    return result
