# Quick Start

Build your first XCore application and plugin in **5 minutes**.

```mermaid
flowchart LR
    S1["① Configure\nintegration.yaml"] --> S2["② Entry point\nmain.py"]
    S2 --> S3["③ First plugin\nplugin.yaml + src/main.py"]
    S3 --> S4["④ Run & test\ncurl / CLI"]

    style S1 fill:#E3F2FD,stroke:#1976D2
    style S2 fill:#E8F5E9,stroke:#388E3C
    style S3 fill:#FFF3E0,stroke:#F57C00
    style S4 fill:#FCE4EC,stroke:#C62828
```

---

## ① Configure

Create `integration.yaml` at the project root:

```yaml title="integration.yaml"
app:
  name: "my-app"
  env: development
  debug: true
  secret_key: "change-me-in-production" # (1)!
  plugin_prefix: "/app"                 # (2)!

plugins:
  directory: ./plugins                  # (3)!
  secret_key: "change-me-in-production"
  strict_trusted: false
  entry_point: src/main.py             # (4)!

services:
  databases:
    db:
      type: sqlasync
      url: sqlite+aiosqlite:///./app.db # (5)!
  cache:
    backend: memory                     # (6)!
    ttl: 300
```

1. Used to authenticate system API calls. **Must be changed in production.**
2. All plugin routes are mounted under `/app/<plugin_name>/`.
3. XCore discovers plugins by scanning subdirectories of this folder.
4. Default entry point inside each plugin folder.
5. SQLite with async support — no setup required for dev.
6. In-memory cache. Switch to `redis` for production.

---

## ② Entry point

```python title="main.py" hl_lines="8 12 15"
from contextlib import asynccontextmanager
from fastapi import FastAPI
from xcore import Xcore

xcore = Xcore(config_path="integration.yaml")  # (1)!

@asynccontextmanager
async def lifespan(app: FastAPI):
    await xcore.boot(app)   # (2)!
    yield
    await xcore.shutdown()  # (3)!

app = FastAPI(**xcore._config.app.fastapi.to_dict(), lifespan=lifespan)
xcore.setup(app)            # (4)!
```

1. Loads `integration.yaml`, parses config, prepares subsystems.
2. Starts services → registry → plugins → mounts routes. Everything in order.
3. Graceful teardown: plugins → services, in reverse order.
4. Registers ASGI middlewares. **Must be called before uvicorn starts.**

!!! warning "Order matters"
    `xcore.setup(app)` must be called **after** `FastAPI()` and **before** the server starts.
    Calling it inside `lifespan` is too late — FastAPI locks middleware after startup.

---

## ③ First plugin

```
plugins/
└── hello/             ← plugin directory
    ├── plugin.yaml    ← manifest
    └── src/
        └── main.py    ← plugin code
```

=== "plugin.yaml"

    ```yaml title="plugins/hello/plugin.yaml"
    name: hello          # (1)!
    version: "1.0.0"
    author: me
    description: Demo plugin
    execution_mode: trusted   # (2)!
    entry_point: src/main.py

    permissions:
      - resource: "cache.*"
        actions: ["read", "write"]
        effect: allow
    ```

    1. Must be unique across all plugins.
    2. Runs in the main FastAPI process. Full service access.

=== "src/main.py"

    ```python title="plugins/hello/src/main.py"
    from xcore import TrustedBase
    from xcore.sdk.decorators import action, validate_payload
    from xcore.sdk.mixin.ipc import AutoDispatchMixin  # (1)!
    from xcore.kernel.api.contract import ok, error
    from pydantic import BaseModel

    class GreetPayload(BaseModel):
        name: str

    class Plugin(AutoDispatchMixin, TrustedBase):  # (2)!

        async def on_load(self) -> None:           # (3)!
            self.cache = self.get_service("cache")

        @action("ping")                            # (4)!
        async def ping(self, payload: dict) -> dict:
            return ok(pong=True)

        @action("greet")
        @validate_payload(GreetPayload)            # (5)!
        async def greet(self, payload: GreetPayload) -> dict:
            cached = await self.cache.get(f"greet:{payload.name}")
            if cached:
                return ok(message=cached, from_cache=True)

            msg = f"Hello, {payload.name}!"
            await self.cache.set(f"greet:{payload.name}", msg, ttl=60)
            return ok(message=msg)
    ```

    1. Auto-generates `handle()` by routing action strings to `@action` methods.
    2. Inherits full kernel context injection from `TrustedBase`.
    3. Called after context injection — services are available here.
    4. Maps `handle("ping", {})` → `self.ping({})`.
    5. Validates the payload with Pydantic before calling the method.

---

## ④ Run and test

```bash
# Start the server
make dev
# or: poetry run uvicorn main:app --reload
```

