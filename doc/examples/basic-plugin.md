# Basic Plugin Example: Calculator

A simple XCore plugin demonstrating basic IPC actions, HTTP routes, and cache usage.

## 1. Plugin Structure

```text
plugins/calculator/
├── plugin.yaml
└── src/
    └── main.py
```

## 2. Manifest (`plugin.yaml`)

```yaml
name: calculator
version: 1.0.0
author: XCore Team
description: A simple calculator plugin with IPC and HTTP endpoints.

execution_mode: trusted
framework_version: ">=2.0"
entry_point: src/main.py

permissions:
  - resource: "cache.*"
    actions: ["read", "write"]
    effect: allow

resources:
  timeout_seconds: 10
  rate_limit:
    calls: 1000
    period_seconds: 60
```

## 3. Implementation (`src/main.py`)

```python
"""Calculator plugin demonstrating XCore features."""
from __future__ import annotations

import time
import math
from fastapi import APIRouter, HTTPException, Query
from xcore.sdk import TrustedBase, ok, error


class Plugin(TrustedBase):
    """Calculator plugin with basic arithmetic operations."""

    def __init__(self) -> None:
        super().__init__()
        self.operations_count = 0

    async def on_load(self) -> None:
        """Initialize plugin by retrieving the cache service."""
        self.cache = self.get_service("cache")
        print("✅ Calculator plugin loaded")

    async def on_unload(self) -> None:
        """Cleanup and log final stats."""
        print(f"📊 Total operations performed: {self.operations_count}")
        print("👋 Calculator plugin unloaded")

    def get_router(self) -> APIRouter:
        """Define FastAPI routes for the calculator."""
        router = APIRouter(prefix="/calc", tags=["calculator"])

        @router.get("/add")
        async def add(a: float = Query(...), b: float = Query(...)):
            result = a + b
            await self._cache_operation("add", a, b, result)
            return {"operation": "add", "a": a, "b": b, "result": result}

        @router.get("/divide")
        async def divide(a: float = Query(...), b: float = Query(...)):
            if b == 0:
                raise HTTPException(status_code=400, detail="Cannot divide by zero")
            result = a / b
            await self._cache_operation("divide", a, b, result)
            return {"operation": "divide", "a": a, "b": b, "result": result}

        @router.get("/history")
        async def get_history(limit: int = Query(10, ge=1, le=100)):
            history = await self.cache.get("calc:history") or []
            return {"history": history[:limit]}

        return router

    async def _cache_operation(self, op: str, a: float, b: float | None, res: float) -> None:
        """Helper to store history in cache."""
        self.operations_count += 1
        entry = {"operation": op, "a": a, "b": b, "result": res, "ts": time.time()}

        history = await self.cache.get("calc:history") or []
        history.insert(0, entry)
        await self.cache.set("calc:history", history[:50], ttl=3600)

    async def handle(self, action: str, payload: dict) -> dict:
        """Handle IPC calls."""
        try:
            if action == "add":
                res = payload.get("a", 0) + payload.get("b", 0)
                await self._cache_operation("add", payload.get("a"), payload.get("b"), res)
                return ok(result=res)

            return error(f"Unknown action: {action}", code="unknown_action")
        except Exception as e:
            return error(str(e), code="calculation_error")
```

## 4. Usage

### HTTP Call
```bash
curl "http://localhost:8082/plugins/calculator/calc/add?a=10&b=5"
# {"operation":"add","a":10.0,"b":5.0,"result":15.0}
```

### IPC Call
```bash
xcore plugin call calculator add '{"a": 10, "b": 5}'
# {"status": "ok", "result": 15}
```
