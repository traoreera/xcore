---
title: Application complète — E-commerce
description: Exemple de référence couvrant toutes les fonctionnalités xcore — plugins trusted/sandboxed, multi-tenant, observabilité, scheduler, events, auth.
icon: material/shopping
---

# Application complète — E-commerce

Cet exemple de référence illustre comment construire un backend e-commerce complet en s'appuyant sur **toutes** les fonctionnalités de xcore : plugins trusted et sandboxed, multi-tenancy, observabilité complète, scheduler distribué, bus d'événements et authentification JWT.

L'application se compose de quatre plugins :

| Plugin | Mode | Rôle |
|--------|------|------|
| `auth` | trusted | Authentification JWT, vérification de tokens |
| `shop` | trusted | Catalogue produits, gestion des commandes |
| `billing` | sandboxed | Traitement des paiements isolé |
| `tenant_manager` | trusted | Provisioning de nouveaux tenants |

---

## 1. `integration.yaml` complet

Configuration de référence pour une mise en production. Toutes les sections sont actives.

```yaml linenums="1" title="integration.yaml"
app:
  name: xcore-ecommerce
  env: production
  secret_key: "${SECRET_KEY}"  # (1)!
  debug: false

plugins:
  directory: app/plugins
  autoload: true
  order:
    - auth          # (2)!
    - shop
    - billing
    - tenant_manager

services:
  db:
    enabled: true
    adapter: postgresql
    url: "${DATABASE_URL}"
    pool_size: 10
    max_overflow: 20
    echo: false

  cache:
    enabled: true
    backend: redis
    url: "${REDIS_URL}"
    default_ttl: 300

  scheduler:
    enabled: true
    backend: redis
    url: "${REDIS_URL}"
    timezone: Europe/Paris

tenancy:
  enabled: true
  isolate_db: true       # (3)!
  isolate_cache: true
  isolate_scheduler: false

observability:
  logging:
    level: INFO
    output: json          # (4)!
    file: log/app.log
  metrics:
    backend: prometheus
    port: 9090
  tracing:
    enabled: true
    backend: opentelemetry
    service_name: xcore-ecommerce
    endpoint: otel-collector:4317
    use_grpc: true
  profiler:
    enabled: true
    sample_rate: 0.05

middleware:
  cors:
    enabled: true
    allow_origins:
      - "https://shop.example.com"
      - "https://admin.example.com"
    allow_methods: ["GET", "POST", "PUT", "DELETE"]
    allow_headers: ["Authorization", "Content-Type", "X-Tenant-ID"]
    allow_credentials: true
  rate_limit:
    enabled: true
    default_rpm: 120
```

1. La `secret_key` est lue depuis l'environnement — ne jamais la mettre en dur dans le fichier.
2. `auth` doit être chargé en premier car `shop` déclare `requires: ["auth"]`.
3. Chaque tenant obtient son propre schéma PostgreSQL — les requêtes ne se mélangent pas.
4. Sortie JSON pour une ingestion facile par Loki, Datadog ou Elasticsearch.

---

## 2. Plugin `shop` (Trusted)

Le plugin principal de l'application. Il illustre l'ensemble du SDK : décorateurs, observabilité, cache, scheduler, events et appels inter-plugins.

### `plugin.yaml`

```yaml linenums="1" title="app/plugins/shop/plugin.yaml"
name: shop
version: 1.4.0
description: Gestion du catalogue et des commandes e-commerce
execution_mode: trusted
requires:
  - auth           # (1)!
xcore_version: ">=2.3.0,<3.0"

permissions:
  - db.orders
  - db.products
  - cache.cart
  - events:order.*
  - events:product.*

resources:
  rate_limit:
    rpm: 200
    burst: 50
```

1. xcore vérifie que `auth` est chargé avant d'initialiser `shop`. Si `auth` est absent, le chargement échoue.

### `src/main.py`

