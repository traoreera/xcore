# XCore — Connaissance complète pour agents IA

> Ce fichier est la source de vérité pour tout agent qui travaille sur XCore.
> Il couvre l'architecture, les APIs, les patterns, les pièges et des exemples complets.

---

## 1. Vue d'ensemble rapide

XCore est un **framework d'orchestration plugin-first** construit sur FastAPI.
Il charge, isole et orchestre des **plugins** (modules Python) dans un environnement sécurisé.

```
xcore/
├── kernel/          # Runtime, permissions, sécurité, observabilité, events
├── services/        # DB, Cache, Scheduler, Worker, DI container
├── configurations/  # Loader YAML + dataclasses de config
├── registry/        # Index des plugins connus
├── marketplace/     # Client HTTP du store de plugins
└── sdk/             # Shim de compatibilité → xcoresdk package
```

**Commandes essentielles :**
```bash
poetry run xcli worker start api   # démarrer l'API
make test                           # tests complets + coverage
make lint-fix                       # black + isort
poetry run pytest tests/ -x -q     # rapide
```

**Config principale :** `integration.yaml` (pas `xcore.yaml`)

---

## 2. Plugin — Structure minimale

```
app/plugins/mon_plugin/
├── plugin.yaml
└── src/
    └── main.py
```

### plugin.yaml — champs complets

```yaml
name: mon-plugin
version: 1.2.0
author: team
description: Ce que fait ce plugin.
framework_version: ">=2.3"

# OBLIGATOIRE : trusted | sandboxed | ephemeral
execution_mode: trusted

entry_point: src/main.py

# Variables d'environnement injectées dans le plugin
env:
  DATABASE_URL: "postgresql://..."
  API_KEY: "${MY_API_KEY}"   # interpolation depuis les variables d'env système

# Dépendances vers d'autres plugins (chargés avant celui-ci)
requires:
  - auth-plugin
  - billing-plugin

# Permissions déclarées (OBLIGATOIRE pour accéder aux services)
permissions:
  - resource: "db.*"
    actions: ["read", "write"]
    effect: allow
  - resource: "cache.*"
    actions: ["read", "write"]
    effect: allow
  - resource: "scheduler.*"
    actions: ["add", "remove"]
    effect: allow
  - resource: "events.*"
    actions: ["emit", "subscribe"]
    effect: allow

# Limites de ressources (optionnel, défauts raisonnables)
resources:
  timeout_seconds: 30
  max_memory_mb: 512
  rate_limit:
    calls: 100
    period_seconds: 60

# Config spécifique au plugin (accessible via self.ctx.config)
extra:
  my_setting: "value"
  max_items: 100
```

### plugin.yaml — mode Ephemeral

```yaml
execution_mode: ephemeral

ephemeral:
  pool_size: 4          # instances préchauffées (0 = cold boot pur)
  max_idle_seconds: 120 # libère après X secondes d'inactivité
  max_concurrent: 8     # parallélisme max (backpressure au-delà)
  boot_timeout: 5.0     # timeout de chargement d'une instance
```

### plugin.yaml — mode Sandboxed

```yaml
execution_mode: sandboxed

resources:
  timeout_seconds: 10
  max_memory_mb: 256
  max_disk_mb: 100      # quota disque pour le subprocess
```

---

## 3. Plugin — Code complet

### Import minimal

```python
from xcore.sdk import TrustedBase, ok, error
```

### Classe de base

```python
# src/main.py
from xcore.sdk import (
    TrustedBase, ok, error,
    action, route, schema,
    cron, interval,
    on_event, on_hook,
    health_check, traced, counted, timed,
    cached, invalidate,
    require_service, retry,
    AutoMixin,
)

class Plugin(TrustedBase):

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def on_load(self):
        """Appelé une fois au démarrage. Initialiser les services ici."""
        self.db = self.get_service("db")
        self.cache = self.get_service("cache")
        self.logger.info("plugin chargé", plugin=self.ctx.name)

    async def on_reload(self):
        """Appelé après un hot-reload."""
        await self.on_load()

    async def on_unload(self):
        """Appelé à l'arrêt."""
        self.logger.info("plugin arrêté")

    # ── Action principale ─────────────────────────────────────────────────────

    async def handle(self, action: str, payload: dict) -> dict:
        if action == "ping":
            return ok(msg="pong")
        if action == "create_user":
            return await self._create_user(payload)
        return error(f"Action inconnue : {action}", "unknown_action")
```

