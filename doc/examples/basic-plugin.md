# Example: Basic Plugin

The minimal structure for a working XCore plugin in `trusted` mode.

---

## Directory Structure

```
plugins/hello/
├── plugin.yaml
└── src/
    └── main.py
```

---

## `plugin.yaml`

```yaml
name: hello
version: "1.0.0"
author: me
description: A minimal greeting plugin
execution_mode: trusted
entry_point: src/main.py
```

---

## `src/main.py`

```python
from xcore import TrustedBase
from xcore.sdk.decorators import action
from xcore.sdk.mixin.ipc import AutoDispatchMixin
from xcore.kernel.api.contract import ok, error

class Plugin(AutoDispatchMixin, TrustedBase):
    """
    AutoDispatchMixin:
        auto-routes handle("ping", {}) → self.ping({})

    TrustedBase:
        provides self.get_service(), self.call_plugin(), lifecycle hooks
    """

    @action("ping")
    async def ping(self, payload: dict) -> dict:
        return ok(pong=True)

    @action("greet")
    async def greet(self, payload: dict) -> dict:
        name = payload.get("name", "world")
        if not isinstance(name, str):
            return error("name must be a string", "invalid_input")
        return ok(message=f"Hello, {name}!")
```

---

## Test it

```bash
# Start the server
make dev

# Call the ping action
curl -X POST http://localhost:8000/app/hello/action \
     -H "Content-Type: application/json" \
     -d '{"action": "ping", "payload": {}}'
# → {"status": "ok", "pong": true}

# Call the greet action
curl -X POST http://localhost:8000/app/hello/action \
     -H "Content-Type: application/json" \
     -d '{"action": "greet", "payload": {"name": "Dev"}}'
# → {"status": "ok", "message": "Hello, Dev!"}
```

---

## Adding a cache

```yaml
# plugin.yaml — add permission
permissions:
  - resource: "cache.*"
    actions: ["read", "write"]
    effect: allow
```

```python
class Plugin(AutoDispatchMixin, TrustedBase):

    async def on_load(self) -> None:
        self.cache = self.get_service("cache")

    @action("greet")
    async def greet(self, payload: dict) -> dict:
        name = payload.get("name", "world")
        key = f"greet:{name}"

        cached = await self.cache.get(key)
        if cached:
            return ok(message=cached, from_cache=True)

        msg = f"Hello, {name}!"
        await self.cache.set(key, msg, ttl=60)
        return ok(message=msg)
```
