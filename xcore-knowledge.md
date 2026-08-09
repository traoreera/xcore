# XCore — Complete Knowledge Base for AI Agents

> This file is the source of truth for any agent working on XCore.
> It covers the architecture, APIs, patterns, gotchas, and complete examples.

---

## 1. Quick Overview

XCore is a **plugin-first orchestration framework** built on FastAPI.
It loads, isolates, and orchestrates **plugins** (Python modules) in a secure, sandboxed environment.

```
xcore/
├── kernel/          # Runtime, permissions, security, observability, events
├── services/        # DB, Cache, Scheduler, Worker, DI container
├── configurations/  # YAML Loader + config dataclasses
├── registry/        # Known plugins index
├── marketplace/     # Plugin store HTTP client
└── sdk/             # Compatibility shim → xcoresdk package
```

**Essential Commands:**
```bash
poetry run xcli worker start api   # start the API
make test                           # full tests + coverage
make lint-fix                       # black + isort
poetry run pytest tests/ -x -q     # fast pytest run
```

**Main Config:** `integration.yaml` (not `xcore.yaml`)

---

## 2. Plugin — Minimal Structure

```
app/plugins/my_plugin/
├── plugin.yaml
└── src/
    └── main.py
```

### plugin.yaml — Complete Fields

```yaml
name: my-plugin
version: 1.2.0
author: team
description: What this plugin does.
framework_version: ">=2.3"

# REQUIRED: trusted | sandboxed | ephemeral
execution_mode: trusted

entry_point: src/main.py

# Environment variables injected into the plugin
env:
  DATABASE_URL: "postgresql://..."
  API_KEY: "${MY_API_KEY}"   # interpolated from system env variables

# Dependencies on other plugins (loaded before this one)
requires:
  - auth-plugin
  - billing-plugin

# Declared permissions (REQUIRED to access services)
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

# Resource limits (optional, reasonable defaults)
resources:
  timeout_seconds: 30
  max_memory_mb: 512
  rate_limit:
    calls: 100
    period_seconds: 60

# Plugin-specific config (accessible via self.ctx.config)
extra:
  my_setting: "value"
  max_items: 100
```

### plugin.yaml — Ephemeral Mode

```yaml
execution_mode: ephemeral

ephemeral:
  pool_size: 4          # pre-warmed instances (0 = pure cold boot)
  max_idle_seconds: 120 # release after X seconds of inactivity
  max_concurrent: 8     # max parallelism (backpressure beyond this)
  boot_timeout: 5.0     # instance boot timeout
```

### plugin.yaml — Sandboxed Mode

```yaml
execution_mode: sandboxed

resources:
  timeout_seconds: 10
  max_memory_mb: 256
  max_disk_mb: 100      # disk quota for the subprocess
```

---

## 3. Plugin — Complete Code

### Minimal Import

```python
from xcore.sdk import TrustedBase, ok, error
```

### Base Class

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
        """Called once upon boot. Initialize services here."""
        self.db = self.get_service("db")
        self.cache = self.get_service("cache")
        self.logger.info("plugin loaded", plugin=self.ctx.name)

    async def on_reload(self):
        """Called after a hot reload."""
        await self.on_load()

    async def on_unload(self):
        """Called upon shutdown."""
        self.logger.info("plugin stopped")

    # ── Main Action Handler ──────────────────────────────────────────────────

    async def handle(self, action: str, payload: dict) -> dict:
        if action == "ping":
            return ok(msg="pong")
        if action == "create_user":
            return await self._create_user(payload)
        return error(f"Unknown action: {action}", "unknown_action")
```

### Standardized Responses

```python
from xcore.sdk import ok, error

return ok()                              # {"status": "ok"}
return ok(data={"id": 1})               # {"status": "ok", "data": {"id": 1}}
return ok(user_id=42, name="Alice")     # {"status": "ok", "user_id": 42, "name": "Alice"}

return error("message")                 # {"status": "error", "msg": "message"}
return error("not found", "not_found")  # {"status": "error", "msg": "...", "code": "not_found"}
```

---

## 4. SDK — All Decorators

### @action + AutoDispatchMixin

```python
from xcore.sdk import action, AutoDispatchMixin

