# SDK Reference

Le SDK XCore fournit tous les outils nécessaires pour créer des plugins puissants et maintenables.

## Vue d'ensemble

```python
from xcore.sdk import (
    TrustedBase,      # Classe de base pour les plugins
    ok, error,        # Helpers de réponse
    action,           # Décorateur d'action IPC
    route,            # Décorateur de route HTTP
    RoutedPlugin,     # Mixin pour routes auto
    AutoDispatchMixin, # Mixin pour dispatch auto
    require_service,  # Décorateur de dépendance
    validate_payload, # Validation Pydantic
    PluginManifest,   # Configuration du plugin
    BaseSyncRepository,   # Repository SQL sync
    BaseAsyncRepository,  # Repository SQL async
)
```

## TrustedBase

Classe de base pour créer des plugins XCore.

### Cycle de vie

```python
from xcore.sdk import TrustedBase, ok


class Plugin(TrustedBase):
    """Plugin exemple montrant le cycle de vie."""

    async def on_load(self) -> None:
        """
        Appelé au chargement du plugin.
        Initialisez vos services et ressources ici.
        """
        # Accès aux services
        self.db = self.get_service("db")
        self.cache = self.get_service("cache")

        # Initialisation
        self.initialized = True
        print(f"Plugin {self.ctx.name} chargé")

    async def on_unload(self) -> None:
        """
        Appelé au déchargement du plugin.
        Nettoyez vos ressources ici.
        """
        # Cleanup
        self.initialized = False
        print(f"Plugin {self.ctx.name} déchargé")

    async def on_reload(self) -> None:
        """
        Appelé lors du rechargement à chaud.
        """
        print(f"Plugin {self.ctx.name} rechargé")

    async def handle(self, action: str, payload: dict) -> dict:
        """
        Point d'entrée pour les actions IPC.
        Obligatoire - doit être implémenté.
        """
        return ok(message=f"Action {action} reçue")
```

### Accès aux services

```python
class Plugin(TrustedBase):

    async def on_load(self) -> None:
        # Récupérer un service par nom
        self.db = self.get_service("db")
        self.cache = self.get_service("cache")
        self.scheduler = self.get_service("scheduler")

        # Accès aux extensions personnalisées
        self.email = self.get_service("ext.email")

    def get_router(self):
        """Définir des routes HTTP personnalisées."""
        from fastapi import APIRouter

        router = APIRouter(prefix="/api", tags=["mon_plugin"])

        @router.get("/status")
        async def status():
            return {"status": "running", "plugin": self.ctx.name}

        return router
```

### Contexte du plugin

```python
class Plugin(TrustedBase):

    async def on_load(self) -> None:
        # Informations sur le plugin
        print(f"Nom: {self.ctx.name}")
        print(f"Version: {self.ctx.version}")
        print(f"Mode: {self.ctx.mode}")

        # Configuration
        config = self.ctx.config  # Dict de configuration

        # Variables d'environnement
        env = self.ctx.env  # Dict des variables d'environnement

        # Services disponibles
        services = self.ctx.services  # Dict des services

        # EventBus pour la communication
        events = self.ctx.events

        # HookManager pour les hooks
        hooks = self.ctx.hooks
```

## Helpers de réponse

### Fonction `ok()`

Crée une réponse de succès standardisée.

```python
from xcore.sdk import ok

# Réponse simple
return ok()
# {"status": "ok"}

# Avec données
return ok(data={"user_id": 123, "name": "Alice"})
# {"status": "ok", "user_id": 123, "name": "Alice"}

# Avec arguments nommés
return ok(message="User created", user_id=123)
# {"status": "ok", "message": "User created", "user_id": 123}

# Combiné
return ok(data={"items": []}, count=0, page=1)
# {"status": "ok", "items": [], "count": 0, "page": 1}
```

### Fonction `error()`

Crée une réponse d'erreur standardisée.

