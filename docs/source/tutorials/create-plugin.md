# Tutoriel : Créer un Plugin Complet

Ce tutoriel vous guide dans la création d'un plugin ERP complet avec base de données, API REST et interface utilisateur.

## Plugin CRM - Gestion des Clients

Nous allons créer un plugin CRM (Customer Relationship Management) avec les fonctionnalités suivantes :
- Gestion des clients (CRUD)
- Gestion des opportunités commerciales
- Suivi des interactions
- Tableau de bord avec statistiques

## Partie 1 : Structure du Plugin

### 1.1 Créer la Structure

```bash
mkdir -p plugins/erp_crm/{models,routes,services,templates}
touch plugins/erp_crm/__init__.py
touch plugins/erp_crm/plugin.json
touch plugins/erp_crm/run.py
```

### 1.2 Configuration du Plugin

```json
// plugins/erp_crm/plugin.json
{
  "name": "erp_crm",
  "version": "1.0.0",
  "author": "Votre Équipe",
  "description": "Module CRM pour la gestion des clients et opportunités",
  "active": true,
  "async": true,
  "api_prefix": "/erp/crm",
  "tags": ["crm", "clients", "opportunités"],
  "dependencies": ["erp_core"],
  "config": {
    "default_currency": "EUR",
    "opportunity_stages": ["prospect", "qualified", "proposal", "negotiation", "closed_won", "closed_lost"]
  }
}
```

## Partie 2 : Modèles de Données

### 2.1 Modèle Client

```python
# plugins/erp_crm/models/customer.py
from datetime import datetime
from typing import Optional, List

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, Numeric, Boolean
from sqlalchemy.orm import relationship
from database import Base
import enum


class CustomerStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PROSPECT = "prospect"


class CustomerType(str, enum.Enum):
    INDIVIDUAL = "individual"
    COMPANY = "company"


class Customer(Base):
    __tablename__ = "crm_customers"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("erp_companies.id"), nullable=False)

    # Informations de base
    type = Column(Enum(CustomerType), default=CustomerType.INDIVIDUAL)
    status = Column(Enum(CustomerStatus), default=CustomerStatus.PROSPECT)

    # Entreprise
    company_name = Column(String(255), nullable=True)
    siret = Column(String(14), nullable=True)
    vat_number = Column(String(50), nullable=True)

    # Contact
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(50), nullable=True)
    mobile = Column(String(50), nullable=True)

    # Adresse
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    postal_code = Column(String(20), nullable=True)
    country = Column(String(100), default="France")

    # Métadonnées
    notes = Column(Text, nullable=True)
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"))

    # Relations
    opportunities = relationship("Opportunity", back_populates="customer")
    interactions = relationship("Interaction", back_populates="customer")
    assigned_user = relationship("User", foreign_keys=[assigned_to])

    @property
    def full_name(self) -> str:
        if self.company_name and self.type == CustomerType.COMPANY:
            return f"{self.company_name} ({self.first_name} {self.last_name})"
        return f"{self.first_name} {self.last_name}"

    @property
    def total_opportunities_value(self) -> float:
        return sum(
            opp.amount for opp in self.opportunities
            if opp.status == OpportunityStatus.OPEN
        )
```

### 2.2 Modèle Opportunité

```python
# plugins/erp_crm/models/opportunity.py
from datetime import datetime, date
from typing import Optional

from sqlalchemy import Column, Integer, String, Text, DateTime, Date, ForeignKey, Enum, Numeric
from sqlalchemy.orm import relationship
from database import Base
import enum


class OpportunityStatus(str, enum.Enum):
    PROSPECT = "prospect"
    QUALIFIED = "qualified"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"


class OpportunityPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Opportunity(Base):
    __tablename__ = "crm_opportunities"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("erp_companies.id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("crm_customers.id"), nullable=False)

    # Détails de l'opportunité
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(OpportunityStatus), default=OpportunityStatus.PROSPECT)
    priority = Column(Enum(OpportunityPriority), default=OpportunityPriority.MEDIUM)

    # Valeur et dates
    amount = Column(Numeric(15, 2), default=0)
    currency = Column(String(3), default="EUR")
    expected_close_date = Column(Date, nullable=True)
    actual_close_date = Column(Date, nullable=True)

    # Probabilité et sources
    probability = Column(Integer, default=0)  # 0-100
    source = Column(String(100), nullable=True)  # Referral, Web, etc.
    campaign = Column(String(255), nullable=True)

    # Assignation
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"))

    # Relations
    customer = relationship("Customer", back_populates="opportunities")
    assigned_user = relationship("User", foreign_keys=[assigned_to])
    interactions = relationship("Interaction", back_populates="opportunity")

    @property
    def weighted_amount(self) -> float:
        return float(self.amount) * (self.probability / 100)

    @property
    def is_closed(self) -> bool:
        return self.status in [OpportunityStatus.CLOSED_WON, OpportunityStatus.CLOSED_LOST]

    @property
    def days_since_creation(self) -> int:
        return (datetime.utcnow() - self.created_at).days
```

