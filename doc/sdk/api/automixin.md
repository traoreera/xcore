---
title: AutoMixin
description: Composite base class bundling all SDK mixins — the recommended starting point for every plugin.
icon: material/layers
---

# AutoMixin

`AutoMixin` is the recommended base class for all xcore plugins. It composes every mixin and dispatch mechanism into a single class so that plugin authors only ever write one import and one `class Plugin(AutoMixin):` declaration.

## Import

```python
from xcore.sdk import AutoMixin
```

## Definition

```python
class AutoMixin(
    EventMixin,
    HookMixin,
    ObservabilityMixin,
    ScheduledMixin,
    RoutedPlugin,
    AutoDispatchMixin,
    TrustedBase,
):
    def get_router(self):
        return self.RouterIn()
```

The MRO ensures each mixin's `on_load` and `on_unload` run in order via cooperative `super()` chaining.

---

## Lifecycle methods

These are inherited from the mixin chain. Override them in `Plugin` to add custom logic — always call `await super()`:

```python
class Plugin(AutoMixin):

    async def on_load(self) -> None:
        await super().on_load()   # ← required: triggers all mixin registrations
        # your init code here

    async def on_reload(self) -> None:
        await super().on_reload()
        # re-initialize any state

    async def on_unload(self) -> None:
        await super().on_unload()  # ← required: unregisters events, hooks, jobs
        # cleanup
```

!!! warning
    Forgetting `await super().on_load()` will silently skip all mixin registrations — events, hooks, scheduled jobs, and health checks will not be set up.

---

## Inherited capabilities

By inheriting `AutoMixin`, your `Plugin` class gains:

| Mixin | What you get |
|-------|--------------|
| `EventMixin` | `@on_event` handler registration, `self.ctx.events` |
| `HookMixin` | `@on_hook` handler registration, `self.ctx.hooks` |
| `ObservabilityMixin` | `self.logger`, `@health_check` registration |
| `ScheduledMixin` | `@cron` and `@interval` job scheduling |
| `RoutedPlugin` | `@route` HTTP handler, `get_router()`, `RouterIn()` |
| `AutoDispatchMixin` | `@action` handler, `handle(action_name, payload)` |
| `TrustedBase` | `get_service()`, `call_plugin()`, `self.ctx` injection |

---

## get_router()

Returns a FastAPI `APIRouter` pre-populated with all `@route`-decorated methods.

```python
# Inside the kernel's plugin loader:
router = plugin.get_router()
app.include_router(router, prefix=f"/plugins/{plugin.ctx.name}")
```

`AutoMixin` pre-implements this as `return self.RouterIn()` so you don't need to override it.

---

## handle()

Dispatches an action by name:

```python
result = await plugin.handle("get_user", {"id": "abc123"})
```

Raises `KeyError` if the action is not registered.

---

## Minimal plugin example

```python
from xcore.sdk import AutoMixin, action, ok

class Plugin(AutoMixin):

    async def on_load(self) -> None:
        await super().on_load()
        self.logger.info("loaded")

    @action("ping")
    async def ping(self, payload: dict) -> dict:
        return ok(pong=True)
```

---

## Using individual mixins

If you need only a subset of capabilities, import and compose mixins manually:

```python
from xcore.sdk import AutoDispatchMixin, EventMixin, TrustedBase
from xcore.kernel.api.contract import TrustedBase

class Plugin(EventMixin, AutoDispatchMixin, TrustedBase):

    async def on_load(self) -> None:
        await super().on_load()
```

This avoids pulling in the scheduler or router if the plugin doesn't need them.
