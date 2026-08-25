---
title: Demo Plugin
description: Canonical reference plugin exercising every xcoreSDK capability in a single class.
icon: material/flask
---

# Demo Plugin

The demo plugin at `plugins/demo/` exercises every capability xcoreSDK provides. It is the canonical reference for how to compose mixins, decorators, and adapters in a single plugin.

---

## Structure

```
plugins/demo/
├── plugin.yaml
└── src/
    └── main.py
```

---

## Manifest

```yaml title="plugins/demo/plugin.yaml"
name: demo
version: 1.0.0
execution_mode: trusted

env:
  DEMO_SECRET: ""
  DEMO_MAX_USERS: "100"

resources:
  timeout_seconds: 15
  rate_limit:
    requests: 200
    window_seconds: 60

runtime:
  health_check: true
  retry:
    max_attempts: 2
    backoff_seconds: 1.0
```

---

## Base class and imports

```python title="plugins/demo/src/main.py"
from xcore.sdk import (
    AutoMixin,
    BaseAsyncRepository,
    Event,
    action, cached, counted, cron, error, health_check,
    interval, invalidate, ok, on_event, on_hook,
    require_service, route, sandboxed, timed, traced, trusted, validate_payload,
)
```

`AutoMixin` bundles all mixins. The rest are decorators and utilities.

---

## Pydantic schemas

```python
from pydantic import BaseModel, Field

class CreateUserSchema(BaseModel):
    name: str = Field(..., min_length=2, max_length=64)
    email: str = Field(..., pattern=r".+@.+\..+")
    role: str = Field(default="user")

class UpdateUserSchema(BaseModel):
    name: str | None = Field(default=None, min_length=2)
    role: str | None = None
```

Schemas are passed to `@validate_payload`. Pydantic validates and coerces the payload dict before the handler runs.

---

## Lifecycle

```python
class Plugin(AutoMixin):

    async def on_load(self) -> None:
        await super().on_load()  # ← triggers all mixin registrations
        self._users_repo = None
        try:
            db = self.get_service("db")
            self.logger.info("DB connected")
        except KeyError:
            self.logger.warning("DB absent — degraded mode")

    async def on_unload(self) -> None:
        await super().on_unload()  # ← unregisters events, hooks, jobs
```

---

## Health checks

```python
@health_check("demo.db")
async def check_db(self) -> tuple[bool, str]:
    try:
        await self.get_service("db").execute("SELECT 1")
        return True, "ok"
    except KeyError:
        return False, "service 'db' absent"

@health_check("demo.cache")
async def check_cache(self) -> tuple[bool, str]:
    try:
        cache = self.get_service("cache")
        await cache.set("demo:ping", 1, ttl=5)
        val = await cache.get("demo:ping")
        return val == 1, "ok"
    except KeyError:
        return False, "service 'cache' absent"
```

---

## Events

```python
@on_event("user.created", priority=80)
async def on_user_created(self, event: Event) -> None:
    self.logger.info("new user: %s", event.data.get("user_id"))
    # Forward to email plugin
    try:
        await self.call_plugin("email", "send", {...})
    except Exception:
        self.logger.warning("email plugin unavailable")

@on_event("user.*")
async def on_any_user_event(self, event: Event) -> None:
    self.logger.debug("user event: %s", event.name)

@on_event("system.shutdown", once=True)
async def on_shutdown(self, event: Event) -> None:
    self.logger.info("shutdown detected")
```

---

## Hooks

```python
@on_hook("plugin.*.loaded", priority=10)
async def after_plugin_load(self, event: Event) -> None:
    self.logger.debug("plugin loaded: %s", event.data.get("plugin"))

@on_hook("permission.deny", timeout=2.0)
async def on_permission_denied(self, event: Event) -> None:
    self.logger.warning("access denied: %s", event.data)
```

---

## Scheduler

```python
@cron("0 3 * * *")           # daily at 03:00
async def daily_cleanup(self) -> None:
    cache = self.get_service("cache")
    await cache.clear()

@cron("0 9 * * MON-FRI")     # weekdays at 09:00
async def morning_report(self) -> None:
    self.logger.info("morning report")

@interval(minutes=5)
async def heartbeat(self) -> None:
    self.logger.debug("alive")
```

---

## Actions

### ping — sandboxed, no auth required

```python
@action("ping")
@sandboxed
async def ping(self, payload: dict) -> dict:
    return ok(pong=True, name="demo")
```

### get_user — trusted, traced, cached

```python
@action("get_user")
@trusted
@traced("demo.get_user")
@timed("demo.get_user.duration_seconds")
@cached(ttl=300, key=lambda self, p: f"demo:user:{p.get('id', 'unknown')}")
async def get_user(self, payload: dict) -> dict:
    user_id = payload.get("id")
    if not user_id:
        return error("id required", "missing_id")
    return ok(user={"id": user_id, "name": "Alice", "role": "admin"})
```

### create_user — validated, requires db, emits event

```python
@action("create_user")
@trusted
@validate_payload(CreateUserSchema)
@require_service("db")
@counted("demo.users.created")
@invalidate(key=lambda self, p: f"demo:user:{p.get('id', '')}")
async def create_user(self, payload: dict) -> dict:
    name, email = payload["name"], payload["email"]
    await self.ctx.events.emit("user.created", {
        "user_id": "generated-id",
        "name": name,
        "email": email,
    })
    return ok(user_id="generated-id", name=name, email=email)
```

---

## HTTP routes

```python
@route("/ping", method="GET", tags=["demo"])
async def route_ping(self):
    return {"pong": True}

@route("/users", method="POST", status_code=201, permissions=["admin"])
async def route_create_user(self, body: dict):
    return await self.create_user(body)

@route("/users/{user_id}", method="GET")
async def route_get_user(self, user_id: str):
    return await self.get_user({"id": user_id})

@route("/users/{user_id}", method="DELETE", permissions=["admin"])
@counted("demo.users.deleted")
async def route_delete_user(self, user_id: str):
    return ok(deleted=True, user_id=user_id)
```

Routes are registered automatically by `AutoMixin.get_router()` — no manual router wiring needed.

---

## Running the demo

```bash
cd plugins/demo
xcore plugin run demo
```

Or load it programmatically in tests:

```python
import sys
import xcore.sdk as local_sdk
sys.modules["xcore.sdk"] = local_sdk

from plugins.demo.src.main import Plugin
```

See the [Installation guide](../installation.md) for full setup instructions.
