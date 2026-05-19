# Services

XCore provides five shared services via `ServiceContainer`. All are accessible from any `TrustedBase` plugin via `self.get_service(name)`.

```mermaid
flowchart LR
    subgraph Container["ServiceContainer"]
        DB["🗄️  Database\nget('db')\nget('analytics')"]
        CACHE["⚡ Cache\nget('cache')"]
        SCHED["⏰ Scheduler\nget('scheduler')"]
        WORKER["🔄 Worker\nget('worker')"]
        EXT["🔌 Extensions\nget('ext.email')"]
    end

    Plugin["Plugin\n(TrustedBase)"] -- "self.get_service()" --> Container
    Container -- "sqlasync / sql / mongodb / redis" --> DB
    Container -- "redis / memory" --> CACHE
    Container -- "APScheduler" --> SCHED
    Container -- "Celery" --> WORKER
    Container -- "custom class" --> EXT

    style Container fill:#E3F2FD,stroke:#1976D2
    style Plugin fill:#E8F5E9,stroke:#388E3C
```

Init order: `database → cache → scheduler → xworker → extensions`

---

## Service Container

```python title="Service access from a plugin"
async def on_load(self):
    # Standard typed keys (IDE autocomplete + mypy infer the return type)
    self.db        = self.get_service("db")        # → AsyncSQLAdapter
    self.cache     = self.get_service("cache")     # → CacheService
    self.scheduler = self.get_service("scheduler") # → SchedulerService
    self.worker    = self.get_service("worker")    # → WorkerService

    # Named connection with explicit type
    from xcore.services.database.adapters.async_sql import AsyncSQLAdapter
    self.analytics = self.get_service_as("analytics", AsyncSQLAdapter)

    # Safe optional access — returns None if not configured
    self.redis = self.ctx.services.get_or_none("redis_db")
```

---

## Database

### Configuration

=== "SQLite (dev)"

    ```yaml title="integration.yaml"
    services:
      databases:
        db:
          type: sqlasync
          url: sqlite+aiosqlite:///./app.db
          echo: false
    ```

=== "PostgreSQL"

    ```yaml title="integration.yaml"
    services:
      databases:
        db:
          type: sqlasync
          url: postgresql+asyncpg://user:pass@localhost/mydb
          pool_size: 5
          max_overflow: 10
          echo: false

        analytics:                   # named second connection
          type: sqlasync
          url: postgresql+asyncpg://user:pass@analytics-host/metrics
    ```

=== "MongoDB"

    ```yaml title="integration.yaml"
    services:
      databases:
        mongo:
          type: mongodb
          url: mongodb://localhost:27017/mydb
    ```

=== "Redis (as DB)"

    ```yaml title="integration.yaml"
    services:
      databases:
        redis_db:
          type: redis
          url: redis://localhost:6379/0
          max_connections: 50
    ```

### Usage — AsyncSQLAdapter

```mermaid
sequenceDiagram
    participant P as Plugin
    participant A as AsyncSQLAdapter
    participant DB as Database

    P->>A: async with self.db.session() as session
    A->>DB: open connection from pool
    P->>DB: session.execute(query)
    DB-->>P: result rows
    P->>DB: session.commit()
    A->>DB: return connection to pool
```

=== "Insert"

    ```python
    @action("create_user")
    @validate_payload(CreateUserPayload)
    async def create_user(self, payload: CreateUserPayload) -> dict:
        async with self.db.session() as session:
            from sqlalchemy import text
            result = await session.execute(
                text("INSERT INTO users (name, email) VALUES (:n, :e) RETURNING id"),
                {"n": payload.name, "e": payload.email},
            )
            user_id = result.scalar_one()
            await session.commit()
        return ok(user_id=user_id)
    ```

=== "Select"

    ```python
    @action("get_user")
    async def get_user(self, payload: dict) -> dict:
        async with self.db.session() as session:
            from sqlalchemy import text
            row = await session.execute(
                text("SELECT id, name, email FROM users WHERE id = :id"),
                {"id": payload["user_id"]},
            )
            user = row.fetchone()
        if not user:
            return error("User not found", "not_found")
        return ok(id=user.id, name=user.name, email=user.email)
    ```