```python linenums="1" title="app/plugins/shop/src/main.py"
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, Float, Integer, String, select
from sqlalchemy.orm import DeclarativeBase

from xcore import TrustedBase, error, ok
from xcore.sdk import (
    AutoDispatchMixin,
    AutoMixin,
    BaseAsyncRepository,
    EventMixin,
    HookMixin,
    ObservabilityMixin,
    ScheduledMixin,
    action,
    cached,
    counted,
    cron,
    health_check,
    interval,
    invalidate,
    on_event,
    on_hook,
    require_service,
    route,
    sandboxed,
    schema,
    timed,
    traced,
    trusted,
    validate_payload,
)
from xcore.sdk import Event, HookResult


# ── Models ────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    customer_id = Column(String(64), nullable=False)
    product_id = Column(String(64), nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String(32), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)


# ── Repository ────────────────────────────────────────────────────────────────

class OrderRepository(BaseAsyncRepository):
    """Accès aux commandes via SQLAlchemy async."""

    def __init__(self, db):
        super().__init__(db, Order)  # (1)!

    async def find_by_tenant(self, tenant_id: str) -> list[Order]:
        async with self.db.session() as session:
            result = await session.execute(
                select(Order).where(Order.tenant_id == tenant_id)
            )
            return result.scalars().all()

    async def find_pending(self) -> list[Order]:
        async with self.db.session() as session:
            result = await session.execute(
                select(Order).where(Order.status == "pending")
            )
            return result.scalars().all()


# ── Plugin ────────────────────────────────────────────────────────────────────

class Plugin(EventMixin, HookMixin, ObservabilityMixin, ScheduledMixin,
             AutoDispatchMixin, TrustedBase):
    """
    Plugin shop — gestion du catalogue et des commandes.

    Utilise AutoDispatchMixin pour le dispatch automatique des actions,
    EventMixin/HookMixin pour le bus d'événements, ObservabilityMixin pour
    les health checks et ScheduledMixin pour les tâches planifiées.
    """

    async def on_load(self):
        await super().on_load()  # (2)!

        self.db = self.get_service("db")
        self.cache = self.get_service("cache")
        self.scheduler = self.get_service("scheduler")

        self.orders = OrderRepository(self.db)

        self.logger.info(
            "plugin shop chargé",
            tenant=self.ctx.tenant_id,
            mode="trusted",
        )

    async def on_unload(self):
        await super().on_unload()
        self.logger.info("plugin shop déchargé")

    # ── Actions ───────────────────────────────────────────────────────────────

    @action("create_order")
    @schema(
        version="2.0",
        input={
            "customer_id": (str, ...),
            "product_id": (str, ...),
            "amount": (float, ...),
            "quantity": (int, 1),
        },
        output={"order_id": int, "status": str, "trace_id": str},
        description="Crée une commande et déclenche le paiement via billing",
        type_response="dict",
    )
    @trusted
    @require_service("db")
    @traced("shop.create_order")   # (3)!
    @counted("shop.orders.created")
    @timed("shop.order.duration")
    async def create_order(self, payload: dict) -> dict:
        tenant_id = self.ctx.tenant_id  # (4)!

        # Persist the order
        async with self.db.session() as session:
            order = Order(
                tenant_id=tenant_id,
                customer_id=payload["customer_id"],
                product_id=payload["product_id"],
                amount=payload["amount"] * payload["quantity"],
                status="pending",
            )
            session.add(order)
            await session.commit()
            await session.refresh(order)

        # Inter-plugin call to billing (5)
        charge_result = await self.call_plugin("billing", "charge", {
            "order_id": order.id,
            "amount": order.amount,
            "customer_id": order.customer_id,
            "__trace__": self.tracer.current_trace_id(),  # (5)!
        })

        if charge_result.get("status") == "error":
            self.logger.error(
                "échec du paiement",
                order_id=order.id,
                reason=charge_result.get("message"),
            )
            return error(charge_result.get("message", "payment failed"), "payment_failed")

        # Update status
        async with self.db.session() as session:
            await session.execute(
                Order.__table__.update()
                .where(Order.id == order.id)
                .values(status="paid")
            )
            await session.commit()

        # Emit event on the bus
        await self.ctx.events.emit("order.created", {
            "order_id": order.id,
            "tenant_id": tenant_id,
            "customer_id": order.customer_id,
            "amount": order.amount,
        })

        # Invalidate cart cache for this customer
        cache_key = f"cart:{tenant_id}:{payload['customer_id']}"
        await self.cache.delete(cache_key)

        self.logger.info(
            "commande créée",
            order_id=order.id,
            tenant=tenant_id,
            amount=order.amount,
        )
        return ok(
            order_id=order.id,
            status="paid",
            trace_id=self.tracer.current_trace_id(),
        )

    @action("get_cart")
    @sandboxed
    @require_service("cache")
    @traced("shop.get_cart")
    @cached(ttl=120, key=lambda self, p: f"cart:{self.ctx.tenant_id}:{p['customer_id']}")
    async def get_cart(self, payload: dict) -> dict:
        """Récupère le panier depuis le cache (ou reconstruit depuis la DB)."""
        customer_id = payload.get("customer_id")
        if not customer_id:
            return error("customer_id requis", "missing_field")

        async with self.db.session() as session:
            result = await session.execute(
                select(Order).where(
                    Order.customer_id == customer_id,
                    Order.tenant_id == self.ctx.tenant_id,
                    Order.status == "pending",
                )
            )
            items = result.scalars().all()

        return ok(items=[
            {"order_id": o.id, "product_id": o.product_id, "amount": o.amount}
            for o in items
        ])

    @action("list_orders")
    @validate_payload({"page": (int, 1), "per_page": (int, 20)})  # (6)!
    @traced("shop.list_orders")
    @counted("shop.orders.listed")
    async def list_orders(self, payload: dict) -> dict:
        orders = await self.orders.find_by_tenant(self.ctx.tenant_id)
        page = payload.get("page", 1)
        per_page = payload.get("per_page", 20)
        start = (page - 1) * per_page
        return ok(
            orders=[
                {
                    "id": o.id,
                    "customer_id": o.customer_id,
                    "amount": o.amount,
                    "status": o.status,
                }
                for o in orders[start : start + per_page]
            ],
            total=len(orders),
            page=page,
        )

    @action("invalidate_product_cache")
    @invalidate(key=lambda self, p: f"product:{p['product_id']}")
    async def invalidate_product_cache(self, payload: dict) -> dict:
        return ok(invalidated=payload.get("product_id"))

    # ── HTTP Routes ───────────────────────────────────────────────────────────

    @route("/orders", method="GET", tags=["shop"], summary="Lister les commandes")
    async def http_list_orders(self):
        return await self.list_orders({"page": 1, "per_page": 50})

    @route("/orders", method="POST", status_code=201, tags=["shop"],
           summary="Créer une commande", permissions=["db.orders"])
    async def http_create_order(self, body: dict):
        return await self.create_order(body)

    @route("/orders/{order_id}", method="DELETE", tags=["shop"],
           summary="Annuler une commande", permissions=["db.orders"])
    async def http_cancel_order(self, order_id: int):
        async with self.db.session() as session:
            await session.execute(
                Order.__table__.update()
                .where(Order.id == order_id)
                .values(status="cancelled")
            )
            await session.commit()
        await self.ctx.events.emit("order.cancelled", {"order_id": order_id})
        return ok(order_id=order_id, status="cancelled")

    # ── Events & Hooks ────────────────────────────────────────────────────────

    @on_event("order.created")
    async def on_order_created(self, event: Event):
        """Met à jour les métriques métier à chaque nouvelle commande."""
        self.metrics.counter(
            "shop.revenue_total",
            labels={"tenant": event.data.get("tenant_id", "unknown")},
        ).inc(event.data.get("amount", 0))
        self.logger.info(
            "événement order.created reçu",
            order_id=event.data.get("order_id"),
        )

    @on_hook("plugin.*.loaded", priority=10)
    async def on_plugin_loaded(self, event: Event) -> HookResult:
        """Log chaque plugin chargé après shop."""
        self.logger.debug("plugin chargé détecté", plugin=event.data.get("name"))
        return HookResult(proceed=True)

    # ── Scheduler ────────────────────────────────────────────────────────────

    @cron("0 2 * * *")  # (7)!
    async def nightly_order_cleanup(self):
        """Marque les commandes pending de plus de 24h comme expirées."""
        pending = await self.orders.find_pending()
        expired_count = 0
        now = datetime.utcnow()
        async with self.db.session() as session:
            for order in pending:
                age_hours = (now - order.created_at).total_seconds() / 3600
                if age_hours > 24:
                    await session.execute(
                        Order.__table__.update()
                        .where(Order.id == order.id)
                        .values(status="expired")
                    )
                    expired_count += 1
            await session.commit()

        self.logger.info("cleanup nocturne", expired=expired_count)
        self.metrics.counter("shop.orders.expired").inc(expired_count)

    @interval(seconds=60)
    async def heartbeat(self):
        """Publie une métrique de liveness toutes les 60 secondes."""
        self.metrics.gauge("shop.heartbeat").set(1)

    # ── Health checks ─────────────────────────────────────────────────────────

    @health_check("shop.internal", kind="liveness")  # (8)!
    async def check_liveness(self) -> tuple[bool, str]:
        """Vérifie l'état interne du plugin."""
        return True, "running"

    @health_check("shop.db", kind="readiness")  # (9)!
    async def check_db(self) -> tuple[bool, str]:
        """Vérifie la connexion à la base de données."""
        try:
            await self.db.execute("SELECT 1")
            return True, "ok"
        except Exception as e:
            self.logger.error("health check db échoué", erreur=str(e))
            return False, str(e)
```