### Réponses standardisées

```python
from xcore.sdk import ok, error

return ok()                              # {"status": "ok"}
return ok(data={"id": 1})               # {"status": "ok", "data": {"id": 1}}
return ok(user_id=42, name="Alice")     # {"status": "ok", "user_id": 42, "name": "Alice"}

return error("message")                 # {"status": "error", "msg": "message"}
return error("non trouvé", "not_found") # {"status": "error", "msg": "...", "code": "not_found"}
```

---

## 4. SDK — Tous les décorateurs

### @action + AutoDispatchMixin

```python
from xcore.sdk import action, AutoDispatchMixin

class Plugin(AutoDispatchMixin, TrustedBase):
    # AutoDispatchMixin génère handle() automatiquement

    @action("greet")
    async def greet(self, payload: dict) -> dict:
        return ok(msg=f"Hello {payload.get('name', 'world')}")

    @action("bye")
    async def bye(self, payload: dict) -> dict:
        return ok(msg="Goodbye")
```

### @schema — Validation + versioning contrat

```python
@action("create_user")
@schema(
    version="2.0",
    input={
        "email": (str, ...),       # requis
        "role": (str, "user"),     # optionnel, défaut "user"
        "age": (int, ...),         # requis
    },
    output={"user_id": int, "created_at": str},
    deprecated_fields={"username": "Supprimé en v2.0"},
    breaking_since="2.0",
    validate=True,           # valide le payload automatiquement
    type_response="dict",    # "dict" | "model" (Pydantic)
)
async def create_user(self, payload: dict) -> dict:
    return ok(user_id=1, created_at="2026-01-01")
```

### @route — Routes HTTP FastAPI

```python
from xcore.sdk import route, RoutedPlugin

class Plugin(RoutedPlugin, TrustedBase):

    @route("/items", method="GET", tags=["items"])
    async def list_items(self):
        return [{"id": 1}]

    @route("/items/{item_id}", method="GET")
    async def get_item(self, item_id: int):
        return {"id": item_id}

    @route("/items", method="POST", status_code=201)
    async def create_item(self, body: dict):
        return {"created": True}

    @route("/admin", method="GET", permissions=["admin"])  # RBAC auto
    async def admin_endpoint(self):
        return {"secret": True}

    async def handle(self, action, payload):
        return error("action inconnue")

# Montées sous /plugins/<plugin_name><path>
```

### @cron et @interval

```python
from xcore.sdk import cron, interval, ScheduledMixin

class Plugin(ScheduledMixin, TrustedBase):

    @cron("0 3 * * *")
    async def nightly_cleanup(self):
        ...

    @cron("*/5 * * * *", job_id="my.sync", max_instances=1, timeout=60.0)
    async def every_5_min(self):
        ...

    @interval(seconds=30)
    async def heartbeat(self):
        ...

    @interval(minutes=10, retry=3, retry_delay=5.0)
    async def sync_with_api(self):
        ...
```

### @on_event et @on_hook

```python
from xcore.sdk import on_event, on_hook, EventMixin, HookMixin, Event

class Plugin(EventMixin, HookMixin, TrustedBase):

    @on_event("user.created")
    async def welcome_user(self, event: Event):
        user_id = event.data["user_id"]

    @on_event("order.*")              # wildcard
    async def on_any_order(self, event: Event):
        ...

    @on_event("critical.alert", once=True)
    async def on_first_alert(self, event: Event):
        ...

    @on_hook("plugin.*.loaded", priority=10)
    async def after_any_plugin_load(self, event: Event):
        ...

    async def handle(self, action, payload):
        await self.ctx.events.emit("user.created", {"user_id": 42})
        return ok()
```

### @health_check

```python
from xcore.sdk import health_check, ObservabilityMixin

class Plugin(ObservabilityMixin, TrustedBase):

    @health_check("mon_plugin.db")
    async def check_db(self) -> tuple[bool, str]:
        try:
            await self.get_service("db").execute("SELECT 1")
            return True, "ok"
        except Exception as e:
            return False, str(e)

    @health_check("mon_plugin.api", kind="liveness")
    async def check_internal(self) -> tuple[bool, str]:
        return True, "alive"
```