```python
from xcore.sdk import error

# Erreur simple
return error("Something went wrong")
# {"status": "error", "msg": "Something went wrong"}

# Avec code d'erreur
return error("User not found", code="not_found")
# {"status": "error", "msg": "User not found", "code": "not_found"}

# Avec données supplémentaires
return error(
    "Validation failed",
    code="validation_error",
    details={"field": "email", "reason": "invalid_format"}
)
# {
#   "status": "error",
#   "msg": "Validation failed",
#   "code": "validation_error",
#   "details": {"field": "email", "reason": "invalid_format"}
# }
```

### Exemple complet

```python
from xcore.sdk import TrustedBase, ok, error


class UserPlugin(TrustedBase):

    async def handle(self, action: str, payload: dict) -> dict:
        if action == "get_user":
            user_id = payload.get("user_id")

            if not user_id:
                return error("user_id is required", code="missing_param")

            user = await self._fetch_user(user_id)

            if not user:
                return error(f"User {user_id} not found", code="not_found")

            return ok(user=user)

        if action == "create_user":
            try:
                user = await self._create_user(payload)
                return ok(
                    message="User created successfully",
                    user_id=user["id"]
                )
            except ValueError as e:
                return error(str(e), code="validation_error")
            except Exception as e:
                return error("Internal error", code="internal_error")

        return error(f"Unknown action: {action}", code="unknown_action")
```

## Décorateurs

### `@action()`

Marque une méthode comme handler d'action IPC. Utilisé avec `AutoDispatchMixin`.

```python
from xcore.sdk import AutoDispatchMixin, action, ok, error


class Plugin(AutoDispatchMixin, TrustedBase):
    """Plugin avec dispatch automatique des actions."""

    @action("greet")
    async def greet(self, payload: dict) -> dict:
        """Handler pour l'action 'greet'."""
        name = payload.get("name", "world")
        return ok(message=f"Hello {name}!")

    @action("calculate")
    async def calculate(self, payload: dict) -> dict:
        """Handler pour l'action 'calculate'."""
        try:
            a = payload["a"]
            b = payload["b"]
            op = payload.get("op", "add")

            if op == "add":
                result = a + b
            elif op == "multiply":
                result = a * b
            else:
                return error(f"Unknown operation: {op}")

            return ok(result=result)
        except KeyError as e:
            return error(f"Missing parameter: {e}", code="missing_param")

    # Plus besoin d'implémenter handle() - géré automatiquement
```

### `@route()`

Déclare une route HTTP FastAPI directement sur la méthode. Utilisé avec `RoutedPlugin`.

```python
from xcore.sdk import RoutedPlugin, route


class Plugin(RoutedPlugin, TrustedBase):
    """Plugin avec routes HTTP automatiques."""

    @route("/items", method="GET", tags=["items"])
    async def list_items(self):
        """Liste tous les items."""
        return [{"id": 1, "name": "foo"}, {"id": 2, "name": "bar"}]

    @route("/items/{item_id}", method="GET", tags=["items"])
    async def get_item(self, item_id: int):
        """Récupère un item par ID."""
        return {"id": item_id, "name": f"Item {item_id}"}

    @route("/items", method="POST", tags=["items"], status_code=201)
    async def create_item(self, body: dict):
        """Crée un nouvel item."""
        return {"id": 3, "created": True, "data": body}

    @route("/items/{item_id}", method="PUT", tags=["items"])
    async def update_item(self, item_id: int, body: dict):
        """Met à jour un item."""
        return {"id": item_id, "updated": True, "data": body}

    @route("/items/{item_id}", method="DELETE", tags=["items"])
    async def delete_item(self, item_id: int):
        """Supprime un item."""
        return {"id": item_id, "deleted": True}
```

Paramètres de `@route()`:

| Paramètre | Type | Description |
|-----------|------|-------------|
| `path` | str | Chemin de la route |
| `method` | str | Méthode HTTP (GET, POST, PUT, DELETE...) |
| `tags` | list[str] | Tags pour la documentation OpenAPI |
| `summary` | str | Résumé de la route |
| `status_code` | int | Code de statut HTTP par défaut |
| `response_model` | Type | Modèle Pydantic de réponse |