=== "ORM (SQLAlchemy)"

    ```python
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
    from sqlalchemy import String

    class Base(DeclarativeBase): pass

    class User(Base):
        __tablename__ = "users"
        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str] = mapped_column(String(100))
        email: Mapped[str] = mapped_column(String(200), unique=True)

    @action("list_users")
    async def list_users(self, payload: dict) -> dict:
        from sqlalchemy import select
        async with self.db.session() as session:
            result = await session.execute(select(User).limit(50))
            users = result.scalars().all()
        return ok(users=[{"id": u.id, "name": u.name} for u in users])
    ```

---

## Cache

### Configuration

=== "Redis (production)"

    ```yaml title="integration.yaml"
    services:
      cache:
        backend: redis
        url: redis://localhost:6379/0
        ttl: 300
    ```

=== "Memory (dev)"

    ```yaml title="integration.yaml"
    services:
      cache:
        backend: memory
        ttl: 300
        max_size: 10000
    ```

### Cache hit / miss flow

```mermaid
flowchart TD
    R["Request\nget_user(user_id=42)"] --> K["Build key\n'user:42'"]
    K --> C{Cache\nhit?}
    C -- "✅ hit" --> RET1["return ok(**cached)\nfrom_cache=True"]
    C -- "❌ miss" --> DB["Query database"]
    DB --> STORE["cache.set(key, data, ttl=300)"]
    STORE --> RET2["return ok(**data)"]

    style RET1 fill:#E8F5E9,stroke:#388E3C
    style DB fill:#FFF3E0,stroke:#F57C00
```

### Usage

=== "get / set / delete"

    ```python
    async def on_load(self):
        self.cache = self.get_service("cache")

    @action("get_profile")
    async def get_profile(self, payload: dict) -> dict:
        user_id = payload["user_id"]
        key = f"profile:{user_id}"

        # Try cache first
        cached = await self.cache.get(key)
        if cached:
            return ok(**cached, from_cache=True)

        # Miss → fetch from DB
        async with self.db.session() as session:
            ...
            data = {"id": user_id, "name": "Alice"}

        await self.cache.set(key, data, ttl=120)
        return ok(**data)

    @action("invalidate")
    async def invalidate(self, payload: dict) -> dict:
        await self.cache.delete(f"profile:{payload['user_id']}")
        return ok()
    ```

=== "Multi-tenancy aware"

    When `tenancy.isolate_cache: true`, keys are automatically prefixed.
    No code change needed in the plugin.

    ```
    # Tenant "acme" calls cache.set("invoices", data)
    # Stored as: "acme:invoices"

    # Tenant "beta" calls cache.get("invoices")
    # Reads:   "beta:invoices"  ← completely isolated
    ```

---

## Scheduler

### Configuration

```yaml title="integration.yaml"
services:
  scheduler:
    enabled: true
    backend: redis       # redis = persistent across restarts
    timezone: Europe/Paris

    jobs:                # static jobs declared upfront
      - id: daily_cleanup
        func: myapp.tasks.maintenance:cleanup
        trigger: cron
        hour: 2
        minute: 0
```

### Usage

=== "Add a job"

    ```python
    @action("schedule_report")
    async def schedule_report(self, payload: dict) -> dict:
        job_id = f"report:{payload['user_id']}"

        self.scheduler.add_job(
            func="myapp.tasks.reports:generate",
            trigger="interval",
            minutes=30,
            id=job_id,
            kwargs={"user_id": payload["user_id"]},
            replace_existing=True,
        )
        return ok(job_id=job_id)
    ```

=== "Cron trigger"

    ```python
    self.scheduler.add_job(
        func="myapp.tasks.billing:monthly_invoice",
        trigger="cron",
        day=1,       # 1st of every month
        hour=0,
        minute=0,
        id="monthly_invoice",
    )
    ```

=== "Cancel a job"

    ```python
    @action("cancel_job")
    async def cancel_job(self, payload: dict) -> dict:
        self.scheduler.remove_job(payload["job_id"])
        return ok(cancelled=True)
    ```

---

## XWorker (Celery) {#xworker-celery}

XWorker wraps Celery for distributed background tasks. Ideal for long-running operations, email sending, report generation, and anything that shouldn't block an HTTP response.

### Architecture

```mermaid
flowchart LR
    subgraph App["FastAPI App"]
        P["Plugin\nself.worker.send(...)"]
    end

    subgraph Queue["Message Broker\n(Redis)"]
        Q1["queue: default"]
        Q2["queue: emails"]
        Q3["queue: reports"]
    end

    subgraph Workers["Celery Workers"]
        W1["Worker 1"]
        W2["Worker 2"]
        W3["Worker 3"]
    end

    RB[("Result Backend\n(Redis)")]

    P -- "send task" --> Q1 & Q2 & Q3
    Q1 --> W1
    Q2 --> W2
    Q3 --> W3
    W1 & W2 & W3 -- "store result" --> RB
    P -- "get_result(task_id)" --> RB
```