### @traced, @counted, @timed

```python
@action("process")
@traced("process_item")
@counted("plugin.process.calls")
@timed("plugin.process.duration_ms")
async def process(self, payload: dict) -> dict:
    ...
```

### @cached et @invalidate

```python
@action("get_user")
@cached(key="user:{payload[user_id]}", ttl=300)
async def get_user(self, payload: dict) -> dict:
    ...

@action("update_user")
@invalidate(key="user:{payload[user_id]}")
async def update_user(self, payload: dict) -> dict:
    ...
```

### @retry

```python
@action("fetch_external")
@retry(max_attempts=3, backoff=1.0, exceptions=(IOError, TimeoutError))
async def fetch_external(self, payload: dict) -> dict:
    ...
```

### AutoMixin — Tout en un

```python
from xcore.sdk import AutoMixin

class Plugin(AutoMixin):
    """Combine AutoDispatchMixin + EventMixin + HookMixin +
       ObservabilityMixin + ScheduledMixin + RoutedPlugin"""

    @action("ping")
    async def ping(self, payload: dict) -> dict:
        return ok(msg="pong")

    @cron("0 * * * *")
    async def hourly(self):
        ...

    @on_event("user.*")
    async def on_user_event(self, event):
        ...

    @route("/ping", method="GET")
    async def ping_http(self):
        return {"pong": True}
```

---

## 5. Services — Accès depuis un plugin

### Accès aux services

```python
async def on_load(self):
    self.db      = self.get_service("db")             # AsyncSQLAdapter
    self.cache   = self.get_service("cache")          # CacheService
    self.mongo   = self.get_service("mongodb")        # MongoDBAdapter
    self.redis   = self.get_service("redisAdapter")   # RedisAdapter
    self.syncdb  = self.get_service("syncdb")         # SQLAdapter (sync)
    svc          = self.get_service_as("mon_svc", MonService)  # typage explicite
```

### Base de données (AsyncSQL)

```python
await self.db.execute("CREATE TABLE IF NOT EXISTS items (id SERIAL PRIMARY KEY, name TEXT)")
await self.db.execute("INSERT INTO items (name) VALUES (:name)", {"name": "foo"})

row  = await self.db.fetch_one("SELECT * FROM items WHERE id = :id", {"id": 1})
rows = await self.db.fetch_all("SELECT * FROM items WHERE active = :a", {"a": True})
item = dict(row) if row else None

async with self.db.session() as session:
    await session.execute("BEGIN")
    await session.execute("INSERT INTO ...")
    await session.execute("COMMIT")
```

### Cache

```python
await self.cache.set("key", {"data": "value"}, ttl=300)
value = await self.cache.get("key")   # None si absent
await self.cache.delete("key")
```

### Scheduler programmatique (cas avancé)

```python
scheduler = self.get_service("scheduler")
await scheduler.add_job(func=self._my_func, trigger="interval", seconds=60, job_id="my_job")
await scheduler.remove_job("my_job")
```

### Repository pattern

```python
from xcore.sdk import BaseAsyncRepository
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, Integer, String

class Base(DeclarativeBase): pass

class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True)
    name = Column(String)

class ItemRepository(BaseAsyncRepository[Item]):
    def __init__(self):
        super().__init__(Item)

class Plugin(TrustedBase):
    async def on_load(self):
        self.repo = ItemRepository()

    async def handle(self, action, payload):
        async with self.get_service("db").session() as session:
            item = await self.repo.get_by_id(session, payload["id"])
            return ok(item={"id": item.id, "name": item.name})
```

### Redis Repository

```python
from xcore.sdk import BaseRedisRepository

class SessionRepo(BaseRedisRepository):
    prefix = "session"   # toutes les clés : "session:<key>"

    async def create(self, token: str, data: dict, ttl: int = 3600):
        await self.set(token, data, ttl=ttl)

    async def fetch(self, token: str) -> dict | None:
        return await self.get(token)

class Plugin(TrustedBase):
    async def on_load(self):
        redis = self.get_service("redisAdapter")
        self.sessions = SessionRepo(redis)
```

---

## 6. Créer un service custom