### 2.3 Modèle Interaction

```python
# plugins/erp_crm/models/interaction.py
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from database import Base
import enum


class InteractionType(str, enum.Enum):
    EMAIL = "email"
    PHONE = "phone"
    MEETING = "meeting"
    NOTE = "note"
    TASK = "task"


class Interaction(Base):
    __tablename__ = "crm_interactions"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("erp_companies.id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("crm_customers.id"), nullable=False)
    opportunity_id = Column(Integer, ForeignKey("crm_opportunities.id"), nullable=True)

    # Détails
    type = Column(Enum(InteractionType), nullable=False)
    subject = Column(String(255), nullable=False)
    content = Column(Text, nullable=True)

    # Participants
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(50), nullable=True)

    # Dates
    scheduled_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_minutes = Column(Integer, nullable=True)

    # Suivi
    follow_up_required = Column(Integer, ForeignKey("crm_interactions.id"), nullable=True)
    is_completed = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"))

    # Relations
    customer = relationship("Customer", back_populates="interactions")
    opportunity = relationship("Opportunity", back_populates="interactions")
```

## Partie 3 : Schémas Pydantic

```python
# plugins/erp_crm/schemas.py
from datetime import datetime, date
from typing import Optional, List
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field


# ========== Customer Schemas ==========

class CustomerBase(BaseModel):
    type: str = "individual"
    company_name: Optional[str] = None
    first_name: str
    last_name: str
    email: EmailStr
    phone: Optional[str] = None
    mobile: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    country: str = "France"
    notes: Optional[str] = None


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    type: Optional[str] = None
    status: Optional[str] = None
    company_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    notes: Optional[str] = None
    assigned_to: Optional[int] = None


class CustomerResponse(CustomerBase):
    id: int
    status: str
    full_name: str
    total_opportunities_value: float
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CustomerList(BaseModel):
    total: int
    items: List[CustomerResponse]


# ========== Opportunity Schemas ==========

class OpportunityBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = None
    amount: Decimal = Field(default=0, ge=0)
    currency: str = "EUR"
    expected_close_date: Optional[date] = None
    probability: int = Field(default=0, ge=0, le=100)
    source: Optional[str] = None
    priority: str = "medium"


class OpportunityCreate(OpportunityBase):
    customer_id: int


class OpportunityUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    amount: Optional[Decimal] = None
    probability: Optional[int] = None
    expected_close_date: Optional[date] = None
    assigned_to: Optional[int] = None


class OpportunityResponse(OpportunityBase):
    id: int
    customer_id: int
    status: str
    weighted_amount: float
    is_closed: bool
    days_since_creation: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    customer: Optional[CustomerResponse] = None

    class Config:
        from_attributes = True


class OpportunityList(BaseModel):
    total: int
    items: List[OpportunityResponse]


# ========== Dashboard Schemas ==========

class DashboardStats(BaseModel):
    total_customers: int
    active_customers: int
    total_opportunities: int
    open_opportunities: int
    total_pipeline_value: float
    weighted_pipeline_value: float
    won_opportunities_this_month: int
    won_value_this_month: float


class PipelineStage(BaseModel):
    stage: str
    count: int
    value: float


class PipelineResponse(BaseModel):
    stages: List[PipelineStage]
    total: float
```

## Partie 4 : Service Layer

