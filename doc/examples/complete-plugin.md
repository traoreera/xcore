# Exemple de Plugin Complet

Cet exemple présente un plugin de gestion d'utilisateurs complet, illustrant une architecture propre (Modèles, Services, Routes) et l'utilisation intensive des services XCore (DB, Cache).

## Structure du Plugin

```text
plugins/users/
├── plugin.yaml
└── src/
    ├── __init__.py
    ├── main.py          # Point d'entrée
    ├── models.py        # Modèles Pydantic & SQLAlchemy
    ├── services.py      # Logique métier
    └── repository.py    # Accès aux données (SDK Repository)
```

## `plugin.yaml`

```yaml
name: users
version: 2.0.0
author: XCore Team
description: Gestion complète des utilisateurs avec SQL et Cache

execution_mode: trusted
framework_version: ">=2.0"
entry_point: src/main.py

permissions:
  - resource: "db.*"
    actions: ["read", "write"]
    effect: allow
  - resource: "cache.*"
    actions: ["read", "write"]
    effect: allow

env:
  TOKEN_EXPIRY: "3600"
```

## `src/repository.py`

Utilisation du `BaseSyncRepository` du SDK pour l'abstraction SQL.

```python
from xcore.sdk import BaseSyncRepository
from .models import UserORM

class UserRepository(BaseSyncRepository[UserORM]):
    def find_by_email(self, email: str):
        """Recherche personnalisée par email."""
        return self.session.query(self.model).filter_by(email=email).first()
```

## `src/main.py`

```python
from xcore.sdk import (
    TrustedBase,
    RoutedPlugin,
    AutoDispatchMixin,
    action,
    route,
    validate_payload,
    ok,
    error
)
from .services import UserService
from .models import UserCreate # Modèle Pydantic

class Plugin(RoutedPlugin, AutoDispatchMixin, TrustedBase):
    """Plugin de gestion utilisateur haute performance."""

    async def on_load(self):
        # Initialisation des services Core
        self.db = self.get_service("db")
        self.cache = self.get_service("cache")

        # Injection dans la couche de service métier
        self.user_service = UserService(self.db, self.cache, self.ctx.env)
        print("✅ Users plugin prêt")

    # --- Actions IPC ---

    @action("create")
    @validate_payload(UserCreate)
    async def create_user(self, data: UserCreate):
        """Action IPC pour créer un utilisateur (validée par Pydantic)."""
        try:
            user = await self.user_service.register(data)
            return ok(user_id=user.id)
        except Exception as e:
            return error(str(e), code="registration_failed")

    @action("get")
    async def get_user(self, payload: dict):
        user_id = payload.get("user_id")
        user = await self.user_service.get_by_id(user_id)
        return ok(user=user) if user else error("Pas trouvé", code="not_found")

    # --- Routes HTTP ---

    @route("/me", method="GET", tags=["auth"])
    async def get_me(self):
        """Endpoint HTTP avec instrumentation de tracing."""
        with self.ctx.tracer.span("api.get_me") as span:
            # Simule l'utilisateur courant (Alice)
            span.set_attribute("user", "alice")
            return {"user": "alice", "status": "active"}

    @route("/", method="GET")
    async def list_users(self, page: int = 1):
        """Liste paginée avec mise en cache."""
        return await self.user_service.list_paginated(page)
```

## Points clés démontrés

1.  **Repository Pattern** : Abstraction propre de la base de données SQLAlchemy via le SDK.
2.  **Validation Pydantic** : Utilisation de `@validate_payload` pour sécuriser et typer les entrées.
3.  **Tracing & Observabilité** : Instrumentation manuelle via `self.ctx.tracer` et les spans.
4.  **Modularité** : Séparation claire entre transport (main.py), logique (services.py) et données (repository.py).
5.  **Gestion des Erreurs** : Utilisation systématique de `ok()` et `error()` pour l'IPC.