Il y a **deux méthodes** pour ajouter un service personnalisé dans XCore.

---

### Méthode 1 — Extension via integration.yaml (recommandée, sans code kernel)

La plus simple. Déclarer le service dans `integration.yaml` sous `services.extensions`.
XCore l'instancie, appelle `init()` et `shutdown()` automatiquement.

```yaml
# integration.yaml
services:
  extensions:
    email:
      module: myapp.services.email:EmailService
      config:
        smtp_host: smtp.gmail.com
        smtp_port: 587
        username: "${SMTP_USER}"
        password: "${SMTP_PASS}"

    stripe:
      module: myapp.services.payments:StripeService
      config:
        api_key: "${STRIPE_SECRET_KEY}"
        webhook_secret: "${STRIPE_WEBHOOK_SECRET}"
```

**Le service doit hériter de `BaseService` :**

```python
# myapp/services/email.py
from xcore.services.base import BaseService, ServiceStatus

class EmailService(BaseService):
    name = "email"

    def __init__(self, config: dict):
        super().__init__()
        self.smtp_host = config["smtp_host"]
        self.smtp_port = config["smtp_port"]
        self.username  = config["username"]
        self.password  = config["password"]
        self._client   = None

    async def init(self) -> None:
        # Connexion / warmup
        import aiosmtplib
        self._client = aiosmtplib.SMTP(
            hostname=self.smtp_host,
            port=self.smtp_port,
            use_tls=True,
        )
        await self._client.connect()
        await self._client.login(self.username, self.password)
        self._status = ServiceStatus.READY

    async def shutdown(self) -> None:
        if self._client:
            await self._client.quit()
        self._status = ServiceStatus.STOPPED

    async def health_check(self) -> tuple[bool, str]:
        try:
            await self._client.noop()
            return True, "ok"
        except Exception as e:
            return False, str(e)

    def status(self) -> dict:
        return {"name": self.name, "status": self._status.value}

    # Méthodes métier du service
    async def send(self, to: str, subject: str, body: str) -> None:
        from email.mime.text import MIMEText
        msg = MIMEText(body, "html")
        msg["Subject"] = subject
        msg["From"] = self.username
        msg["To"] = to
        await self._client.sendmail(self.username, [to], msg.as_string())
```

**Accès depuis un plugin :**

```python
class Plugin(TrustedBase):
    async def on_load(self):
        # Le nom d'accès est "ext.<nom_déclaré_dans_yaml>"
        self.email = self.get_service("ext.email")

    async def handle(self, action, payload):
        if action == "send_welcome":
            await self.email.send(
                to=payload["email"],
                subject="Bienvenue !",
                body="<h1>Bonjour !</h1>",
            )
            return ok()
```

---

### Méthode 2 — ServiceProvider custom (injection dans le container)

Pour un contrôle total sur l'initialisation, ou pour brancher plusieurs services d'un coup.

```python
# myapp/providers.py
from xcore.services.base import BaseService, BaseServiceProvider, ServiceStatus
from xcore.services.container import ServiceContainer

class MyCustomService(BaseService):
    name = "my_custom"

    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key
        self._client = None

    async def init(self) -> None:
        from mylib import Client
        self._client = Client(api_key=self.api_key)
        await self._client.connect()
        self._status = ServiceStatus.READY

    async def shutdown(self) -> None:
        if self._client:
            await self._client.close()
        self._status = ServiceStatus.STOPPED

    async def health_check(self) -> tuple[bool, str]:
        try:
            await self._client.ping()
            return True, "ok"
        except Exception as e:
            return False, str(e)

    def status(self) -> dict:
        return {"name": self.name, "status": self._status.value}


class MyCustomServiceProvider(BaseServiceProvider):
    async def init(self, container: ServiceContainer) -> None:
        api_key = container._config.extensions.get("my_custom", {}).get("config", {}).get("api_key")
        svc = MyCustomService(api_key=api_key)
        await svc.init()
        # Enregistre sous le nom "my_custom" dans le container
        container.register_service("my_custom", svc)
```

**Brancher le provider au boot de l'app :**

```python
# Dans le point d'entrée de l'app (avant container.init())
from myapp.providers import MyCustomServiceProvider
container.add_provider(MyCustomServiceProvider())
await container.init()
```