1. `BaseAsyncRepository` prend le service db et la classe de modèle SQLAlchemy.
2. Chaque mixin chaîne `await super().on_load()` — l'ordre MRO garantit l'initialisation correcte.
3. `@traced` crée un span OpenTelemetry. Le `trace_id` se propage automatiquement aux appels inter-plugins via `ContextVar`.
4. `self.ctx.tenant_id` est mis à jour par le middleware de tenancy à chaque requête.
5. `__trace__` transmet le trace_id courant au plugin sandboxed qui ne peut pas lire le `ContextVar` directement.
6. `@validate_payload` valide directement sans schéma versionné — idéal pour les actions internes.
7. Exécution à 2h00 chaque nuit. Le scheduler distribué évite les doublons en multi-workers via un lock Redis.
8. `kind="liveness"` — état interne du plugin. Toujours `True` si le processus tourne.
9. `kind="readiness"` — dépendance externe. Retourne `False` si la DB est inaccessible.

---

## 3. Plugin `billing` (Sandboxed)

Le plugin de paiement s'exécute dans un subprocess isolé. Il n'a accès ni à la DB principale ni au cache — uniquement à ce qui lui est passé par IPC.

### `plugin.yaml`

```yaml linenums="1" title="app/plugins/billing/plugin.yaml"
name: billing
version: 1.1.0
description: Traitement des paiements — subprocess isolé
execution_mode: sandboxed

resources:
  max_memory_mb: 128     # (1)!
  max_disk_mb: 50
  timeout_seconds: 10
  max_cpu_percent: 50

filesystem:
  allowed_paths:
    - "/tmp/billing"     # (2)!
  denied_paths:
    - "/etc"
    - "/home"
    - "/root"

rate_limit:
  rpm: 500
  burst: 100

xcore_version: ">=2.3.0,<3.0"
```