### `@require_service()`

Vérifie que les services requis sont disponibles avant d'exécuter la méthode.

```python
from xcore.sdk import require_service, ok, error


class Plugin(TrustedBase):

    @require_service("db")
    async def handle(self, action: str, payload: dict) -> dict:
        """Cette méthode nécessite le service 'db'."""
        db = self.get_service("db")
        # Le décorateur lève KeyError si 'db' est indisponible
        # avant même d'entrer dans la méthode
        ...

    @require_service("cache", "db")
    async def complex_operation(self, payload: dict) -> dict:
        """Cette méthode nécessite 'cache' ET 'db'."""
        cache = self.get_service("cache")
        db = self.get_service("db")
        ...
```

### `@validate_payload()`

Valide le payload avec un modèle Pydantic.

```python
from pydantic import BaseModel, Field
from xcore.sdk import validate_payload, ok, error


class CreateUserPayload(BaseModel):
    """Modèle de validation pour la création d'utilisateur."""
    name: str = Field(..., min_length=2, max_length=50)
    email: str = Field(..., regex=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    age: int = Field(..., ge=0, le=150)


class UpdateUserPayload(BaseModel):
    """Modèle pour la mise à jour (tous les champs optionnels)."""
    name: str | None = Field(None, min_length=2, max_length=50)
    email: str | None = Field(None, regex=r"^[\w\.-]+@[\w\.-]+\.\w+$")


class Plugin(TrustedBase):

    @validate_payload(CreateUserPayload)
    async def create_user(self, validated: CreateUserPayload) -> dict:
        """Crée un utilisateur avec validation automatique."""
        # validated est une instance de CreateUserPayload
        user = await self._save_user(
            name=validated.name,
            email=validated.email,
            age=validated.age
        )
        return ok(user_id=user["id"])

    @validate_payload(UpdateUserPayload)
    async def update_user(self, validated: UpdateUserPayload) -> dict:
        """Met à jour un utilisateur."""
        data = validated.model_dump(exclude_unset=True)
        user = await self._update_user(data)
        return ok(updated=True)

    async def handle(self, action: str, payload: dict) -> dict:
        if action == "create_user":
            return await self.create_user(payload)
        if action == "update_user":
            return await self.update_user(payload)
        return error("Unknown action")
```

### `@trusted()` et `@sandboxed()`

Marquent une méthode comme compatible avec un mode d'exécution spécifique.

```python
from xcore.sdk import trusted, sandboxed, ok


class Plugin(TrustedBase):

    @trusted
    async def sensitive_operation(self, payload: dict) -> dict:
        """Cette méthode ne fonctionne qu'en mode Trusted."""
        # Accès aux services sensibles
        db = self.get_service("db")
        ...
        return ok()

    @sandboxed
    async def safe_operation(self, payload: dict) -> dict:
        """Cette méthode est compatible mode Sandboxed."""
        # Ne pas accéder aux services sensibles
        return ok()
```

## Mixins

### `AutoDispatchMixin`

Génère automatiquement la méthode `handle()` à partir des méthodes `@action`.

```python
from xcore.sdk import AutoDispatchMixin, action, TrustedBase, ok


class Plugin(AutoDispatchMixin, TrustedBase):
    """
    Les méthodes décorées avec @action sont automatiquement
    dispatchées par handle().
    """

    @action("add")
    async def add_numbers(self, payload: dict) -> dict:
        result = payload["a"] + payload["b"]
        return ok(result=result)

    @action("multiply")
    async def multiply_numbers(self, payload: dict) -> dict:
        result = payload["a"] * payload["b"]
        return ok(result=result)

    @action("status")
    async def get_status(self, payload: dict) -> dict:
        return ok(
            loaded=True,
            version=self.ctx.version
        )

# Appels:
# handle("add", {"a": 5, "b": 3}) -> {"status": "ok", "result": 8}
# handle("multiply", {"a": 4, "b": 7}) -> {"status": "ok", "result": 28}
# handle("status", {}) -> {"status": "ok", "loaded": True, "version": "1.0.0"}
# handle("unknown", {}) -> {"status": "error", ...}
```