class Plugin(AutoDispatchMixin, TrustedBase):
    # AutoDispatchMixin generates handle() automatically

    @action("greet")
    async def greet(self, payload: dict) -> dict:
        return ok(msg=f"Hello {payload.get('name', 'world')}")

    @action("bye")
    async def bye(self, payload: dict) -> dict:
        return ok(msg="Goodbye")
```

### @schema — Validation + Contract Versioning

```python
@action("create_user")
@schema(
    version="2.0",
    input={
        "email": (str, ...),       # required
        "role": (str, "user"),     # optional, defaults to "user"
        "age": (int, ...),         # required
    },
    output={"user_id": int, "created_at": str},
    deprecated_fields={"username": "Removed in v2.0"},
    breaking_since="2.0",
    validate=True,           # automatically validate payload
    type_response="dict",    # "dict" | "model" (Pydantic)
)
async def create_user(self, payload: dict) -> dict:
    return ok(user_id=1, created_at="2026-01-01")
```

### @route — FastAPI HTTP Routes

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

    @route("/admin", method="GET", permissions=["admin"])  # Auto RBAC
    async def admin_endpoint(self):
        return {"secret": True}

    async def handle(self, action, payload):
        return error("unknown action")

# Mounted under /plugins/<plugin_name><path>
```

### @cron and @interval

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

### @on_event and @on_hook

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

    @health_check("my_plugin.db")
    async def check_db(self) -> tuple[bool, str]:
        try:
            await self.get_service("db").execute("SELECT 1")
            return True, "ok"
        except Exception as e:
            return False, str(e)

    @health_check("my_plugin.api", kind="liveness")
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

### @cached and @invalidate

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

### AutoMixin — All-in-One

```python
from xcore.sdk import AutoMixin

class Plugin(AutoMixin):
    """Combines AutoDispatchMixin + EventMixin + HookMixin +
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

## 5. Services — Plugin-level Access

### Accessing Services

```python
async def on_load(self):
    self.db      = self.get_service("db")             # AsyncSQLAdapter
    self.cache   = self.get_service("cache")          # CacheService
    self.mongo   = self.get_service("mongodb")        # MongoDBAdapter
    self.redis   = self.get_service("redisAdapter")   # RedisAdapter
    self.syncdb  = self.get_service("syncdb")         # SQLAdapter (sync)
    svc          = self.get_service_as("my_svc", MyService)  # explicit typing
```

### Databases (AsyncSQL)

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
value = await self.cache.get("key")   # None if absent
await self.cache.delete("key")
```

### Programmatic Scheduler (Advanced Use Cases)

```python
scheduler = self.get_service("scheduler")
await scheduler.add_job(func=self._my_func, trigger="interval", seconds=60, job_id="my_job")
await scheduler.remove_job("my_job")
```

### Repository Pattern

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
    prefix = "session"   # all keys: "session:<key>"

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

## 6. Creating a Custom Service

There are **two ways** to add custom services to XCore.

---

### Method 1 — Extension via integration.yaml (Recommended, Code-Free Core Modification)

The simplest approach. Declare the service under `services.extensions` in `integration.yaml`.
XCore will instantiate it, call `init()`, and trigger `shutdown()` automatically.

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

**The service must inherit from `BaseService`:**

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
        # Connection / warmup
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

    # Custom business methods
    async def send(self, to: str, subject: str, body: str) -> None:
        from email.mime.text import MIMEText
        msg = MIMEText(body, "html")
        msg["Subject"] = subject
        msg["From"] = self.username
        msg["To"] = to
        await self._client.sendmail(self.username, [to], msg.as_string())
```

**Accessing the Service from a Plugin:**

```python
class Plugin(TrustedBase):
    async def on_load(self):
        # Access name pattern is "ext.<declared_name>"
        self.email = self.get_service("ext.email")

    async def handle(self, action, payload):
        if action == "send_welcome":
            await self.email.send(
                to=payload["email"],
                subject="Welcome!",
                body="<h1>Hello there!</h1>",
            )
            return ok()
