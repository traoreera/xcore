# Basic Plugin Example

A complete example of a simple XCore plugin with various features.

## Plugin Structure

```
plugins/calculator/
├── plugin.yaml
└── src/
    └── main.py
```

## plugin.yaml

```yaml
name: calculator
version: 1.0.0
author: XCore Team
description: A simple calculator plugin with IPC and HTTP endpoints

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

## main.py

```python
"""Calculator plugin demonstrating XCore features."""
from __future__ import annotations

import json
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from xcore.sdk import TrustedBase, ok, error


class Plugin(TrustedBase):
    """Calculator plugin with basic operations."""

    def __init__(self) -> None:
        super().__init__()
        self.operations_count = 0

    async def on_load(self) -> None:
        """Initialize plugin."""
        self.cache = self.get_service("cache")
        print("✅ Calculator plugin loaded")

    async def on_unload(self) -> None:
        """Cleanup plugin."""
        print(f"📊 Total operations: {self.operations_count}")
        print("👋 Calculator plugin unloaded")

    def get_router(self) -> APIRouter:
        """Define HTTP routes."""
        router = APIRouter(
            prefix="/calc",
            tags=["calculator"],
        )

        @router.get("/add")
        async def add(
            a: float = Query(..., description="First number"),
            b: float = Query(..., description="Second number"),
        ):
            """Add two numbers."""
            result = a + b
            await self._cache_operation("add", a, b, result)
            return {"operation": "add", "a": a, "b": b, "result": result}

        @router.get("/subtract")
        async def subtract(
            a: float = Query(..., description="First number"),
            b: float = Query(..., description="Second number"),
        ):
            """Subtract b from a."""
            result = a - b
            await self._cache_operation("subtract", a, b, result)
            return {"operation": "subtract", "a": a, "b": b, "result": result}

        @router.get("/multiply")
        async def multiply(
            a: float = Query(..., description="First number"),
            b: float = Query(..., description="Second number"),
        ):
            """Multiply two numbers."""
            result = a * b
            await self._cache_operation("multiply", a, b, result)
            return {"operation": "multiply", "a": a, "b": b, "result": result}

        @router.get("/divide")
        async def divide(
            a: float = Query(..., description="Dividend"),
            b: float = Query(..., description="Divisor"),
        ):
            """Divide a by b."""
            if b == 0:
                raise HTTPException(status_code=400, detail="Cannot divide by zero")
            result = a / b
            await self._cache_operation("divide", a, b, result)
            return {"operation": "divide", "a": a, "b": b, "result": result}

        @router.get("/power")
        async def power(
            base: float = Query(..., description="Base number"),
            exp: float = Query(..., description="Exponent"),
        ):
            """Calculate base^exp."""
            result = base ** exp
            await self._cache_operation("power", base, exp, result)
            return {"operation": "power", "base": base, "exp": exp, "result": result}

        @router.get("/sqrt")
        async def sqrt(
            value: float = Query(..., description="Number to square root", ge=0),
        ):
            """Calculate square root."""
            import math
            result = math.sqrt(value)
            await self._cache_operation("sqrt", value, None, result)
            return {"operation": "sqrt", "value": value, "result": result}

        @router.get("/history")
        async def get_history(limit: int = Query(10, ge=1, le=100)):
            """Get recent calculations from cache."""
            history = await self._get_history(limit)
            return {"history": history}

        @router.post("/clear")
        async def clear_history():
            """Clear calculation history."""
            await self.cache.delete("calc:history")
            return {"cleared": True}

        return router

    async def _cache_operation(
        self,
        operation: str,
        a: float | None,
        b: float | None,
        result: float,
    ) -> None:
        """Cache calculation result."""
        self.operations_count += 1

        entry = {
            "operation": operation,
            "a": a,
            "b": b,
            "result": result,
            "timestamp": time.time(),
        }

        # Get existing history
        history = await self.cache.get("calc:history") or []
        history.insert(0, entry)

        # Keep only last 100 entries
        history = history[:100]

        # Save back to cache
        await self.cache.set("calc:history", history, ttl=3600)

    async def _get_history(self, limit: int) -> list[dict]:
        """Get calculation history."""
        history = await self.cache.get("calc:history") or []
        return history[:limit]

    async def handle(self, action: str, payload: dict) -> dict:
        """Handle IPC actions."""
        try:
            if action == "add":
                a = payload.get("a", 0)
                b = payload.get("b", 0)
                result = a + b
                await self._cache_operation("add", a, b, result)
                return ok(result=result)

            if action == "subtract":
                a = payload.get("a", 0)
                b = payload.get("b", 0)
                result = a - b
                await self._cache_operation("subtract", a, b, result)
                return ok(result=result)

            if action == "multiply":
                a = payload.get("a", 0)
                b = payload.get("b", 0)
                result = a * b
                await self._cache_operation("multiply", a, b, result)
                return ok(result=result)

            if action == "divide":
                a = payload.get("a", 0)
                b = payload.get("b", 0)
                if b == 0:
                    return error("Cannot divide by zero", code="divide_by_zero")
                result = a / b
                await self._cache_operation("divide", a, b, result)
                return ok(result=result)

            if action == "power":
                base = payload.get("base", 0)
                exp = payload.get("exp", 0)
                result = base ** exp
                await self._cache_operation("power", base, exp, result)
                return ok(result=result)

            if action == "sqrt":
                import math
                value = payload.get("value", 0)
                if value < 0:
                    return error("Cannot calculate square root of negative number")
                result = math.sqrt(value)
                await self._cache_operation("sqrt", value, None, result)
                return ok(result=result)

            if action == "stats":
                """Return plugin statistics."""
                history = await self._get_history(1000)
                operations = {}
                for entry in history:
                    op = entry["operation"]
                    operations[op] = operations.get(op, 0) + 1

                return ok(
                    operations_count=self.operations_count,
                    cached_operations=len(history),
                    operations_breakdown=operations,
                )

            if action == "history":
                limit = payload.get("limit", 10)
                history = await self._get_history(limit)
                return ok(history=history)

            return error(f"Unknown action: {action}", code="unknown_action")

        except Exception as e:
            return error(str(e), code="calculation_error")
