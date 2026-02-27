# Creating Plugins

This guide covers everything you need to know about creating XCore plugins, from simple IPC handlers to full REST API endpoints.

## Plugin Structure

A minimal plugin requires two files:

```
plugins/my_plugin/
├── plugin.yaml      # Plugin manifest
└── src/
    └── main.py     # Plugin implementation
```

## The Manifest (plugin.yaml)

The manifest describes your plugin to XCore:

```yaml
name: my_plugin                    # Unique identifier
version: 1.0.0                    # Semantic version
author: Your Name                  # Author name
description: Plugin description    # Short description

execution_mode: trusted            # trusted | sandboxed | legacy
framework_version: ">=2.0"        # Compatible XCore version
entry_point: src/main.py          # Main file path

# Dependencies on other plugins (optional)
requires:
  - other_plugin
  - another_plugin

# Service permissions (optional)
permissions:
  - resource: "db.*"
    actions: ["read", "write"]
    effect: allow
  - resource: "cache.*"
    actions: ["read"]
    effect: allow

# Environment variables (optional)
env:
  API_KEY: "default_value"
  DEBUG: "false"

# Resource limits (optional)
resources:
  timeout_seconds: 30
  max_memory_mb: 256
  rate_limit:
    calls: 1000
    period_seconds: 60
```

## Basic Plugin

The simplest plugin inherits from `TrustedBase`:

```python
# src/main.py
from xcore.sdk import TrustedBase, ok, error


class Plugin(TrustedBase):
    """My first XCore plugin."""

    async def on_load(self) -> None:
        """Called when plugin is loaded."""
        print(f"Plugin {self.__class__.__name__} loaded")

    async def on_unload(self) -> None:
        """Called when plugin is unloaded."""
        print(f"Plugin {self.__class__.__name__} unloaded")

    async def handle(self, action: str, payload: dict) -> dict:
        """Handle IPC actions.

        Args:
            action: The action name to execute
            payload: Dictionary of parameters

        Returns:
            Dictionary with status and data
        """
        if action == "ping":
            return ok(message="pong")

        if action == "echo":
            return ok(received=payload)

        return error(
            msg=f"Unknown action: {action}",
            code="unknown_action"
        )
```

## Plugin with HTTP Routes

Expose REST API endpoints by implementing `get_router()`:

```python
from fastapi import APIRouter, HTTPException
from xcore.sdk import TrustedBase
import uuid


class Plugin(TrustedBase):

    def __init__(self):
        super().__init__()
        self.items = {}  # In-memory storage

    def get_router(self) -> APIRouter:
        """Return FastAPI router with custom routes."""
        router = APIRouter(
            prefix="/items",
            tags=["items"],
            responses={404: {"description": "Not found"}}
        )

        @router.get("/")
        async def list_items():
            """List all items."""
            return {"items": list(self.items.values())}

        @router.get("/{item_id}")
        async def get_item(item_id: str):
            """Get a specific item."""
            if item_id not in self.items:
                raise HTTPException(status_code=404, detail="Item not found")
            return self.items[item_id]

        @router.post("/")
        async def create_item(data: dict):
            """Create a new item."""
            item_id = str(uuid.uuid4())
            self.items[item_id] = {
                "id": item_id,
                **data
            }
            return self.items[item_id]

        @router.put("/{item_id}")
        async def update_item(item_id: str, data: dict):
            """Update an existing item."""
            if item_id not in self.items:
                raise HTTPException(status_code=404, detail="Item not found")
            self.items[item_id].update(data)
            return self.items[item_id]

        @router.delete("/{item_id}")
        async def delete_item(item_id: str):
            """Delete an item."""
            if item_id not in self.items:
                raise HTTPException(status_code=404, detail="Item not found")
            del self.items[item_id]
            return {"deleted": True}

        return router

    async def handle(self, action: str, payload: dict) -> dict:
        # IPC actions can also manipulate items
        if action == "create":
            item_id = str(uuid.uuid4())
            self.items[item_id] = {"id": item_id, **payload}
            return {"status": "ok", "id": item_id}

        return {"status": "error", "msg": "Unknown action"}
```