```

---

### Method 2 — Custom ServiceProvider (DI Container Injection)

For absolute control over initialization or to wire up multiple services simultaneously.

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
        # Register under name "my_custom" in the container
        container.register_service("my_custom", svc)
```

**Wiring up the Provider during Boot:**

```python
# In the app entry point (prior to container.init())
from myapp.providers import MyCustomServiceProvider
container.add_provider(MyCustomServiceProvider())
await container.init()
```

**Or Register Directly (No Provider):**

```python
# Best for lightweight utilities lacking dynamic lifecycles
container.register_service("feature_flags", FeatureFlagClient(url="..."))
```

---

### Method 3 — Registration from a Plugin (Inter-Plugin Shared Service)

A plugin can register a service directly into the shared container for other plugins to consume.

```python
class Plugin(TrustedBase):
    async def on_load(self):
        # Expose its custom HTTP client to the container
        from mylib import HttpClient
        client = HttpClient(base_url="https://api.example.com")
        await client.connect()

        # Save to shared services
        self.ctx.services["http_client"] = client

    async def on_unload(self):
        client = self.ctx.services.pop("http_client", None)
        if client:
            await client.close()
```

**Consuming from another Plugin:**

```python
class OtherPlugin(TrustedBase):
    async def on_load(self):
        # Ensure the provider is loaded beforehand via `requires`
        self.http = self.get_service("http_client")
```

```yaml
# plugin.yaml of OtherPlugin
requires:
  - my-http-provider-plugin  # guarantees load order
```

---

### BaseService Interface Contract Summary

```python
from xcore.services.base import BaseService, ServiceStatus

class MyService(BaseService):
    name = "my_service"   # label shown in status lists and logs

    def __init__(self, config: dict):
        super().__init__()  # sets self._status = ServiceStatus.UNINITIALIZED
        # store configuration

    async def init(self) -> None:
        # Connect, warm up connections, perform handshakes
        # Obligatory: update self._status to ServiceStatus.READY upon completion
        self._status = ServiceStatus.READY

    async def shutdown(self) -> None:
        # Gracefully sever connections
        self._status = ServiceStatus.STOPPED

    async def health_check(self) -> tuple[bool, str]:
        # Return (True, "ok") or (False, "error description")
        return True, "ok"

    def status(self) -> dict:
        # Dictionary rendered by /status and in logs
        return {"name": self.name, "status": self._status.value}

# ServiceStatus State Machine values:
# UNINITIALIZED → INITIALIZING → READY → DEGRADED → STOPPED → FAILED
```

---

### Service Configuration inside integration.yaml

```yaml
services:
  # Multiple Databases — each entry defines a distinct adapter
  databases:
    default:
      type: postgresql+aio       # sqlite | postgresql | mysql | sqlite+aio | postgresql+aio | mongodb | redis
      url: "${DATABASE_URL}"
      pool_size: 10
      max_overflow: 20
      pool_pre_ping: true
      pool_recycle: 1800         # recycle before DB severs (less than MySQL wait_timeout)
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
    ttl: 300                     # default TTL in seconds
    max_size: 1000               # max size for memory backend

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

### Querying Multiple Databases in a Plugin

```yaml
# plugin.yaml — explicit database resource wildcard
permissions:
  - resource: "db.*"
    actions: ["read", "write"]
    effect: allow
```

```python
async def on_load(self):
    # Primary DB (first declared adapter or key "default")
    self.db       = self.get_service("db")

    # Named Database Adapters
    self.analytics = self.get_service("analytics")
    self.mongo     = self.get_service("mongo")
    self.redis     = self.get_service("redis_store")
```

---

## 7. Observability — Core APIs

### Logger

```python
from xcore.kernel.observability import get_logger
logger = get_logger("xcore.my_module")   # structured logger namespace required

self.logger.info("action performed", details="value", id=42)
self.logger.warning("attention needed", plugin="my_plugin")
self.logger.error("action failed", err=str(e))
self.logger.debug("debug message", payload=payload)

