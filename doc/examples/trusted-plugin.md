# Example: Trusted Plugin

A full-featured `trusted` plugin with database access, HTTP routes, IPC, and a Celery task.

---

## Directory Structure

```
plugins/users/
├── plugin.yaml
├── plugin.sig          # sign with: xcore plugin sign plugins/users
└── src/
    └── main.py
```

---

## `plugin.yaml`

```yaml
name: users
version: "2.0.0"
author: "XCore Team"
description: "User management plugin"
execution_mode: trusted
entry_point: src/main.py
framework_version: ">=2.0"

requires:
  - name: auth_plugin
    version: ">=1.0"

permissions:
  - resource: "db.users"
    actions: ["read", "write", "delete"]
    effect: allow
  - resource: "cache.*"
    actions: ["read", "write"]
    effect: allow

allowed_callers:
  - auth_plugin
  - dashboard_plugin

resources:
  rate_limit:
    calls: 100
    period_seconds: 60
```

---

## `src/main.py`

```python
from __future__ import annotations

from xcore import TrustedBase
from xcore.sdk.decorators import action, schema, validate_payload
from xcore.sdk.mixin.ipc import AutoDispatchMixin
from xcore.kernel.api.contract import ok, error
from pydantic import BaseModel, EmailStr

# ── Payload models ────────────────────────────────────────────────────────

class CreateUserPayload(BaseModel):
    name: str
    email: str
    role: str = "user"

class GetUserPayload(BaseModel):
    user_id: int

# ── Plugin ────────────────────────────────────────────────────────────────

class Plugin(AutoDispatchMixin, TrustedBase):

    # ── Lifecycle ──────────────────────────────────────────────────────────

    async def on_load(self) -> None:
        self.db     = self.get_service("db")
        self.cache  = self.get_service("cache")
        self.worker = self.get_service("worker")
        self.logger = self.ctx.get_logger("users")

    # ── Actions ────────────────────────────────────────────────────────────

    @action("create")
    @schema(
        "1.0",
        input={"name": (str, ...), "email": (str, ...), "role": (str, "user")},
        output={"user_id": (int, ...), "name": (str, ...)},
        description="Create a new user account.",
    )
    @validate_payload(CreateUserPayload)
    async def create_user(self, payload: CreateUserPayload) -> dict:
        async with self.db.session() as session:
            # Check for duplicate email
            from sqlalchemy import select, text
            exists = await session.execute(
                text("SELECT id FROM users WHERE email = :email"),
                {"email": payload.email},
            )
            if exists.fetchone():
                return error("Email already in use", "duplicate_email")

            # Insert user
            result = await session.execute(
                text("INSERT INTO users (name, email, role) VALUES (:n, :e, :r) RETURNING id"),
                {"n": payload.name, "e": payload.email, "r": payload.role},
            )
            user_id = result.scalar_one()
            await session.commit()

        # Dispatch welcome email via Celery
        self.worker.send("app.tasks.emails.send_welcome", user_id, payload.email, queue="emails")

        # Publish event for other plugins
        await self.ctx.events.publish("user.created", {"user_id": user_id, "email": payload.email})

        self.logger.info("User created: id=%d email=%s", user_id, payload.email)
        return ok(user_id=user_id, name=payload.name)

    @action("get")
    @validate_payload(GetUserPayload)
    async def get_user(self, payload: GetUserPayload) -> dict:
        cache_key = f"user:{payload.user_id}"

        cached = await self.cache.get(cache_key)
        if cached:
            return ok(**cached)

        async with self.db.session() as session:
            from sqlalchemy import text
            row = await session.execute(
                text("SELECT id, name, email, role FROM users WHERE id = :id"),
                {"id": payload.user_id},
            )
            user = row.fetchone()

        if not user:
            return error("User not found", "not_found")

        data = {"user_id": user.id, "name": user.name, "email": user.email, "role": user.role}
        await self.cache.set(cache_key, data, ttl=300)
        return ok(**data)

    @action("delete")
    async def delete_user(self, payload: dict) -> dict:
        user_id = payload.get("user_id")
        if not user_id:
            return error("user_id required", "missing_field")

        async with self.db.session() as session:
            from sqlalchemy import text
            await session.execute(
                text("DELETE FROM users WHERE id = :id"), {"id": user_id}
            )
            await session.commit()

        await self.cache.delete(f"user:{user_id}")
        await self.ctx.events.publish("user.deleted", {"user_id": user_id})
        return ok(deleted=True)

    # ── IPC ────────────────────────────────────────────────────────────────

    @action("notify_auth")
    async def notify_auth(self, payload: dict) -> dict:
        """Call auth_plugin to register a new session after user creation."""
        return await self.call_plugin("auth_plugin", "create_session", {
            "user_id": payload["user_id"],
            "role": payload.get("role", "user"),
        })

    # ── HTTP routes ────────────────────────────────────────────────────────

    def get_router(self):
        from fastapi import APIRouter, HTTPException

        router = APIRouter(prefix="/v1", tags=["users"])

        @router.get("/{user_id}")
        async def get_user_http(user_id: int):
            result = await self.get_user({"user_id": user_id})
            if result.get("status") == "error":
                raise HTTPException(status_code=404, detail=result["msg"])
            return result

        @router.post("/")
        async def create_user_http(body: CreateUserPayload):
            result = await self.create_user(body)
            if result.get("status") == "error":
                raise HTTPException(status_code=400, detail=result["msg"])
            return result

        return router
```

---

## Sign the plugin

```bash
poetry run xcore plugin sign plugins/users --secret "your-hmac-secret"
```

---

## Test

```bash
# Create a user
curl -X POST http://localhost:8000/app/users/action \
     -H "Content-Type: application/json" \
     -d '{"action": "create", "payload": {"name": "Alice", "email": "alice@example.com"}}'

# Get via HTTP route
curl http://localhost:8000/app/users/v1/1
```