These routes will be mounted at `/plugins/my_plugin/items/`.

## Using Services

Access XCore services through `self.get_service()`:

### Database Access

```python
from xcore.sdk import TrustedBase


class Plugin(TrustedBase):

    async def on_load(self) -> None:
        # Get database service
        self.db = self.get_service("db")

    def get_router(self):
        from fastapi import APIRouter
        router = APIRouter()

        @router.get("/users")
        async def list_users():
            # Using sync database
            with self.db.session() as session:
                result = session.execute("SELECT * FROM users")
                users = result.fetchall()
                return {"users": [dict(u) for u in users]}

        return router
```

### Cache Service

```python
from xcore.sdk import TrustedBase, ok


class Plugin(TrustedBase):

    async def on_load(self) -> None:
        self.cache = self.get_service("cache")

    async def handle(self, action: str, payload: dict) -> dict:
        if action == "set":
            key = payload["key"]
            value = payload["value"]
            ttl = payload.get("ttl", 300)

            await self.cache.set(key, value, ttl=ttl)
            return ok(message="Value cached")

        if action == "get":
            key = payload["key"]
            value = await self.cache.get(key)
            return ok(value=value)

        if action == "delete":
            key = payload["key"]
            await self.cache.delete(key)
            return ok(message="Key deleted")

        return ok()
```

### Scheduler Service

```python
from xcore.sdk import TrustedBase
import datetime


class Plugin(TrustedBase):

    async def on_load(self) -> None:
        self.scheduler = self.get_service("scheduler")

        # Add a recurring job
        self.scheduler.add_job(
            func=self._cleanup_task,
            trigger="interval",
            minutes=5,
            id=f"{self.__class__.__name__}_cleanup",
            replace_existing=True
        )

    def _cleanup_task(self):
        """Run every 5 minutes."""
        print(f"Cleanup task running at {datetime.datetime.now()}")

    async def handle(self, action: str, payload: dict) -> dict:
        if action == "schedule":
            # Schedule a one-time job
            run_at = payload.get("run_at")  # ISO format datetime
            self.scheduler.add_job(
                func=self._scheduled_action,
                trigger="date",
                run_date=run_at,
                args=[payload.get("data")]
            )
            return {"status": "ok", "scheduled": True}

        return {"status": "ok"}

    def _scheduled_action(self, data):
        print(f"Scheduled action executed with data: {data}")
```

## Using Events

Plugins can emit and subscribe to events:

```python
from xcore.sdk import TrustedBase, ok


class Plugin(TrustedBase):

    async def on_load(self) -> None:
        # Subscribe to events
        self.ctx.events.on("user.created", self._on_user_created)
        self.ctx.events.on("order.placed", self._on_order_placed, priority=100)

    async def _on_user_created(self, event):
        """Handle user creation event."""
        user_email = event.data.get("email")
        print(f"New user created: {user_email}")

        # Could send welcome email here

    async def _on_order_placed(self, event):
        """Handle order placement (high priority)."""
        order_id = event.data.get("order_id")
        print(f"Processing order: {order_id}")

    async def handle(self, action: str, payload: dict) -> dict:
        if action == "create_order":
            # Create order logic...
            order_id = "12345"

            # Emit event
            await self.ctx.events.emit("order.placed", {
                "order_id": order_id,
                "user_id": payload.get("user_id"),
                "amount": payload.get("amount")
            })

            return ok(order_id=order_id)

        return ok()
```

## Validation with Pydantic

Use Pydantic models for request validation:

