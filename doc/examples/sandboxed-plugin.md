# Example: Sandboxed Plugin

A `sandboxed` plugin runs in a separate OS process with restricted imports. It is suitable for third-party code or any logic you want to isolate from the main process.

---

## Directory Structure

```
plugins/calculator/
├── plugin.yaml
└── src/
    └── main.py
```

---

## `plugin.yaml`

```yaml
name: calculator
version: "1.0.0"
description: "Safe math computations in an isolated process"
execution_mode: sandboxed
entry_point: src/main.py

# Extra imports beyond the global allowed_imports whitelist
allowed_imports:
  - statistics
  - decimal

resources:
  timeout_seconds: 5
  max_memory_mb: 64
  rate_limit:
    calls: 500
    period_seconds: 60

filesystem:
  allowed_paths: ["data/"]
  denied_paths: ["src/"]
```

---

## `src/main.py`

```python
import math
import json
import statistics
from decimal import Decimal, InvalidOperation

from xcore.kernel.api.contract import ok, error

class Plugin:
    """
    Sandboxed plugin — no TrustedBase, no service access.
    Only handle() is required.
    Allowed imports: whatever is in the global whitelist + allowed_imports in plugin.yaml.
    """

    _config: dict   # injected from plugin.yaml (the `extra` fields)

    async def handle(self, action: str, payload: dict) -> dict:
        handlers = {
            "add":      self._add,
            "sqrt":     self._sqrt,
            "stats":    self._stats,
            "evaluate": self._evaluate,
        }
        handler = handlers.get(action)
        if handler is None:
            return error(f"Unknown action: {action}", "unknown_action")
        try:
            return await handler(payload)
        except Exception as exc:
            return error(str(exc), "computation_error")

    async def _add(self, payload: dict) -> dict:
        a = Decimal(str(payload.get("a", 0)))
        b = Decimal(str(payload.get("b", 0)))
        return ok(result=str(a + b))

    async def _sqrt(self, payload: dict) -> dict:
        value = float(payload.get("value", 0))
        if value < 0:
            return error("Cannot take square root of a negative number", "domain_error")
        return ok(result=math.sqrt(value))

    async def _stats(self, payload: dict) -> dict:
        data = payload.get("data", [])
        if not data:
            return error("data list is required", "missing_field")
        if not all(isinstance(x, (int, float)) for x in data):
            return error("All values must be numbers", "invalid_input")
        return ok(
            mean=statistics.mean(data),
            median=statistics.median(data),
            stdev=statistics.stdev(data) if len(data) > 1 else 0,
        )

    async def _evaluate(self, payload: dict) -> dict:
        # Safe expression evaluator using only math functions
        expr = payload.get("expression", "")
        allowed_names = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
        try:
            result = eval(expr, {"__builtins__": {}}, allowed_names)  # noqa: S307
            return ok(result=result)
        except Exception as exc:
            return error(f"Evaluation error: {exc}", "eval_error")

    # Optional lifecycle hooks
    async def on_init(self) -> None: ...
    async def on_start(self) -> None: ...
    async def on_stop(self) -> None: ...
```

---

## Test it

```bash
# Square root
curl -X POST http://localhost:8000/app/calculator/action \
     -H "Content-Type: application/json" \
     -d '{"action": "sqrt", "payload": {"value": 144}}'
# → {"status": "ok", "result": 12.0}

# Statistics
curl -X POST http://localhost:8000/app/calculator/action \
     -H "Content-Type: application/json" \
     -d '{"action": "stats", "payload": {"data": [1, 2, 3, 4, 5]}}'
# → {"status": "ok", "mean": 3.0, "median": 3, "stdev": 1.58}
```

---

## Key Differences from Trusted

| | Trusted | Sandboxed |
|:--|:--------|:---------|
| Process | Main FastAPI process | Isolated OS subprocess |
| Service access | Full (`get_service()`) | None |
| Import restriction | None | AST whitelist |
| IPC ability | `call_plugin()` | No |
| HTTP routes | `get_router()` | No |
| Performance | Low overhead | ~10ms IPC round-trip |
| Use case | Internal features | Third-party / untrusted code |

!!! warning "No `import os`"
    Even if `os` is not in `forbidden_imports`, any import not explicitly in `allowed_imports` is blocked. The AST scanner runs **before** the module loads — there is no runtime escape.