=== "curl"

    ```bash
    # Ping
    curl -X POST http://localhost:8000/app/hello/action \
         -H "Content-Type: application/json" \
         -d '{"action": "ping", "payload": {}}'
    # → {"status": "ok", "pong": true}

    # Greet
    curl -X POST http://localhost:8000/app/hello/action \
         -H "Content-Type: application/json" \
         -d '{"action": "greet", "payload": {"name": "Dev"}}'
    # → {"status": "ok", "message": "Hello, Dev!"}

    # Second call — served from cache
    curl -X POST http://localhost:8000/app/hello/action \
         -H "Content-Type: application/json" \
         -d '{"action": "greet", "payload": {"name": "Dev"}}'
    # → {"status": "ok", "message": "Hello, Dev!", "from_cache": true}
    ```

=== "CLI"

    ```bash
    # List all loaded plugins
    poetry run xcore plugin list

    # Inspect a plugin
    poetry run xcore plugin info hello

    # Hot-reload after editing src/main.py
    poetry run xcore plugin reload hello
    ```

=== "Python (httpx)"

    ```python
    import httpx

    BASE = "http://localhost:8000/app/hello/action"

    with httpx.Client() as client:
        r = client.post(BASE, json={"action": "ping", "payload": {}})
        print(r.json())  # {"status": "ok", "pong": True}

        r = client.post(BASE, json={"action": "greet", "payload": {"name": "Dev"}})
        print(r.json())  # {"status": "ok", "message": "Hello, Dev!"}
    ```

---

## What happens at boot

```mermaid
sequenceDiagram
    participant U as uvicorn
    participant X as Xcore Engine
    participant S as ServiceContainer
    participant P as PluginSupervisor
    participant H as Plugin hello

    U->>X: boot(app)
    X->>S: init DB + cache
    S-->>X: ✅ ready

    X->>P: boot()
    P->>P: discover plugins/hello/
    P->>P: parse plugin.yaml
    P->>H: instantiate Plugin class
    H->>H: on_init()
    H->>H: on_load() — get_service("cache")
    H-->>P: ✅ READY

    P->>U: mount routes under /app/
    U-->>U: 🚀 serving on :8000
```

---

## Plugin lifecycle hooks

```python title="All available lifecycle hooks"
class Plugin(AutoDispatchMixin, TrustedBase):

    async def on_init(self) -> None:
        """Before context injection. No services yet."""

    async def on_load(self) -> None:
        """After injection. Services available. Most setup goes here."""
        self.db = self.get_service("db")

    async def on_start(self) -> None:
        """Server is fully ready and accepting requests."""

    async def on_reload(self) -> None:
        """Called after a hot-reload (file changed)."""

    async def on_stop(self) -> None:
        """Server is shutting down."""

    async def on_unload(self) -> None:
        """Plugin is being removed. Release resources."""
```

---

## Next steps

=== "Add a database"

    ```yaml title="integration.yaml"
    services:
      databases:
        db:
          type: sqlasync
          url: postgresql+asyncpg://user:pass@localhost/mydb
    ```

    ```python title="plugin src/main.py"
    async def on_load(self):
        self.db = self.get_service("db")   # → AsyncSQLAdapter

    @action("get_user")
    async def get_user(self, payload: dict) -> dict:
        async with self.db.session() as session:
            from sqlalchemy import text
            row = await session.execute(
                text("SELECT id, name FROM users WHERE id = :id"),
                {"id": payload["user_id"]}
            )
            user = row.fetchone()
            return ok(id=user.id, name=user.name) if user else error("Not found", "not_found")
    ```

=== "Add HTTP routes"

    ```python title="plugin src/main.py"
    def get_router(self):
        from fastapi import APIRouter
        router = APIRouter(prefix="/v1", tags=["hello"])

        @router.get("/greet/{name}")
        async def greet_http(name: str):
            result = await self.greet({"name": name})
            return result

        return router
    # Mounted automatically at /app/hello/v1/greet/{name}
    ```

=== "Add background tasks"

    ```yaml title="integration.yaml"
    services:
      xworker:
        enabled: true
        broker_url: redis://localhost:6379/0
        result_backend: redis://localhost:6379/1
        modules:
          - app.tasks.jobs
    ```

    ```python title="app/tasks/jobs.py"
    from xcore.services.xworker.registry import task

    @task(queue="default")
    def send_email(to: str, subject: str) -> dict:
        # Runs in a Celery worker process
        return {"sent": True}
    ```

    ```python title="plugin src/main.py"
    async def on_load(self):
        self.worker = self.get_service("worker")

    @action("notify")
    async def notify(self, payload: dict) -> dict:
        self.worker.send("app.tasks.jobs.send_email", payload["email"], "Welcome!")
        return ok(queued=True)
    ```

| Goal | Doc |
|:-----|:----|
| Full plugin authoring | [Creating a Plugin](../guides/creating-plugins.md) |
| All services | [Services](../guides/services.md) |
| Security & sandboxing | [Security](../guides/security.md) |
| Multi-tenancy | [Multi-Tenancy](../guides/tenancy.md) |
| Internals | [Architecture](../architecture/overview.md) |