**Ou enregistrement manuel direct (sans provider) :**

```python
# Pour les services légers qui n'ont pas besoin de lifecycle
container.register_service("feature_flags", FeatureFlagClient(url="..."))
```

---

### Méthode 3 — Enregistrement depuis un plugin (service partagé entre plugins)

Un plugin peut enregistrer un service dans le container pour que d'autres plugins l'utilisent.

```python
class Plugin(TrustedBase):
    async def on_load(self):
        # Ce plugin expose son client HTTP pour les autres plugins
        from mylib import HttpClient
        client = HttpClient(base_url="https://api.example.com")
        await client.connect()

        # Enregistre dans le container partagé
        self.ctx.services["http_client"] = client

    async def on_unload(self):
        client = self.ctx.services.pop("http_client", None)
        if client:
            await client.close()
```

**Accès depuis un autre plugin :**

```python
class OtherPlugin(TrustedBase):
    async def on_load(self):
        # Attend que le plugin qui expose le service soit chargé (via `requires`)
        self.http = self.get_service("http_client")
```

```yaml
# plugin.yaml de OtherPlugin
requires:
  - mon-plugin-qui-expose-http  # garantit l'ordre de chargement
```

---

### Contrat BaseService — résumé

```python
from xcore.services.base import BaseService, ServiceStatus

class MonService(BaseService):
    name = "mon_service"   # nom affiché dans les logs et le status

    def __init__(self, config: dict):
        super().__init__()  # initialise self._status = ServiceStatus.UNINITIALIZED
        # stocker la config

    async def init(self) -> None:
        # Connexion, warmup, vérification
        # Obligatoire : mettre self._status = ServiceStatus.READY en fin
        self._status = ServiceStatus.READY

    async def shutdown(self) -> None:
        # Fermeture propre des connexions
        self._status = ServiceStatus.STOPPED

    async def health_check(self) -> tuple[bool, str]:
        # Retourne (True, "ok") ou (False, "message d'erreur")
        return True, "ok"

    def status(self) -> dict:
        # Dict affiché dans /status et les logs
        return {"name": self.name, "status": self._status.value}

# États disponibles dans ServiceStatus :
# UNINITIALIZED → INITIALIZING → READY → DEGRADED → STOPPED → FAILED
```

---

### Config dans integration.yaml pour les services

```yaml
services:
  # BDD multiples — chaque entrée est un adaptateur distinct
  databases:
    default:
      type: postgresql+aio       # sqlite | postgresql | mysql | sqlite+aio | postgresql+aio | mongodb | redis
      url: "${DATABASE_URL}"
      pool_size: 10
      max_overflow: 20
      pool_pre_ping: true
      pool_recycle: 1800         # recycle avant que la BDD coupe (< wait_timeout MySQL)
      pool_timeout: 30
      pool_reset_on_return: rollback   # "rollback" | "commit" | "none"
      echo: false
      connect_args:
        command_timeout: 30      # asyncpg
      isolation_level: null      # "READ COMMITTED" | "SERIALIZABLE" | null

    analytics:
      type: postgresql+aio
      url: "${ANALYTICS_DB_URL}"

    mongo:
      type: mongodb
      url: "${MONGO_URL}"
      database: myapp

    redis_store:
      type: redis
      url: "${REDIS_URL}"

  cache:
    backend: redis               # "memory" | "redis"
    url: "${REDIS_URL}"
    ttl: 300                     # TTL par défaut en secondes
    max_size: 1000               # taille max en mode memory

  scheduler:
    enabled: true
    backend: redis               # "memory" | "redis"
    url: "${REDIS_URL}"
    timezone: Europe/Paris

  xworker:
    enabled: false
    broker_url: "${REDIS_URL}"
    result_backend: "${REDIS_URL}"
    queues: ["default", "high", "low"]
    concurrency: 4

  extensions:
    email:
      module: myapp.services.email:EmailService
      config:
        smtp_host: smtp.gmail.com
        smtp_port: 587
        username: "${SMTP_USER}"
        password: "${SMTP_PASS}"
    stripe:
      module: myapp.services.payments:StripeService
      config:
        api_key: "${STRIPE_SECRET_KEY}"
```

---

### Accès aux BDD multiples depuis un plugin