### `RoutedPlugin`

Génère automatiquement `get_router()` à partir des méthodes `@route`.

```python
from xcore.sdk import RoutedPlugin, route, TrustedBase


class Plugin(RoutedPlugin, TrustedBase):
    """
    Les méthodes décorées avec @route sont automatiquement
    montées sur l'application FastAPI.
    """

    @route("/health", method="GET")
    async def health_check(self):
        return {"status": "healthy"}

    @route("/config", method="GET")
    async def get_config(self):
        return {"config": self.ctx.config}

# Les routes sont disponibles sur:
# GET /plugins/<plugin_name>/health
# GET /plugins/<plugin_name>/config
```

### Combinaison des mixins

```python
from xcore.sdk import (
    RoutedPlugin,
    AutoDispatchMixin,
    TrustedBase,
    action,
    route,
    ok
)


class CompletePlugin(RoutedPlugin, AutoDispatchMixin, TrustedBase):
    """Plugin avec à la fois routes HTTP et dispatch d'actions."""

    # --- Actions IPC ---

    @action("process")
    async def process_action(self, payload: dict) -> dict:
        result = await self._process(payload)
        return ok(result=result)

    @action("validate")
    async def validate_action(self, payload: dict) -> dict:
        is_valid = await self._validate(payload)
        return ok(valid=is_valid)

    # --- Routes HTTP ---

    @route("/process", method="POST")
    async def process_http(self, body: dict):
        result = await self._process(body)
        return {"result": result}

    @route("/validate", method="POST")
    async def validate_http(self, body: dict):
        is_valid = await self._validate(body)
        return {"valid": is_valid}
```

## PluginManifest

Configuration typée du manifeste plugin.

```python
from xcore.sdk import PluginManifest, ResourceConfig, RuntimeConfig
from pathlib import Path

# Création d'un manifeste
manifest = PluginManifest(
    name="mon_plugin",
    version="1.0.0",
    plugin_dir=Path("/path/to/plugin"),
    author="John Doe",
    description="Un plugin exemple",
    entry_point="src/main.py",
    resources=ResourceConfig(
        timeout_seconds=30,
        max_memory_mb=256,
        max_disk_mb=100
    ),
    runtime=RuntimeConfig(
        health_check=HealthCheckConfig(
            enabled=True,
            interval_seconds=30
        ),
        retry=RetryConfig(
            max_attempts=3,
            backoff_seconds=1.0
        )
    )
)

# Champs disponibles
print(manifest.name)          # "mon_plugin"
print(manifest.version)     # "1.0.0"
print(manifest.author)      # "John Doe"
print(manifest.resources.timeout_seconds)  # 30
```

### Configuration du manifeste YAML

```yaml
# plugin.yaml
name: mon_plugin
version: 1.0.0
author: John Doe
description: Un plugin exemple

execution_mode: trusted
framework_version: ">=2.0"
entry_point: src/main.py

# Permissions
permissions:
  - resource: "cache.*"
    actions: ["read", "write"]
    effect: allow

# Ressources
resources:
  timeout_seconds: 30
  max_memory_mb: 256
  max_disk_mb: 100
  rate_limit:
    calls: 1000
    period_seconds: 60

# Runtime
runtime:
  health_check:
    enabled: true
    interval_seconds: 30
    timeout_seconds: 5
  retry:
    max_attempts: 3
    backoff_seconds: 1.0

# Filesystem
filesystem:
  allowed_paths:
    - "data/"
    - "logs/"
  denied_paths:
    - "src/"
    - "../"

# Configuration supplémentaire (extra)
api_key: "${API_KEY}"
webhook_url: "${WEBHOOK_URL}"
```