1. Si le subprocess dépasse 128 Mo, xcore le tue et retourne une erreur `resource_limit_exceeded`.
2. Seul `/tmp/billing` est accessible en écriture — les autres chemins sont refusés par le filesystem guard.

### `src/main.py`

```python linenums="1" title="app/plugins/billing/src/main.py"
from __future__ import annotations

from xcore import TrustedBase, error, ok
from xcore.kernel.observability import get_logger

logger = get_logger("xcore.plugins.billing")


class Plugin(TrustedBase):
    """
    Plugin billing — traitement des paiements en mode sandboxed.

    Ce plugin ne peut pas appeler d'autres plugins ni accéder à la DB directement.
    Toutes les données lui sont transmises via le payload IPC.
    """

    # État interne pour le health check
    _payment_gateway_ok: bool = True
    _processed_count: int = 0

    async def on_load(self):
        self._payment_gateway_ok = True
        self._processed_count = 0
        logger.info("plugin billing chargé", mode="sandboxed")

    async def handle(self, action: str, payload: dict) -> dict:
        # Propagation du trace_id reçu depuis shop (1)
        trace_id = payload.get("__trace__", "no-trace")

        if action == "charge":
            return await self._charge(payload, trace_id)
        elif action == "refund":
            return await self._refund(payload, trace_id)
        else:
            return error(f"action inconnue: {action}", "unknown_action")

    async def _charge(self, payload: dict, trace_id: str) -> dict:
        order_id = payload.get("order_id")
        amount = payload.get("amount")
        customer_id = payload.get("customer_id")

        if not all([order_id, amount, customer_id]):
            return error("champs requis manquants", "missing_fields")

        if amount <= 0:
            return error("montant invalide", "invalid_amount")

        logger.info(
            "traitement paiement",
            order_id=order_id,
            amount=amount,
            trace_id=trace_id,  # (2)!
        )

        # Stub — intégrer ici Stripe, Adyen, etc.
        try:
            # Simulation d'un appel à la passerelle de paiement
            charge_id = f"ch_{order_id}_{int(amount * 100)}"
            self._processed_count += 1
            logger.info(
                "paiement accepté",
                charge_id=charge_id,
                trace_id=trace_id,
            )
            return ok(charge_id=charge_id, status="succeeded")

        except Exception as e:
            self._payment_gateway_ok = False
            logger.error("erreur passerelle", erreur=str(e), trace_id=trace_id)
            return error(str(e), "gateway_error")

    async def _refund(self, payload: dict, trace_id: str) -> dict:
        charge_id = payload.get("charge_id")
        if not charge_id:
            return error("charge_id requis", "missing_fields")
        logger.info("remboursement", charge_id=charge_id, trace_id=trace_id)
        return ok(refund_id=f"re_{charge_id}", status="refunded")

    # ── Health check ──────────────────────────────────────────────────────────

    async def _health_check_gateway(self) -> tuple[bool, str]:
        """Vérifie l'état interne de la passerelle de paiement."""
        if self._payment_gateway_ok:
            return True, f"ok — {self._processed_count} paiements traités"
        return False, "passerelle en erreur — vérifier les logs"
```