```python
# plugins/erp_crm/services/customer_service.py
from typing import Optional, List
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.customer import Customer, CustomerStatus, CustomerType
from ..schemas import CustomerCreate, CustomerUpdate


class CustomerService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, company_id: int, data: CustomerCreate, created_by: int) -> Customer:
        customer = Customer(
            company_id=company_id,
            created_by=created_by,
            **data.dict()
        )
        self.db.add(customer)
        await self.db.commit()
        await self.db.refresh(customer)
        return customer

    async def get_by_id(self, company_id: int, customer_id: int) -> Optional[Customer]:
        result = await self.db.execute(
            select(Customer)
            .where(and_(Customer.id == customer_id, Customer.company_id == company_id))
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, company_id: int, email: str) -> Optional[Customer]:
        result = await self.db.execute(
            select(Customer)
            .where(and_(Customer.email == email, Customer.company_id == company_id))
        )
        return result.scalar_one_or_none()

    async def list_customers(
        self,
        company_id: int,
        skip: int = 0,
        limit: int = 20,
        search: Optional[str] = None,
        status: Optional[str] = None,
        assigned_to: Optional[int] = None
    ) -> tuple[List[Customer], int]:
        query = select(Customer).where(Customer.company_id == company_id)
        count_query = select(func.count(Customer.id)).where(Customer.company_id == company_id)

        # Filtres
        if status:
            query = query.where(Customer.status == status)
            count_query = count_query.where(Customer.status == status)

        if assigned_to:
            query = query.where(Customer.assigned_to == assigned_to)
            count_query = count_query.where(Customer.assigned_to == assigned_to)

        if search:
            search_filter = or_(
                Customer.first_name.ilike(f"%{search}%"),
                Customer.last_name.ilike(f"%{search}%"),
                Customer.email.ilike(f"%{search}%"),
                Customer.company_name.ilike(f"%{search}%")
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        # Pagination
        query = query.offset(skip).limit(limit).order_by(Customer.created_at.desc())

        result = await self.db.execute(query)
        count_result = await self.db.execute(count_query)

        return result.scalars().all(), count_result.scalar()

    async def update(self, customer: Customer, data: CustomerUpdate) -> Customer:
        update_data = data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(customer, field, value)

        await self.db.commit()
        await self.db.refresh(customer)
        return customer

    async def delete(self, customer: Customer) -> bool:
        await self.db.delete(customer)
        await self.db.commit()
        return True

    async def get_statistics(self, company_id: int) -> dict:
        # Statistiques clients
        total = await self.db.execute(
            select(func.count(Customer.id)).where(Customer.company_id == company_id)
        )

        active = await self.db.execute(
            select(func.count(Customer.id))
            .where(and_(Customer.company_id == company_id, Customer.status == CustomerStatus.ACTIVE))
        )

        return {
            "total_customers": total.scalar(),
            "active_customers": active.scalar(),
        }
```

## Partie 5 : Routes API

```python
# plugins/erp_crm/routes/customers.py
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from auth.routes import get_current_user, get_current_company
from auth.models import User
from admin.models import Company

from ..models.customer import Customer
from ..schemas import CustomerCreate, CustomerUpdate, CustomerResponse, CustomerList
from ..services.customer_service import CustomerService


router = APIRouter(prefix="/customers", tags=["CRM - Customers"])


@router.get("/", response_model=CustomerList)
async def list_customers(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_company: Company = Depends(get_current_company)
):
    """Lister tous les clients avec pagination et filtres."""
    service = CustomerService(db)
    customers, total = await service.list_customers(
        company_id=current_company.id,
        skip=skip,
        limit=limit,
        search=search,
        status=status
    )

    return CustomerList(total=total, items=customers)


@router.post("/", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    customer_data: CustomerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_company: Company = Depends(get_current_company)
):
    """Créer un nouveau client."""
    service = CustomerService(db)

    # Vérifier si l'email existe déjà
    existing = await service.get_by_email(current_company.id, customer_data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un client avec cet email existe déjà"
        )

    customer = await service.create(
        company_id=current_company.id,
        data=customer_data,
        created_by=current_user.id
    )

    return customer


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_company: Company = Depends(get_current_company)
):
    """Récupérer un client par ID."""
    service = CustomerService(db)
    customer = await service.get_by_id(current_company.id, customer_id)

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client non trouvé"
        )

    return customer


@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: int,
    customer_data: CustomerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_company: Company = Depends(get_current_company)
):
    """Mettre à jour un client."""
    service = CustomerService(db)
    customer = await service.get_by_id(current_company.id, customer_id)

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client non trouvé"
        )

    # Vérifier l'email unique si modifié
    if customer_data.email and customer_data.email != customer.email:
        existing = await service.get_by_email(current_company.id, customer_data.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cet email est déjà utilisé"
            )

    updated_customer = await service.update(customer, customer_data)
    return updated_customer


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(
    customer_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_company: Company = Depends(get_current_company)
):
    """Supprimer un client."""
    service = CustomerService(db)
    customer = await service.get_by_id(current_company.id, customer_id)

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client non trouvé"
        )

    await service.delete(customer)
    return None
```

### Route Dashboard