```yaml
# plugin.yaml — permission sur une BDD nommée
permissions:
  - resource: "db.*"
    actions: ["read", "write"]
    effect: allow
```

```python
async def on_load(self):
    # BDD principale (premier adapter déclaré ou celui nommé "default")
    self.db       = self.get_service("db")

    # BDD nommées explicitement
    self.analytics = self.get_service("analytics")
    self.mongo     = self.get_service("mongo")
    self.redis     = self.get_service("redis_store")
```

---

## 7. Observabilité — APIs directes

### Logger

```python
from xcore.kernel.observability import get_logger
logger = get_logger("xcore.mon_module")   # namespace obligatoire

self.logger.info("message", champ="valeur", autre=42)
self.logger.warning("attention", plugin="mon_plugin")
self.logger.error("erreur", erreur=str(e))
self.logger.debug("debug", payload=payload)

# INTERDIT
import logging; logging.getLogger("mon_plugin")  # pas structuré, pas capturé
```

### Métriques

```python
self.metrics.counter("calls_total", labels={"plugin": "shop"}).inc()
self.metrics.gauge("queue_size").set(42)
self.metrics.gauge("active_connections").inc()
self.metrics.histogram("duration_ms").observe(123.4)
```

### Tracing

```python
with self.tracer.span("operation") as span:
    span.set_attribute("user_id", 42)
    result = await self._do_work()
    if error:
        span.set_status("error")
        span.set_attribute("error.message", str(e))
```

---

## 8. Appels inter-plugins

```python
result = await self.call_plugin("billing-plugin", "charge", {
    "amount": 100,
    "currency": "EUR",
    "user_id": 42,
})

if result.get("status") == "ok":
    charge_id = result["charge_id"]
else:
    return error(result.get("msg", "billing failed"), "billing_error")
```

---

## 9. Permissions

```yaml
permissions:
  - resource: "db.*"
    actions: ["read", "write"]
    effect: allow
  - resource: "db.users"
    actions: ["delete"]
    effect: deny
  - resource: "events.*"
    actions: ["emit", "subscribe"]
    effect: allow
  - resource: "plugins.billing-plugin"
    actions: ["call"]
    effect: allow
```

---

## 10. Multi-tenancy

```yaml
tenancy:
  enabled: true
  isolate_db: true
  isolate_cache: true
  isolate_scheduler: false
```

Le `tenant_id` vient du header `X-Tenant-ID` ou du sous-domaine.
Les services DB/Cache/Scheduler prefixent automatiquement — **rien à faire dans le plugin**.

---

## 11. Auth

```python
from xcore.sdk import AuthBackend, AuthPayload, register_auth_backend

class JWTBackend(AuthBackend):
    async def authenticate(self, token: str) -> AuthPayload | None:
        try:
            payload = jwt.decode(token, SECRET, algorithms=["HS256"])
            return AuthPayload(
                user_id=payload["sub"],
                roles=payload.get("roles", []),
                scopes=payload.get("scopes", []),
                extra=payload,
            )
        except jwt.InvalidTokenError:
            return None

async def on_load(self):
    register_auth_backend("jwt", JWTBackend())
```

---

## 12. Modes d'exécution — différences clés

| | `trusted` | `sandboxed` | `ephemeral` |
|---|---|---|---|
| Processus | In-process | Subprocess isolé | In-process (pool) |
| Accès services | Direct `get_service()` | Via IPC JSON | Direct `get_service()` |
| État persistant | Oui | Oui (subprocess) | **Non** (stateless) |
| Sécurité | Moyenne | Haute | Moyenne |
| Performance | Haute | Basse (IPC overhead) | Haute (warm pool) |
| Cas d'usage | Services métier internes | Code tiers, UGC | Fonctions sans état |

---

## 13. Pièges critiques

```python
# INTERDIT — logger standard, pas structuré
import logging; logging.getLogger("mon_plugin")

# INTERDIT — race condition multi-tenant
self.current_tenant = tenant_id

# INTERDIT — bound method → pickle Redis échoue
scheduler.add_job(self.my_method, ...)

# CORRECT — scheduler via décorateur
@cron("0 3 * * *")
async def nightly(self): ...

# CORRECT — patch au niveau du module SOURCE dans les tests
@patch("xcore.services.container.ServiceContainer.get")  # ✓
@patch("xcore.ServiceContainer.get")                      # ✗

# CORRECT — logger xcore
from xcore.kernel.observability import get_logger
logger = get_logger("xcore.mon_plugin")
logger.info("action", user_id=42)  # kwargs structurés, jamais f-strings
```