1. Le plugin sandboxed ne peut pas lire le `ContextVar` de trace — `shop` lui transmet le `trace_id` explicitement dans le payload.
2. Le `trace_id` apparaît dans les logs de `billing` ce qui permet de corréler les deux spans dans Jaeger ou Tempo.

---

## 4. Plugin `auth` (Trusted)

Ce plugin expose un backend JWT et une route `/me`. Il doit être chargé avant `shop`.

### `plugin.yaml`

```yaml linenums="1" title="app/plugins/auth/plugin.yaml"
name: auth
version: 1.0.0
description: Authentification JWT
execution_mode: trusted
xcore_version: ">=2.3.0,<3.0"

permissions:
  - cache.sessions
```

### `src/main.py`

```python linenums="1" title="app/plugins/auth/src/main.py"
from __future__ import annotations

import json
from typing import Any

from xcore import TrustedBase, error, ok
from xcore.sdk import (
    AuthBackend,
    AuthPayload,
    action,
    health_check,
    register_auth_backend,
    route,
    unregister_auth_backend,
    AutoDispatchMixin,
    ObservabilityMixin,
)


class JWTBackend(AuthBackend):
    """Backend JWT minimaliste — remplacer par PyJWT en production."""

    async def authenticate(self, token: str) -> AuthPayload | None:
        # Stub : décoder le JWT ici avec PyJWT
        if not token or not token.startswith("Bearer "):
            return None
        raw = token.removeprefix("Bearer ").strip()
        # En prod : jwt.decode(raw, SECRET_KEY, algorithms=["HS256"])
        try:
            # Simulation d'un token valide au format "user_id:tenant_id"
            parts = raw.split(":")
            if len(parts) != 2:
                return None
            return AuthPayload(
                user_id=parts[0],
                tenant_id=parts[1],
                scopes=["read", "write"],
                extra={},
            )
        except Exception:
            return None


class Plugin(ObservabilityMixin, AutoDispatchMixin, TrustedBase):

    async def on_load(self):
        await super().on_load()
        self._backend = JWTBackend()
        register_auth_backend(self._backend)  # (1)!
        self.logger.info("backend JWT enregistré")

    async def on_unload(self):
        await super().on_unload()
        unregister_auth_backend()

    # ── Actions ───────────────────────────────────────────────────────────────

    @action("verify_token")
    async def verify_token(self, payload: dict) -> dict:
        token = payload.get("token", "")
        auth = await self._backend.authenticate(token)
        if auth is None:
            return error("token invalide ou expiré", "unauthorized")
        return ok(user_id=auth.user_id, tenant_id=auth.tenant_id, scopes=auth.scopes)

    # ── HTTP Routes ───────────────────────────────────────────────────────────

    @route("/me", method="GET", tags=["auth"], summary="Profil utilisateur courant")
    async def http_me(self):
        """Retourne l'identité de l'utilisateur authentifié."""
        # En prod, extraire le token depuis Request.headers via une dépendance FastAPI
        return {
            "tenant_id": self.ctx.tenant_id,
            "message": "Authentifié via JWT",
        }

    # ── Health checks ─────────────────────────────────────────────────────────

    @health_check("auth.backend", kind="readiness")
    async def check_backend(self) -> tuple[bool, str]:
        """Vérifie que le backend JWT est opérationnel."""
        try:
            test_result = await self._backend.authenticate("Bearer test:default")
            return True, "backend JWT actif"
        except Exception as e:
            return False, str(e)
```

1. `register_auth_backend` enregistre le backend globalement — tous les plugins peuvent ensuite appeler `get_auth_backend()` pour valider un token.

---

## 5. Plugin `tenant_manager` (Trusted)

Ce plugin provisionne de nouveaux tenants et planifie leur nettoyage automatique.

### `plugin.yaml`

```yaml linenums="1" title="app/plugins/tenant_manager/plugin.yaml"
name: tenant_manager
version: 1.0.0
description: Provisioning et cycle de vie des tenants
execution_mode: trusted
xcore_version: ">=2.3.0,<3.0"

permissions:
  - db.tenants
  - db.schemas
  - events:tenant.*
```