# FORBIDDEN
import logging; logging.getLogger("my_plugin")  # unstuctured, bypasses kernel logging hooks
```

### Metrics

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

## 8. Inter-Plugin Calls

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

The `tenant_id` is fetched automatically from the `X-Tenant-ID` header or request subdomain.
Adapters automatically handle prefixing — **no tenant-aware logic required inside plugins**.

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

## 12. Execution Modes Comparison

| | `trusted` | `sandboxed` | `ephemeral` |
|---|---|---|---|
| Process Context | In-process | Isolated Subprocess | In-process (pooled) |
| Service Access | Direct `get_service()` | JSON IPC bridge | Direct `get_service()` |
| Persist State | Yes | Yes (subprocess) | **No** (stateless) |
| Security | Medium | High | Medium |
| Performance | High | Lower (IPC overhead) | High (warm pool) |
| Target Use Cases | Core business domains | Untrusted/3rd-party code | Stateless VFs |

---

## 13. Critical Gotchas

```python
# FORBIDDEN — standard logger, lacks structured formats
import logging; logging.getLogger("my_plugin")

# FORBIDDEN — multi-tenant race condition
self.current_tenant = tenant_id

# FORBIDDEN — bound method → Redis serialization/pickle fails
scheduler.add_job(self.my_method, ...)

# CORRECT — scheduler decorator pattern
@cron("0 3 * * *")
async def nightly(self): ...

# CORRECT — patch the original SOURCE module inside test suites
@patch("xcore.services.container.ServiceContainer.get")  # ✓
@patch("xcore.ServiceContainer.get")                      # ✗

# CORRECT — utilize structured logs
from xcore.kernel.observability import get_logger
logger = get_logger("xcore.my_plugin")
logger.info("action performed", user_id=42)  # kwargs, never f-strings
```

---

## 14. Testing Patterns

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
    from app.plugins.my_plugin.src.main import Plugin
    p = Plugin()
    p._ctx = MagicMock()
    p._ctx.services = {"db": mock_db, "cache": AsyncMock()}
    p._ctx.name = "my-plugin"
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

Environment variables required for testing:
```bash
DATABASE_URL=sqlite:///./test.db
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=test-secret-key
```

`asyncio_mode = auto` → do not add `@pytest.mark.asyncio` manually. Target coverage `fail_under = 80` (branch).

---

## 15. HTTP Flow → Plugin

```
HTTP Request
  └─ TenantMiddleware       (extracts X-Tenant-ID, binds ContextVar)
       └─ Router            (/plugins/{name}/{action})
            └─ supervisor.call(name, action, payload)
                 └─ IPCAuthMiddleware
                      └─ TracingMiddleware    (span extraction + context propagation)
                           └─ RateLimitMiddleware
                                └─ PermissionMiddleware
                                     └─ RetryMiddleware
                                          └─ handler.call(action, payload)
                                               └─ Plugin.handle(action, payload)
```

---

## 16. Out-of-the-Box System Endpoints

| Endpoint | Description |
|---|---|
| `GET /status` | Check state of all loaded plugins |
| `POST /plugins/{name}/reload` | Hot-reload specific plugin without restart |
| `POST /plugins/{name}/load` | Boot up specific plugin |
| `POST /plugins/{name}/unload` | Shut down specific plugin |
| `GET /metrics` | Exposes Prometheus formats |
| `GET /health` | Fetch report of all health checks |
| `GET /health/live` | Liveness indicator (k8s probe) |
| `GET /health/ready` | Readiness indicator (k8s probe) |
| `POST /plugins/{name}/{action}` | Invoke action handler directly |

---

## 17. Quick Imports Index

```python
# Base
from xcore.sdk import TrustedBase, ok, error

# Dispatch
from xcore.sdk import action, AutoDispatchMixin, AutoMixin

# HTTP
from xcore.sdk import route, RoutedPlugin

# Schemas
from xcore.sdk import schema, validate_payload

# Scheduler
from xcore.sdk import cron, interval, ScheduledMixin

# Events
from xcore.sdk import on_event, on_hook, EventMixin, HookMixin, Event

# Observability
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

# Custom Services
from xcore.services.base import BaseService, BaseServiceProvider, ServiceStatus
from xcore.services.container import ServiceContainer

# Execution Modes
from xcore.sdk import ExecutionMode  # trusted, sandboxed, ephemeral

# Errors
from xcore.sdk import PermissionDenied
```