---

## 14. Tests — patterns standards

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.fetch_one.return_value = {"id": 1, "name": "test"}
    db.fetch_all.return_value = [{"id": 1}, {"id": 2}]
    db.execute.return_value = None
    return db

@pytest.fixture
async def plugin(mock_db):
    from app.plugins.mon_plugin.src.main import Plugin
    p = Plugin()
    p._ctx = MagicMock()
    p._ctx.services = {"db": mock_db, "cache": AsyncMock()}
    p._ctx.name = "mon-plugin"
    p._ctx.config = MagicMock()
    p._ctx.events = AsyncMock()
    p._ctx.tracer = MagicMock()
    p._ctx.metrics = MagicMock()
    p._ctx.health = MagicMock()
    await p._inject_context(p._ctx)
    await p.on_load()
    return p

async def test_create_user(plugin, mock_db):
    result = await plugin.handle("create_user", {"email": "alice@test.com"})
    assert result["status"] == "ok"
    mock_db.execute.assert_called_once()

async def test_missing_field(plugin):
    result = await plugin.handle("create_user", {})
    assert result["status"] == "error"
    assert result.get("code") == "missing_field"
```

Variables d'environnement pour les tests :
```bash
DATABASE_URL=sqlite:///./test.db
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=test-secret-key
```

`asyncio_mode = auto` → pas de `@pytest.mark.asyncio`. Coverage `fail_under = 80` (branch).

---

## 15. Flux HTTP → Plugin

```
HTTP Request
  └─ TenantMiddleware       (extrait X-Tenant-ID, met ContextVar)
       └─ Router            (/plugins/{name}/{action})
            └─ supervisor.call(name, action, payload)
                 └─ IPCAuthMiddleware
                      └─ TracingMiddleware    (span + propagation trace_id)
                           └─ RateLimitMiddleware
                                └─ PermissionMiddleware
                                     └─ RetryMiddleware
                                          └─ handler.call(action, payload)
                                               └─ Plugin.handle(action, payload)
```

---

## 16. Endpoints système automatiques

| Endpoint | Description |
|---|---|
| `GET /status` | État de tous les plugins |
| `POST /plugins/{name}/reload` | Hot-reload un plugin |
| `POST /plugins/{name}/load` | Charger un plugin |
| `POST /plugins/{name}/unload` | Décharger un plugin |
| `GET /metrics` | Métriques Prometheus |
| `GET /health` | Health de tous les checks |
| `GET /health/live` | Liveness (k8s probe) |
| `GET /health/ready` | Readiness (k8s probe) |
| `POST /plugins/{name}/{action}` | Appel direct d'une action |

---

## 17. Référence rapide des imports

```python
# Base
from xcore.sdk import TrustedBase, ok, error

# Dispatch
from xcore.sdk import action, AutoDispatchMixin, AutoMixin

# HTTP
from xcore.sdk import route, RoutedPlugin

# Schémas
from xcore.sdk import schema, validate_payload

# Scheduler
from xcore.sdk import cron, interval, ScheduledMixin

# Events
from xcore.sdk import on_event, on_hook, EventMixin, HookMixin, Event

# Observabilité
from xcore.sdk import health_check, traced, counted, timed, ObservabilityMixin
from xcore.kernel.observability import get_logger

# Cache
from xcore.sdk import cached, invalidate

# Guards
from xcore.sdk import require_service, retry, trusted, sandboxed

# RBAC
from xcore.sdk import require_permission, require_role, RBACChecker

# Auth
from xcore.sdk import AuthBackend, AuthPayload, register_auth_backend

# Repositories
from xcore.sdk import BaseAsyncRepository, BaseRedisRepository, BaseMongoRepository

# Services custom
from xcore.services.base import BaseService, BaseServiceProvider, ServiceStatus
from xcore.services.container import ServiceContainer

# Modes
from xcore.sdk import ExecutionMode  # trusted, sandboxed, ephemeral

# Erreurs
from xcore.sdk import PermissionDenied
```