### Configuration

```yaml title="integration.yaml"
services:
  xworker:
    enabled: true
    name: my-app
    broker_url: redis://localhost:6379/0
    result_backend: redis://localhost:6379/1
    task_default_queue: default
    concurrency: 4
    task_soft_time_limit: 300    # SoftTimeLimitExceeded at 5 min
    task_time_limit: 360         # hard kill at 6 min
    result_expires: 86400        # 24h

    queues:
      - default
      - emails
      - reports

    modules:
      - app.tasks.emails          # (1)!
      - app.tasks.reports
```

1. Python modules containing `@task()` definitions — auto-imported when the service starts.

### Define tasks

```python title="app/tasks/emails.py"
from xcore.services.xworker.registry import task

@task(queue="emails")              # (1)!
def send_welcome_email(user_id: int, email: str) -> dict:
    # Runs in a Celery worker process — no FastAPI context
    print(f"Sending welcome email to {email}")
    return {"sent": True, "to": email}

@task(queue="reports", bind=True)  # (2)!
def generate_report(self, user_id: int) -> dict:
    try:
        # ... heavy computation ...
        return {"report_url": f"/reports/{user_id}.pdf"}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60, max_retries=3)
```

1. `@task(queue=...)` registers the task in a pending list, bound to the Celery app at service init.
2. `bind=True` gives access to `self` — used for retry logic.

### Dispatch from a plugin

=== "Fire and forget"

    ```python
    async def on_load(self):
        self.worker = self.get_service("worker")

    @action("register")
    async def register(self, payload: dict) -> dict:
        user_id = await self._create_user(payload)

        # Dispatch — returns immediately
        self.worker.send(
            "app.tasks.emails.send_welcome_email",
            user_id,
            payload["email"],
            queue="emails",
        )
        return ok(user_id=user_id)
    ```

=== "Async result tracking"

    ```python
    @action("generate_report")
    async def generate_report(self, payload: dict) -> dict:
        result = self.worker.send(
            "app.tasks.reports.generate_report",
            payload["user_id"],
            queue="reports",
        )
        return ok(task_id=result.id)

    @action("check_report")
    async def check_report(self, payload: dict) -> dict:
        result = self.worker.get_result(payload["task_id"])
        return ok(
            task_id=payload["task_id"],
            ready=result.ready(),
            result=result.result if result.ready() else None,
            failed=result.failed(),
        )
    ```

### CLI

```bash
# Start a Celery worker
poetry run xcore worker start celery

# Custom concurrency
poetry run xcore worker start celery --concurrency 8

# Start beat (periodic tasks)
poetry run xcore worker beat

# Inspect running workers
poetry run xcore worker inspect
```

---

## Extensions

Extensions are custom services (email, SMS, etc.) loaded at startup from any Python class that extends `BaseService`.

### Configuration

```yaml title="integration.yaml"
services:
  extensions:
    email:
      module: extensions.email.service:EmailService
      config:
        smtp_host: smtp.gmail.com
        smtp_port: 587
        smtp_user: ${SMTP_USER}           # ${VAR} substitution
        smtp_password: ${SMTP_PASSWORD}
        from_address: noreply@example.com
        use_tls: true
```

### Implementing an extension

```python title="extensions/email/service.py"
from xcore.services.base import BaseService, ServiceStatus

class EmailService(BaseService):

    def __init__(self, config: dict) -> None:
        super().__init__()
        self._cfg = config

    async def init(self) -> None:
        # Connect to SMTP, validate credentials, etc.
        self._status = ServiceStatus.READY

    async def shutdown(self) -> None:
        self._status = ServiceStatus.STOPPED

    async def health_check(self) -> tuple[bool, str]:
        return True, f"SMTP {self._cfg['smtp_host']} reachable"

    async def send(self, to: str, subject: str, body: str) -> None:
        import smtplib
        ...
```

### Usage from a plugin

```python
async def on_load(self):
    self.email = self.get_service("ext.email")

@action("notify")
async def notify(self, payload: dict) -> dict:
    await self.email.send(
        to=payload["email"],
        subject="Your account is ready",
        body="Welcome to XCore!",
    )
    return ok()
```
