---
title: SDK Core Concepts
description: Foundational concepts of the xcoreSDK — plugin model, lifecycle, context, and decorator ordering.
icon: material/lightbulb
---

# Core Concepts

## Plugin model

Every xcore plugin is a Python class named `Plugin` that inherits from a base provided by the SDK. The xcore kernel discovers, loads, and manages plugin lifecycle automatically.

```
plugin.yaml          →  kernel reads metadata, execution mode, resources
src/main.py          →  kernel imports and instantiates Plugin()
Plugin.on_load()     →  kernel calls this after injecting context
Plugin.on_unload()   →  kernel calls this on graceful shutdown
```

---

## Execution modes

Defined in `plugin.yaml` under `execution_mode`:

| Mode | Trust level | Use case |
|------|-------------|----------|
| `trusted` | Full kernel access | Internal, first-party plugins |
| `sandboxed` | Restricted — no direct service access | Third-party plugins |
| `legacy` | Compatibility shim | Migrating older plugins |

Decorators like `@trusted` and `@sandboxed` enforce access at the action level, independent of the plugin's global mode.

---

## PluginContext

Every plugin receives a `PluginContext` injected into `self.ctx` before `on_load()` is called.

```python
self.ctx.name          # str — plugin name from manifest
self.ctx.version       # str — plugin version
self.ctx.env           # dict — env vars declared in plugin.yaml
self.ctx.services      # dict — registered kernel services
self.ctx.events        # EventBus — emit / subscribe
self.ctx.hooks         # HookBus — register / unregister
self.ctx.metrics       # MetricsCollector — counters, histograms
self.ctx.tracer        # Tracer — distributed tracing spans
self.ctx.health        # HealthRegistry — register health checks
self.ctx.scheduler     # SchedulerService — APScheduler wrapper
```

!!! note
    Not all services are guaranteed to be present. Decorators like `@require_service("db")` guard against missing services at call time.

---

## Plugin lifecycle

```
kernel.load_plugin("my_plugin")
  → Plugin.__init__()
  → Plugin.ctx = PluginContext(...)
  → await Plugin.on_load()           ← mixins register here
      EventMixin.on_load()           ← subscribes @on_event methods
      HookMixin.on_load()            ← registers @on_hook methods
      ObservabilityMixin.on_load()   ← registers @health_check methods
      ScheduledMixin.on_load()       ← adds @cron / @interval jobs

kernel.unload_plugin("my_plugin")
  → await Plugin.on_unload()         ← mixins clean up here
      EventMixin.on_unload()         ← unsubscribes all events
      HookMixin.on_unload()          ← unregisters all hooks
      ScheduledMixin.on_unload()     ← removes all scheduled jobs
```

The MRO chain guarantees every mixin's `on_load` and `on_unload` runs — as long as each mixin calls `await super().on_load()`.

---

## Services

Plugins access kernel services through `self.ctx.services` or the helper:

```python
db = self.get_service("db")        # raises KeyError if absent
cache = self.get_service("cache")
```

Common service keys registered by the kernel:

| Key | Type | Description |
|-----|------|-------------|
| `db` | `AsyncEngine` | SQLAlchemy async engine |
| `cache` | `CacheService` | Redis or in-memory cache |
| `email` | plugin proxy | Email plugin (if loaded) |

---

## AutoMixin composition

`AutoMixin` is the recommended base class. It composes all mixins through Python MRO:

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
    ...
```

The MRO ensures each mixin's `on_load` is called exactly once, in the correct order, via cooperative `super()` chaining.

---

## Decorator stacking order

Python decorators apply bottom-up. For action handlers, the recommended order is:

```python
@action("name")         # 1 — registers the action name
@trusted                # 2 — enforces execution mode
@validate_payload(...)  # 3 — validates input (runs before business logic)
@require_service("db")  # 4 — checks service availability
@traced("span.name")    # 5 — wraps in tracing span
@cached(ttl=300, ...)   # 6 — innermost: cache lookup wraps the actual call
async def handler(self, payload: dict) -> dict:
    ...
```

!!! warning "Order matters"
    `@validate_payload` must be **above** `@require_service` in source — i.e., it must run **before** `@require_service` in execution order. If reversed, a missing service raises before validation runs.