### `src/main.py`

```python linenums="1" title="app/plugins/tenant_manager/src/main.py"
from __future__ import annotations

from datetime import datetime, timedelta

from xcore import TrustedBase, error, ok
from xcore.sdk import (
    AutoDispatchMixin,
    ObservabilityMixin,
    ScheduledMixin,
    action,
    cron,
    health_check,
    require_service,
    traced,
)


class Plugin(ObservabilityMixin, ScheduledMixin, AutoDispatchMixin, TrustedBase):

    async def on_load(self):
        await super().on_load()
        self.db = self.get_service("db")
        self.cache = self.get_service("cache")
        self.logger.info("tenant_manager chargé")

    # ── Actions ───────────────────────────────────────────────────────────────

    @action("create_tenant")
    @require_service("db")
    @traced("tenant_manager.create_tenant")
    async def create_tenant(self, payload: dict) -> dict:
        tenant_id = payload.get("tenant_id")
        plan = payload.get("plan", "free")

        if not tenant_id:
            return error("tenant_id requis", "missing_field")

        # Crée le schéma PostgreSQL dédié au tenant (1)
        async with self.db.session() as session:
            await session.execute(
                f"CREATE SCHEMA IF NOT EXISTS tenant_{tenant_id}"  # (1)!
            )
            await session.execute(
                f"SET search_path TO tenant_{tenant_id}, public"
            )
            # Crée les tables dans le schéma tenant
            await session.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id SERIAL PRIMARY KEY,
                    customer_id VARCHAR(64) NOT NULL,
                    amount FLOAT NOT NULL,
                    status VARCHAR(32) DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            await session.commit()

        # Seed les clés de cache par défaut
        await self.cache.set(
            f"tenant:{tenant_id}:config",
            {"plan": plan, "created_at": datetime.utcnow().isoformat()},
            ttl=0,  # persistant
        )

        # Émet l'événement de création
        await self.ctx.events.emit("tenant.created", {
            "tenant_id": tenant_id,
            "plan": plan,
            "created_at": datetime.utcnow().isoformat(),
        })

        self.logger.info(
            "tenant créé",
            tenant_id=tenant_id,
            plan=plan,
        )
        self.metrics.counter("tenant_manager.tenants.created").inc()
        return ok(tenant_id=tenant_id, schema=f"tenant_{tenant_id}")

    @action("delete_tenant")
    @require_service("db")
    @traced("tenant_manager.delete_tenant")
    async def delete_tenant(self, payload: dict) -> dict:
        tenant_id = payload.get("tenant_id")
        if not tenant_id:
            return error("tenant_id requis", "missing_field")

        async with self.db.session() as session:
            await session.execute(
                f"DROP SCHEMA IF EXISTS tenant_{tenant_id} CASCADE"
            )
            await session.commit()

        await self.cache.delete(f"tenant:{tenant_id}:config")
        await self.ctx.events.emit("tenant.deleted", {"tenant_id": tenant_id})

        self.logger.info("tenant supprimé", tenant_id=tenant_id)
        return ok(tenant_id=tenant_id, deleted=True)

    # ── Scheduler ────────────────────────────────────────────────────────────

    @cron("0 3 * * 0")  # (2)!
    async def weekly_tenant_cleanup(self):
        """Supprime les schémas des tenants inactifs depuis plus de 90 jours."""
        self.logger.info("démarrage du nettoyage hebdomadaire des tenants")
        threshold = datetime.utcnow() - timedelta(days=90)
        # Logique de nettoyage à implémenter selon le modèle de données
        self.metrics.counter("tenant_manager.cleanup.runs").inc()

    # ── Health checks ─────────────────────────────────────────────────────────

    @health_check("tenant_manager.db", kind="readiness")
    async def check_db(self) -> tuple[bool, str]:
        try:
            await self.db.execute("SELECT COUNT(*) FROM information_schema.schemata")
            return True, "ok"
        except Exception as e:
            return False, str(e)
```

1. Chaque tenant possède son propre schéma PostgreSQL. `SET search_path` garantit que les requêtes suivantes s'adressent au bon schéma.
2. Exécution tous les dimanches à 3h00. Le lock Redis empêche les exécutions en double en cas de déploiement multi-workers.

---

## 6. Tests

### Test d'un plugin en isolation