## Repositories SQL

### `BaseSyncRepository`

Repository CRUD pour SQLAlchemy synchrone.

```python
from xcore.sdk import BaseSyncRepository
from sqlalchemy.orm import declarative_base, Session
from sqlalchemy import Column, String, Integer

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True)
    age = Column(Integer)


class UserRepository(BaseSyncRepository[User]):
    """Repository pour les utilisateurs."""

    def find_by_email(self, email: str) -> User | None:
        """Recherche par email."""
        from sqlalchemy import select
        stmt = select(User).where(User.email == email)
        result = self.session.execute(stmt)
        return result.scalar_one_or_none()

    def search_by_name(self, name_pattern: str) -> list[User]:
        """Recherche par pattern de nom."""
        from sqlalchemy import select
        stmt = select(User).where(User.name.ilike(f"%{name_pattern}%"))
        result = self.session.execute(stmt)
        return result.scalars().all()


# Utilisation dans un plugin
class Plugin(TrustedBase):

    async def on_load(self) -> None:
        self.db = self.get_service("db")

    def create_user(self, data: dict) -> dict:
        with self.db.session() as session:
            repo = UserRepository(User, session)

            # Vérifier si l'email existe déjà
            existing = repo.find_by_email(data["email"])
            if existing:
                return error("Email already exists", code="duplicate")

            # Créer l'utilisateur
            user = User(
                id=str(uuid.uuid4()),
                name=data["name"],
                email=data["email"],
                age=data.get("age")
            )
            created = repo.create(user)

            return ok(user_id=created.id)

    def get_user(self, user_id: str) -> dict:
        with self.db.session() as session:
            repo = UserRepository(User, session)
            user = repo.get_by_id(user_id)

            if not user:
                return error("User not found", code="not_found")

            return ok(
                id=user.id,
                name=user.name,
                email=user.email
            )

    def list_users(self) -> dict:
        with self.db.session() as session:
            repo = UserRepository(User, session)
            users = repo.get_all()

            return ok(users=[
                {"id": u.id, "name": u.name, "email": u.email}
                for u in users
            ])

    def update_user(self, user_id: str, data: dict) -> dict:
        with self.db.session() as session:
            repo = UserRepository(User, session)
            updated = repo.update(user_id, data)

            if not updated:
                return error("User not found", code="not_found")

            return ok(updated=True)

    def delete_user(self, user_id: str) -> dict:
        with self.db.session() as session:
            repo = UserRepository(User, session)
            deleted = repo.delete(user_id)

            if not deleted:
                return error("User not found", code="not_found")

            return ok(deleted=True)
```

### `BaseAsyncRepository`

Repository CRUD pour SQLAlchemy asynchrone.

```python
from xcore.sdk import BaseAsyncRepository
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, Integer

Base = declarative_base()


class Product(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    price = Column(Integer)
    stock = Column(Integer)


class ProductRepository(BaseAsyncRepository[Product]):
    """Repository asynchrone pour les produits."""

    async def find_by_name(self, name: str) -> Product | None:
        from sqlalchemy import select
        stmt = select(Product).where(Product.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_in_stock(self) -> list[Product]:
        from sqlalchemy import select
        stmt = select(Product).where(Product.stock > 0)
        result = await self.session.execute(stmt)
        return result.scalars().all()


# Utilisation dans un plugin
class Plugin(TrustedBase):

    async def on_load(self) -> None:
        self.db = self.get_service("db")  # Connexion async

    async def create_product(self, data: dict) -> dict:
        async with self.db.connection() as conn:
            repo = ProductRepository(Product, conn)

            product = Product(
                id=str(uuid.uuid4()),
                name=data["name"],
                price=data["price"],
                stock=data.get("stock", 0)
            )
            created = await repo.create(product)

            return ok(product_id=created.id)

    async def get_product(self, product_id: str) -> dict:
        async with self.db.connection() as conn:
            repo = ProductRepository(Product, conn)
            product = await repo.get_by_id(product_id)

            if not product:
                return error("Product not found", code="not_found")

            return ok(
                id=product.id,
                name=product.name,
                price=product.price,
                stock=product.stock
            )

    async def list_products(self) -> dict:
        async with self.db.connection() as conn:
            repo = ProductRepository(Product, conn)
            products = await repo.get_all()

            return ok(products=[
                {"id": p.id, "name": p.name, "price": p.price}
                for p in products
            ])
```

