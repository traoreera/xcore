---
title: Advanced User Management
description: A complete production-ready example integrating DB Models, Pydantic Schemas, Cache, Events, XWorker, and Scheduler.
icon: material/manage-accounts
---

# Advanced User Management

This example demonstrates a full-featured **Trusted** plugin. It goes beyond simple handlers to show how to structure **SQLAlchemy Models**, **Pydantic Schemas**, and **Automated Tasks** (Scheduler) within a single isolated module.

---

### 1. The Manifest (`plugin.yaml`)

We request access to all necessary subsystems, including the `scheduler` for background maintenance.

```yaml linenums="1"
name: "user_manager"
version: "2.5.0"
execution_mode: "trusted"

permissions:
  - resource: "db.users"
    actions: ["read", "write"]
  - resource: "cache.sessions"
    actions: ["*"]
  - resource: "service:worker"
    actions: ["execute"]
  - resource: "service:scheduler"  # (1)!
    actions: ["*"]
  - resource: "events:user.*"
    actions: ["emit"]
```

1.  Granting full control over the scheduler to register internal maintenance jobs.

---

### 2. Data Models & Schemas

To keep the plugin organized, we define our data structures using standard Python libraries supported by Xcore.

#### SQLAlchemy Model (`src/models.py`)
```python linenums="1"
from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
```

#### Pydantic Schema (`src/schemas.py`)
```python linenums="1"
from pydantic import BaseModel, EmailStr, Field

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
```

---

### 3. Implementation (`src/main.py`)

The plugin implementation now includes **validation**, **persistence**, and **scheduling**.

```python linenums="1"
from fastapi import APIRouter, Depends, status
from sqlalchemy import text, select
from xcore import TrustedBase, ok, error
from .models import User
from .schemas import UserCreate

class Plugin(TrustedBase):
    async def on_load(self):
        # Resolve services
        self.db = self.get_service("db")
        self.cache = self.get_service("cache")
        self.worker = self.get_service("worker")
        self.scheduler = self.get_service("scheduler")

    async def on_start(self):
        # (1) Register a background maintenance job
        @self.scheduler.interval(hours=24)
        async def daily_user_report():
            async with self.db.session() as session:
                count = await session.scalar(select(func.count(User.id)))
                print(f"Daily Report: {count} total users for tenant {self.ctx.tenant_id}")

    def get_router(self) -> APIRouter:
        router = APIRouter(prefix="/v2")

        @router.post("/register", status_code=status.HTTP_201_CREATED)
        async def register_user(user_in: UserCreate): # (2) Automatic Pydantic Validation
            # 1. Database Persistence
            async with self.db.session() as session:
                new_user = User(username=user_in.username, email=user_in.email)
                session.add(new_user)
                await session.flush()
                user_id = new_user.id

            # 2. Asynchronous Notifications
            self.ctx.events.emit_sync("user.created", {"id": user_id})
            self.worker.send("tasks.email:send_welcome", user_in.email)

            return ok(user_id=user_id)

        return router

    async def handle(self, action, payload):
        if action == "get_count":
            async with self.db.session() as session:
                count = await session.scalar(select(func.count(User.id)))
                return ok(count=count)
        return error("Action not found")
```

---

### 4. Architecture Deep Dive

#### Pydantic Integration
By using `UserCreate` in the FastAPI route, Xcore (via FastAPI) automatically performs request validation. If the email is invalid, a `422 Unprocessable Entity` is returned before the plugin code even runs.

#### Automated Scheduling
The `@self.scheduler.interval` decorator in `on_start` ensures that every tenant running this plugin has its own daily report job. Because Xcore multi-tenancy is active, the `self.db` call inside the job is automatically scoped to the correct tenant.

#### Dependency Waves
This plugin is loaded in **Wave 1** if it requires `db` and `cache` (which are initialized in Wave 0). This ensures all services are `READY` before the scheduler tries to start the maintenance job.

---

### 5. Integration Testing

```python linenums="1"
@pytest.mark.asyncio
async def test_complete_flow(xcore_app):
    client = AsyncClient(app=xcore_app, base_url="http://test")

    # 1. Test Validation
    bad_res = await client.post("/plugin/user_manager/v2/register", json={"email": "not-an-email"})
    assert bad_res.status_code == 422

    # 2. Test Success
    res = await client.post(
        "/plugin/user_manager/v2/register",
        json={"username": "alice", "email": "alice@xcore.dev"},
        headers={"X-Tenant-ID": "test_tenant"}
    )
    assert res.status_code == 201

    # 3. Test Scheduler Presence
    jobs = xcore_app.services.get("scheduler").jobs()
    assert any("daily_user_report" in j["id"] for j in jobs)
```

---

### See Also

[Scheduler Service](../services/scheduler.md)
:   Full reference for cron and interval jobs.

[Database Services](../services/database.md)
:   Working with SQLAlchemy models and sessions.

[Multi-Tenancy](../advanced/multi-tenancy.md)
:   Understanding how the scheduler remains tenant-aware.