```python linenums="1" title="tests/unit/test_shop.py"
import pytest
from unittest.mock import AsyncMock, MagicMock

from xcore.kernel.api.contract import TrustedBase


@pytest.fixture
def mock_ctx():
    """Contexte minimal pour tester un plugin en isolation."""
    ctx = MagicMock()
    ctx.tenant_id = "tenant_test"
    ctx.events = AsyncMock()
    ctx.events.emit = AsyncMock()
    ctx.tracer = MagicMock()
    ctx.tracer.current_trace_id = MagicMock(return_value="trace-abc-123")
    ctx.metrics = MagicMock()
    ctx.metrics.counter = MagicMock(return_value=MagicMock(inc=MagicMock()))
    ctx.metrics.gauge = MagicMock(return_value=MagicMock(set=MagicMock()))
    return ctx


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.session = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=AsyncMock(
            execute=AsyncMock(),
            add=MagicMock(),
            commit=AsyncMock(),
            refresh=AsyncMock(),
        )),
        __aexit__=AsyncMock(return_value=False),
    ))
    return db


@pytest.fixture
async def shop_plugin(mock_ctx, mock_db):
    """Instancie le plugin shop avec un contexte mocké."""
    from app.plugins.shop.src.main import Plugin
    plugin = Plugin.__new__(Plugin)
    plugin.ctx = mock_ctx
    plugin.db = mock_db
    plugin.cache = AsyncMock()
    plugin.cache.delete = AsyncMock()
    plugin.orders = AsyncMock()
    plugin.orders.find_by_tenant = AsyncMock(return_value=[])
    plugin.logger = MagicMock()
    plugin.metrics = mock_ctx.metrics
    plugin.tracer = mock_ctx.tracer
    plugin.call_plugin = AsyncMock(return_value={"status": "ok", "charge_id": "ch_123"})
    return plugin


@pytest.mark.asyncio
async def test_list_orders_empty(shop_plugin):
    """list_orders retourne une liste vide pour un tenant sans commandes."""
    result = await shop_plugin.list_orders({"page": 1, "per_page": 20})
    assert result["status"] == "ok"
    assert result["orders"] == []
    assert result["total"] == 0
```

### Test d'un appel inter-plugins shop → billing

```python linenums="1" title="tests/unit/test_inter_plugin.py"
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_create_order_calls_billing(shop_plugin):
    """create_order doit appeler billing.charge avec le bon montant."""
    payload = {
        "customer_id": "cust_001",
        "product_id": "prod_abc",
        "amount": 49.99,
        "quantity": 2,
    }

    result = await shop_plugin.create_order(payload)

    assert result["status"] == "ok"
    shop_plugin.call_plugin.assert_called_once_with(
        "billing",
        "charge",
        {
            "order_id": result["order_id"],
            "amount": 99.98,  # 49.99 * 2
            "customer_id": "cust_001",
            "__trace__": "trace-abc-123",
        },
    )


@pytest.mark.asyncio
async def test_create_order_payment_failure(shop_plugin):
    """Si billing retourne une erreur, create_order doit propager l'erreur."""
    shop_plugin.call_plugin = AsyncMock(return_value={
        "status": "error",
        "message": "carte refusée",
    })

    result = await shop_plugin.create_order({
        "customer_id": "cust_002",
        "product_id": "prod_xyz",
        "amount": 100.0,
        "quantity": 1,
    })

    assert result["status"] == "error"
    assert result["code"] == "payment_failed"
```

### Test des health checks

```python linenums="1" title="tests/unit/test_health.py"
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_shop_liveness_always_true(shop_plugin):
    ok, msg = await shop_plugin.check_liveness()
    assert ok is True
    assert msg == "running"


@pytest.mark.asyncio
async def test_shop_readiness_db_failure(shop_plugin):
    shop_plugin.db.execute = AsyncMock(side_effect=Exception("connexion refusée"))
    ok, msg = await shop_plugin.check_db()
    assert ok is False
    assert "connexion refusée" in msg
```

### Test de l'isolation multi-tenant