## Exemples complets

### Plugin avec validation et routes

```python
from pydantic import BaseModel, Field, validator
from xcore.sdk import (
    TrustedBase,
    RoutedPlugin,
    AutoDispatchMixin,
    action,
    route,
    validate_payload,
    require_service,
    ok,
    error
)


class CreateOrderPayload(BaseModel):
    """Payload pour créer une commande."""
    customer_id: str = Field(..., min_length=1)
    items: list[dict] = Field(..., min_items=1)
    total: float = Field(..., gt=0)

    @validator("items")
    def validate_items(cls, v):
        for item in v:
            if "product_id" not in item or "quantity" not in item:
                raise ValueError("Each item must have product_id and quantity")
            if item["quantity"] <= 0:
                raise ValueError("Quantity must be positive")
        return v


class OrderPlugin(RoutedPlugin, AutoDispatchMixin, TrustedBase):
    """Plugin complet de gestion des commandes."""

    async def on_load(self) -> None:
        self.db = self.get_service("db")
        self.cache = self.get_service("cache")

    # --- Actions IPC ---

    @action("create_order")
    @validate_payload(CreateOrderPayload)
    @require_service("db")
    async def create_order_ipc(self, payload: CreateOrderPayload) -> dict:
        order_id = await self._create_order(payload)
        return ok(order_id=order_id)

    @action("get_order")
    @require_service("db")
    async def get_order_ipc(self, payload: dict) -> dict:
        order = await self._get_order(payload.get("order_id"))
        if not order:
            return error("Order not found", code="not_found")
        return ok(order=order)

    # --- Routes HTTP ---

    @route("/orders", method="POST", tags=["orders"], status_code=201)
    @validate_payload(CreateOrderPayload)
    async def create_order_http(self, body: CreateOrderPayload):
        order_id = await self._create_order(body)
        return {"order_id": order_id, "status": "created"}

    @route("/orders/{order_id}", method="GET", tags=["orders"])
    async def get_order_http(self, order_id: str):
        order = await self._get_order(order_id)
        if not order:
            return error("Order not found", code="not_found")
        return order

    @route("/orders/{order_id}/status", method="PUT", tags=["orders"])
    async def update_status_http(self, order_id: str, body: dict):
        new_status = body.get("status")
        await self._update_order_status(order_id, new_status)
        return {"order_id": order_id, "status": new_status}

    # --- Méthodes privées ---

    async def _create_order(self, payload) -> str:
        # Logique de création
        return "order_123"

    async def _get_order(self, order_id: str) -> dict | None:
        # Logique de récupération
        return None

    async def _update_order_status(self, order_id: str, status: str):
        # Logique de mise à jour
        pass
```

### Plugin avec EventBus et Hooks