```

## Usage

### HTTP Endpoints

```bash
# Addition
curl "http://localhost:8082/plugins/calculator/calc/add?a=10&b=5"
# {"operation":"add","a":10,"b":5,"result":15}

# Division
curl "http://localhost:8082/plugins/calculator/calc/divide?a=100&b=4"
# {"operation":"divide","a":100,"b":4,"result":25}

# Power
curl "http://localhost:8082/plugins/calculator/calc/power?base=2&exp=10"
# {"operation":"power","base":2,"exp":10,"result":1024}

# Square root
curl "http://localhost:8082/plugins/calculator/calc/sqrt?value=16"
# {"operation":"sqrt","value":16,"result":4}

# Get history
curl "http://localhost:8082/plugins/calculator/calc/history?limit=5"
# {"history":[{"operation":"sqrt","a":16,...},...]}

# Clear history
curl -X POST "http://localhost:8082/plugins/calculator/calc/clear"
# {"cleared":true}
```

### IPC Calls

```bash
# Addition
curl -X POST http://localhost:8082/app/calculator/add \
  -H "Content-Type: application/json" \
  -d '{"a": 10, "b": 5}'
# {"status":"ok","result":15}

# Division
curl -X POST http://localhost:8082/app/calculator/divide \
  -H "Content-Type: application/json" \
  -d '{"a": 100, "b": 4}'
# {"status":"ok","result":25}

# Stats
curl -X POST http://localhost:8082/app/calculator/stats
# {"status":"ok","operations_count":42,"cached_operations":42,...}

# History
curl -X POST http://localhost:8082/app/calculator/history \
  -H "Content-Type: application/json" \
  -d '{"limit": 5}'
# {"status":"ok","history":[...]}
```

## Key Features Demonstrated

1. **HTTP Routes**: GET endpoints with query parameters
2. **IPC Actions**: POST endpoints for actions
3. **Cache Service**: Storing calculation history
4. **Error Handling**: Proper error responses
5. **Input Validation**: Query parameter validation
6. **Statistics**: Tracking operations count
7. **Lifecycle Hooks**: on_load and on_unload

## Testing the Plugin

```python
# test_calculator.py
import httpx
import pytest


@pytest.mark.asyncio
async def test_calculator_add():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8082/plugins/calculator/calc/add",
            params={"a": 10, "b": 5}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["result"] == 15


@pytest.mark.asyncio
async def test_calculator_divide_by_zero():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8082/plugins/calculator/calc/divide",
            params={"a": 10, "b": 0}
        )
        assert response.status_code == 400
```

## Next Steps

- Add more complex operations (sin, cos, log)
- Add expression parsing
- Add unit conversion
- Add memory functions (M+, M-, MR, MC)