```python linenums="1" title="tests/integration/test_tenancy.py"
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_two_tenants_isolated_orders(mock_db):
    """Deux tenants ne voient pas les commandes de l'autre."""
    from app.plugins.shop.src.main import Plugin, Order

    # Tenant A
    ctx_a = MagicMock()
    ctx_a.tenant_id = "tenant_a"
    ctx_a.events = AsyncMock()
    ctx_a.tracer = MagicMock()
    ctx_a.tracer.current_trace_id = MagicMock(return_value="trace-a")
    ctx_a.metrics = MagicMock()
    ctx_a.metrics.counter = MagicMock(return_value=MagicMock(inc=MagicMock()))

    # Tenant B
    ctx_b = MagicMock()
    ctx_b.tenant_id = "tenant_b"
    ctx_b.events = AsyncMock()
    ctx_b.tracer = MagicMock()
    ctx_b.tracer.current_trace_id = MagicMock(return_value="trace-b")
    ctx_b.metrics = MagicMock()
    ctx_b.metrics.counter = MagicMock(return_value=MagicMock(inc=MagicMock()))

    orders_a = [
        Order(id=1, tenant_id="tenant_a", customer_id="c1", amount=50.0, status="paid")
    ]
    orders_b = [
        Order(id=2, tenant_id="tenant_b", customer_id="c2", amount=75.0, status="paid"),
        Order(id=3, tenant_id="tenant_b", customer_id="c3", amount=30.0, status="paid"),
    ]

    plugin_a = Plugin.__new__(Plugin)
    plugin_a.ctx = ctx_a
    plugin_a.logger = MagicMock()
    plugin_a.metrics = ctx_a.metrics
    plugin_a.orders = AsyncMock()
    plugin_a.orders.find_by_tenant = AsyncMock(return_value=orders_a)

    plugin_b = Plugin.__new__(Plugin)
    plugin_b.ctx = ctx_b
    plugin_b.logger = MagicMock()
    plugin_b.metrics = ctx_b.metrics
    plugin_b.orders = AsyncMock()
    plugin_b.orders.find_by_tenant = AsyncMock(return_value=orders_b)

    result_a = await plugin_a.list_orders({"page": 1, "per_page": 20})
    result_b = await plugin_b.list_orders({"page": 1, "per_page": 20})

    # Tenant A voit 1 commande, tenant B en voit 2
    assert result_a["total"] == 1
    assert result_b["total"] == 2

    # Aucun chevauchement
    ids_a = {o["id"] for o in result_a["orders"]}
    ids_b = {o["id"] for o in result_b["orders"]}
    assert ids_a.isdisjoint(ids_b)
```

!!! tip "Variables d'environnement pour les tests d'intégration"
    ```bash
    DATABASE_URL=sqlite+aiosqlite:///./test.db
    REDIS_URL=redis://localhost:6379/0
    SECRET_KEY=test-secret-key-not-for-production
    ```

---

## 7. Déploiement Kubernetes

Les endpoints `/health/live` et `/health/ready` sont exposés automatiquement par xcore. Configurez vos probes Kubernetes pour les utiliser.

```yaml linenums="1" title="k8s/deployment.yaml"
apiVersion: apps/v1
kind: Deployment
metadata:
  name: xcore-ecommerce
spec:
  replicas: 3
  selector:
    matchLabels:
      app: xcore-ecommerce
  template:
    metadata:
      labels:
        app: xcore-ecommerce
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "9090"   # (1)!
        prometheus.io/path: "/metrics"
    spec:
      containers:
        - name: api
          image: your-registry/xcore-ecommerce:latest
          ports:
            - containerPort: 8000
            - containerPort: 9090
          env:
            - name: SECRET_KEY
              valueFrom:
                secretKeyRef:
                  name: xcore-secrets
                  key: secret-key
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: xcore-secrets
                  key: database-url
            - name: REDIS_URL
              valueFrom:
                secretKeyRef:
                  name: xcore-secrets
                  key: redis-url
          livenessProbe:        # (2)!
            httpGet:
              path: /health/live
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 15
            failureThreshold: 3
          readinessProbe:       # (3)!
            httpGet:
              path: /health/ready
              port: 8000
            initialDelaySeconds: 20
            periodSeconds: 10
            failureThreshold: 3
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "1000m"
```

1. Kubernetes scrape automatiquement les métriques Prometheus sur le port 9090 grâce à ces annotations.
2. `/health/live` agrège tous les health checks `kind="liveness"`. Si ce probe échoue, Kubernetes redémarre le pod.
3. `/health/ready` agrège tous les health checks `kind="readiness"` (DB, cache, etc.). Si ce probe échoue, le pod est retiré du load balancer sans être redémarré.

!!! warning "Scheduler en multi-replicas"
    Avec `replicas: 3`, trois instances du scheduler tournent en parallèle. xcore utilise un lock Redis (`xcore:sched:lock:<job_id>`) pour s'assurer que chaque job ne s'exécute qu'une seule fois. Vérifiez que `REDIS_URL` pointe bien sur la même instance Redis pour toutes les replicas.

!!! note "Plugin sandboxed en Kubernetes"
    Le plugin `billing` en mode `sandboxed` spawne un subprocess à l'intérieur du container. Assurez-vous que votre `securityContext` autorise la création de processus enfants (`allowPrivilegeEscalation: false` est compatible).