```python
# plugins/erp_crm/routes/dashboard.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from auth.routes import get_current_user, get_current_company
from auth.models import User
from admin.models import Company

from ..schemas import DashboardStats, PipelineResponse, PipelineStage
from ..services.dashboard_service import DashboardService


router = APIRouter(prefix="/dashboard", tags=["CRM - Dashboard"])


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_company: Company = Depends(get_current_company)
):
    """Récupérer les statistiques du tableau de bord CRM."""
    service = DashboardService(db)
    stats = await service.get_stats(current_company.id)
    return stats


@router.get("/pipeline", response_model=PipelineResponse)
async def get_sales_pipeline(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_company: Company = Depends(get_current_company)
):
    """Récupérer le pipeline de ventes."""
    service = DashboardService(db)
    pipeline = await service.get_pipeline(current_company.id)
    return pipeline
```

## Partie 6 : Point d'Entrée Principal

```python
# plugins/erp_crm/run.py
"""Point d'entrée du plugin CRM."""
from fastapi import APIRouter

from .routes import customers, opportunities, interactions, dashboard

PLUGIN_INFO = {
    "name": "erp_crm",
    "version": "1.0.0",
    "author": "Votre Équipe",
    "description": "Module CRM complet pour xcore",
    "api_prefix": "/erp/crm",
    "tags": ["crm", "customers", "opportunities"],
}

# Créer le router principal
router = APIRouter(prefix="/erp/crm", tags=["CRM"])

# Inclure les sous-routers
router.include_router(customers.router)
router.include_router(opportunities.router)
router.include_router(interactions.router)
router.include_router(dashboard.router)


# Hooks pour initialisation
async def on_plugin_load():
    """Appelé lors du chargement du plugin."""
    print("✅ Plugin CRM chargé avec succès")


async def on_plugin_unload():
    """Appelé lors du déchargement du plugin."""
    print("⏏️ Plugin CRM déchargé")
```

```python
# plugins/erp_crm/__init__.py
"""Plugin ERP CRM pour xcore."""
from .run import router, PLUGIN_INFO, on_plugin_load, on_plugin_unload

__all__ = ["router", "PLUGIN_INFO", "on_plugin_load", "on_plugin_unload"]
```

## Partie 7 : Migrations

Créez une migration Alembic pour les tables CRM :

```python
# alembic/versions/xxx_add_crm_tables.py
"""Add CRM tables

Revision ID: xxx
Revises: yyy
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import Enum

# revision identifiers
revision = 'xxx'
down_revision = 'yyy'
branch_labels = None
depends_on = None


def upgrade():
    # Créer les tables CRM
    op.create_table(
        'crm_customers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('company_name', sa.String(255), nullable=True),
        sa.Column('siret', sa.String(14), nullable=True),
        sa.Column('vat_number', sa.String(50), nullable=True),
        sa.Column('first_name', sa.String(100), nullable=False),
        sa.Column('last_name', sa.String(100), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('mobile', sa.String(50), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('postal_code', sa.String(20), nullable=True),
        sa.Column('country', sa.String(100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('assigned_to', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    op.create_index('ix_crm_customers_id', 'crm_customers', ['id'])

    op.create_table(
        'crm_opportunities',
        # ... colonnes
    )

    op.create_table(
        'crm_interactions',
        # ... colonnes
    )


def downgrade():
    op.drop_table('crm_interactions')
    op.drop_table('crm_opportunities')
    op.drop_table('crm_customers')
```

## Partie 8 : Tests

```python
# tests/test_crm_plugin.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from main import app


@pytest.mark.asyncio
async def test_create_customer(client: TestClient, db: AsyncSession):
    """Test création d'un client."""
    response = client.post(
        "/erp/crm/customers/",
        json={
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "type": "individual"
        },
        headers={"Authorization": "Bearer test_token"}
    )

    assert response.status_code == 201
    data = response.json()
    assert data["first_name"] == "John"
    assert data["email"] == "john.doe@example.com"


@pytest.mark.asyncio
async def test_list_customers(client: TestClient):
    """Test listing des clients."""
    response = client.get(
        "/erp/crm/customers/",
        headers={"Authorization": "Bearer test_token"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "items" in data
```

## Résumé

Vous avez maintenant un plugin CRM complet avec :

- ✅ Modèles de données relationnels
- ✅ Services métier séparés
- ✅ API REST avec validation
- ✅ Authentification et autorisation
- ✅ Statistiques et dashboard
- ✅ Migrations de base de données
- ✅ Tests

### Prochaines Étapes

1. **Ajouter des webhooks** pour notifier les changements
2. **Implémenter le cache** Redis pour les requêtes fréquentes
3. **Créer des templates** pour l'interface utilisateur
4. **Ajouter des exports** CSV/Excel
5. **Intégrer des emails** pour les notifications

### Ressources

- [Plugin Development Guide](../plugins.md)
- [Database Migrations](../database.md)
- [API Endpoints Reference](../api/endpoints.md)
