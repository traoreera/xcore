# Example: Calculator Plugin

A simple plugin demonstrating basic IPC actions, arithmetic logic, and cache usage.

## 1. Manifest (`plugin.yaml`)

```yaml
name: calculator
version: 1.0.0
execution_mode: trusted
entry_point: src/main.py

permissions:
  - resource: "cache.calc.*"
    actions: ["read", "write"]
    effect: allow
```

## 2. Implementation (`src/main.py`)

```python
from xcore.sdk import TrustedBase, AutoDispatchMixin, action, ok, error

class Plugin(AutoDispatchMixin, TrustedBase):
    async def on_load(self):
        self.cache = self.get_service("cache")

    @action("add")
    async def add(self, payload: dict):
        a = payload.get("a", 0)
        b = payload.get("b", 0)
        res = a + b

        # Cache the last result
        await self.cache.set("calc.last_result", res)

        return ok(result=res)

    @action("last")
    async def get_last(self, payload: dict):
        res = await self.cache.get("calc.last_result")
        return ok(result=res)
```