```python
from xcore.sdk import TrustedBase, action, ok


class EventDrivenPlugin(TrustedBase):
    """Plugin utilisant EventBus et Hooks."""

    async def on_load(self) -> None:
        self.events = self.ctx.events
        self.hooks = self.ctx.hooks
        self.db = self.get_service("db")

        # S'abonner aux événements système
        self.events.on("user.created", self._on_user_created)
        self.events.on("order.placed", self._on_order_placed)

        # Enregistrer des hooks
        self.hooks.on("payment.processing", self._validate_payment)

    async def on_unload(self) -> None:
        # Se désabonner
        self.events.unsubscribe("user.created", self._on_user_created)
        self.events.unsubscribe("order.placed", self._on_order_placed)

    async def _on_user_created(self, event):
        """Handler appelé quand un utilisateur est créé."""
        user_id = event.data.get("user_id")
        email = event.data.get("email")

        # Créer un profil par défaut
        await self._create_default_profile(user_id)

        # Émettre un événement de confirmation
        await self.events.emit("profile.created", {
            "user_id": user_id,
            "profile_id": "profile_123"
        })

    async def _on_order_placed(self, event):
        """Handler appelé quand une commande est passée."""
        order_id = event.data.get("order_id")

        # Vérifier le stock
        has_stock = await self._check_stock(event.data["items"])

        if not has_stock:
            event.stop()  # Arrêter la propagation
            await self.events.emit("order.rejected", {
                "order_id": order_id,
                "reason": "out_of_stock"
            })

    async def _validate_payment(self, event):
        """Hook de validation de paiement."""
        amount = event.data.get("amount")

        if amount > 10000:  # Limite de 10 000
            event.cancel()  # Annuler l'événement
            return

    @action("notify")
    async def notify_action(self, payload: dict) -> dict:
        """Action qui émet un événement."""
        await self.events.emit("notification.sent", {
            "recipient": payload["to"],
            "message": payload["message"]
        })
        return ok(sent=True)
```

## Bonnes pratiques

1. **Toujours implémenter `handle()`** sauf si vous utilisez `AutoDispatchMixin`
2. **Utiliser `ok()` et `error()`** pour des réponses standardisées
3. **Valider les entrées** avec `@validate_payload()`
4. **Vérifier les dépendances** avec `@require_service()`
5. **Nettoyer dans `on_unload()`** — se désabonner des événements, fermer les connexions
6. **Gérer les erreurs** avec try/except et retourner des messages clairs
7. **Documenter les actions** avec des docstrings

```python
class WellDesignedPlugin(TrustedBase):
    """Plugin bien conçu suivant les bonnes pratiques."""

    async def on_load(self) -> None:
        """Initialiser les ressources."""
        try:
            self.db = self.get_service("db")
            self.cache = self.get_service("cache")
            self.events = self.ctx.events

            # S'abonner aux événements
            self.events.on("system.tick", self._on_tick)

            self._initialized = True
        except Exception as e:
            self._initialized = False
            raise RuntimeError(f"Failed to initialize: {e}")

    async def on_unload(self) -> None:
        """Nettoyer les ressources."""
        # Se désabonner
        if hasattr(self, 'events'):
            self.events.unsubscribe("system.tick", self._on_tick)

        self._initialized = False

    async def handle(self, action: str, payload: dict) -> dict:
        """Handler principal avec validation."""
        if not getattr(self, '_initialized', False):
            return error("Plugin not initialized", code="not_ready")

        try:
            if action == "process":
                return await self._process(payload)
            elif action == "status":
                return await self._get_status()
            else:
                return error(f"Unknown action: {action}", code="unknown_action")
        except ValueError as e:
            return error(str(e), code="validation_error")
        except Exception as e:
            return error(f"Internal error: {e}", code="internal_error")

    async def _process(self, payload: dict) -> dict:
        """Traiter une demande avec validation."""
        if "required_field" not in payload:
            return error("Missing required_field", code="missing_param")

        # Logique métier...
        return ok(processed=True)

    async def _get_status(self) -> dict:
        """Récupérer le statut."""
        return ok(
            initialized=self._initialized,
            version=self.ctx.version
        )

    async def _on_tick(self, event):
        """Handler d'événement périodique."""
        # Traitement...
        pass
```

## Next Steps

- [Creating Plugins](../guides/creating-plugins.md) — Créer des plugins pas à pas
- [Creating Services](../guides/creating-services.md) — Créer des services personnalisés
- [Events](../guides/events.md) — Système d'événements
- [Services](../guides/services.md) — Utiliser les services
- [Monitoring](../guides/monitoring.md) — Monitorer vos plugins
