# Quickstart Guide

Get up and running with XCore in 5 minutes. This guide will walk you through creating your first plugin and making your first API call.

## Step 1: Start the Server

```bash
cd xcore
poetry run uvicorn app:app --reload --port 8082
```

You should see:
```
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8082
```

## Step 2: Create Your First Plugin

Create a simple "Hello World" plugin:

```bash
mkdir -p plugins/hello_world/src
```

Create `plugins/hello_world/plugin.yaml`:

```yaml
name: hello_world
version: 1.0.0
author: Your Name
description: A simple hello world plugin
execution_mode: trusted
framework_version: ">=2.0"
entry_point: src/main.py

permissions:
  - resource: "cache.*"
    actions: ["read", "write"]
    effect: allow

resources:
  timeout_seconds: 10
```

Create `plugins/hello_world/src/main.py`:

```python
from xcore.sdk import TrustedBase, ok, error


class Plugin(TrustedBase):
    """Hello World plugin demonstrating XCore basics."""

    async def on_load(self) -> None:
        """Called when plugin is loaded."""
        print("✅ Hello World plugin loaded!")

    async def on_unload(self) -> None:
        """Called when plugin is unloaded."""
        print("👋 Hello World plugin unloaded!")

    async def handle(self, action: str, payload: dict) -> dict:
        """Handle incoming action calls."""

        if action == "hello":
            name = payload.get("name", "World")
            return ok(message=f"Hello, {name}!")

        if action == "greet":
            name = payload.get("name", "Guest")
            language = payload.get("language", "en")

            greetings = {
                "en": f"Hello, {name}!",
                "fr": f"Bonjour, {name}!",
                "es": f"¡Hola, {name}!",
                "de": f"Hallo, {name}!",
            }

            return ok(
                message=greetings.get(language, greetings["en"]),
                language=language
            )

        return error(f"Unknown action: {action}", code="unknown_action")
```

## Step 3: Call Your Plugin

The plugin automatically loads. Now let's call it:

### Using cURL

```bash
# Simple hello
curl -X POST http://localhost:8082/app/hello_world/hello \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice"}'

# Response:
# {"status":"ok","message":"Hello, Alice!"}

# Greet with language
curl -X POST http://localhost:8082/app/hello_world/greet \
  -H "Content-Type: application/json" \
  -d '{"name": "Bob", "language": "fr"}'

# Response:
# {"status":"ok","message":"Bonjour, Bob!","language":"fr"}
```

### Using Python

```python
import httpx

async def call_plugin():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8082/app/hello_world/hello",
            json={"name": "Alice"}
        )
        print(response.json())
        # {'status': 'ok', 'message': 'Hello, Alice!'}

# Run with asyncio
import asyncio
asyncio.run(call_plugin())
```

## Step 4: Add HTTP Routes

Let's expose a REST API endpoint:

Update `plugins/hello_world/src/main.py`:

```python
from fastapi import APIRouter
from xcore.sdk import TrustedBase, ok, error


class Plugin(TrustedBase):

    async def on_load(self) -> None:
        print("✅ Hello World plugin loaded!")

    def get_router(self) -> APIRouter:
        """Define custom HTTP routes."""
        router = APIRouter(prefix="/hello", tags=["hello"])

        @router.get("/")
        async def hello_root():
            return {"message": "Hello World API"}

        @router.get("/{name}")
        async def hello_name(name: str):
            return {"message": f"Hello, {name}!"}

        @router.post("/greet")
        async def greet(data: dict):
            name = data.get("name", "Guest")
            return {"message": f"Hello, {name}!"}

        return router

    async def handle(self, action: str, payload: dict) -> dict:
        if action == "hello":
            return ok(message="Hello from IPC!")
        return error("Unknown action")
```

Now test the HTTP routes:

```bash
# GET endpoint
curl http://localhost:8082/plugins/hello_world/hello/Alice
# {"message":"Hello, Alice!"}

# POST endpoint
curl -X POST http://localhost:8082/plugins/hello_world/hello/greet \
  -H "Content-Type: application/json" \
  -d '{"name": "Charlie"}'
# {"message":"Hello, Charlie!"}
```

## Step 5: Use Services

Let's use the cache service:

Update `plugins/hello_world/src/main.py`:

```python
from fastapi import APIRouter
from xcore.sdk import TrustedBase, ok
import time


class Plugin(TrustedBase):

    async def on_load(self) -> None:
        # Get cache service
        self.cache = self.get_service("cache")
        print("✅ Hello World plugin loaded with cache access!")

    def get_router(self) -> APIRouter:
        router = APIRouter(prefix="/hello", tags=["hello"])

        @router.get("/cached-time")
        async def cached_time():
            """Returns cached current time."""
            # Try to get from cache
            cached = await self.cache.get("current_time")
            if cached:
                return {"time": cached, "cached": True}

            # Compute and cache
            current = time.strftime("%Y-%m-%d %H:%M:%S")
            await self.cache.set("current_time", current, ttl=60)
            return {"time": current, "cached": False}

        return router

    async def handle(self, action: str, payload: dict) -> dict:
        if action == "cache_test":
            await self.cache.set("test_key", "test_value", ttl=300)
            value = await self.cache.get("test_key")
            return ok(cached_value=value)
        return ok()
```

Test the cache:

```bash
# First call - not cached
curl http://localhost:8082/plugins/hello_world/hello/cached-time
# {"time":"2024-01-15 14:30:00","cached":false}

# Second call - cached
curl http://localhost:8082/plugins/hello_world/hello/cached-time
# {"time":"2024-01-15 14:30:00","cached":true}
```

## Summary

You've learned:

✅ How to create a basic XCore plugin
✅ How to expose IPC actions (handle method)
✅ How to add custom HTTP routes (get_router method)
✅ How to access services (cache, database, etc.)

## What's Next?

- [Complete Plugin Tutorial](../guides/creating-plugins.md)
- [Working with Services](../guides/services.md)
- [Event System](../guides/events.md)
- [Security Best Practices](../guides/security.md)