```python
from pydantic import BaseModel, EmailStr, Field
from xcore.sdk import TrustedBase, ok, error


class CreateUserInput(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    age: int = Field(ge=0, le=150)


class UpdateUserInput(BaseModel):
    username: str | None = Field(None, min_length=3, max_length=50)
    age: int | None = Field(None, ge=0, le=150)


class Plugin(TrustedBase):

    users = {}

    def get_router(self):
        from fastapi import APIRouter
        router = APIRouter()

        @router.post("/users")
        async def create_user(data: CreateUserInput):
            """Create a new user with validation."""
            user_id = str(len(self.users) + 1)
            self.users[user_id] = {
                "id": user_id,
                "username": data.username,
                "email": data.email,
                "age": data.age
            }
            return self.users[user_id]

        @router.put("/users/{user_id}")
        async def update_user(user_id: str, data: UpdateUserInput):
            """Update user with partial validation."""
            if user_id not in self.users:
                return error("User not found", code="not_found")

            update_data = data.model_dump(exclude_unset=True)
            self.users[user_id].update(update_data)
            return self.users[user_id]

        return router

    async def handle(self, action: str, payload: dict) -> dict:
        if action == "create_user":
            try:
                validated = CreateUserInput(**payload)
                # ... create user
                return ok(user_id="123")
            except Exception as e:
                return error(str(e), code="validation_error")

        return ok()
```

## Error Handling

Use standardized error responses:

```python
from xcore.sdk import TrustedBase, ok, error
from fastapi import HTTPException


class Plugin(TrustedBase):

    async def handle(self, action: str, payload: dict) -> dict:
        try:
            if action == "risky_operation":
                result = await self._risky_operation(payload)
                return ok(data=result)

        except ValueError as e:
            # Client error
            return error(
                msg=str(e),
                code="invalid_input",
                status_code=400
            )

        except PermissionError as e:
            # Authorization error
            return error(
                msg=str(e),
                code="forbidden",
                status_code=403
            )

        except Exception as e:
            # Server error
            return error(
                msg="Internal server error",
                code="internal_error",
                details=str(e),
                status_code=500
            )

        return error("Unknown action", code="unknown_action")
```

## Plugin Lifecycle

Understanding the plugin lifecycle:

```python
from xcore.sdk import TrustedBase


class Plugin(TrustedBase):

    def __init__(self):
        super().__init__()
        self.initialized = False

    async def on_load(self) -> None:
        """
        Called once when plugin is first loaded.
        Initialize services, connections, etc.
        """
        # Get services
        self.db = self.get_service("db")
        self.cache = self.get_service("cache")

        # Initialize internal state
        self.data = {}
        self.initialized = True

        print("Plugin initialized")

    async def on_reload(self) -> None:
        """
        Called when plugin is reloaded (hot reload).
        Clean up and reinitialize if needed.
        """
        # Save state if needed
        self._saved_state = self.data.copy()

        # Clean up
        self.data.clear()

        print("Plugin reloading...")

    async def on_unload(self) -> None:
        """
        Called when plugin is unloaded.
        Clean up resources, close connections.
        """
        # Close any open resources
        self.data.clear()
        self.initialized = False

        print("Plugin unloaded")

    async def handle(self, action: str, payload: dict) -> dict:
        if not self.initialized:
            return {"status": "error", "msg": "Plugin not initialized"}
        # ... handle actions
        return {"status": "ok"}
```

## Best Practices

### 1. Use Type Hints

```python
from typing import Any

async def handle(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
    ...
```

### 2. Document Your Code

```python
class Plugin(TrustedBase):
    """User management plugin.

    Provides CRUD operations for users with
    caching and event notifications.
    """

    async def handle(self, action: str, payload: dict) -> dict:
        """Handle user-related actions.

        Actions:
            - create: Create new user
            - get: Get user by ID
            - list: List all users
            - delete: Delete user
        """
        ...
```

### 3. Handle Edge Cases

```python
async def handle(self, action: str, payload: dict) -> dict:
    if action == "divide":
        try:
            a = payload.get("a", 0)
            b = payload.get("b", 0)

            if b == 0:
                return error("Cannot divide by zero", code="divide_by_zero")

            return ok(result=a / b)
        except TypeError:
            return error("Invalid number format", code="type_error")
```

### 4. Use Constants for Action Names

```python
ACTION_CREATE = "create"
ACTION_UPDATE = "update"
ACTION_DELETE = "delete"

class Plugin(TrustedBase):
    async def handle(self, action: str, payload: dict) -> dict:
        if action == ACTION_CREATE:
            ...
        elif action == ACTION_UPDATE:
            ...
```

## Next Steps

- [Working with Services](services.md)
- [Event System](events.md)
- [Security Best Practices](security.md)
- [Testing Plugins](testing.md)
