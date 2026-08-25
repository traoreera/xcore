---
title: Observability SDK
description: Decorators and mixins for logging, metrics, tracing, and health checks in plugins.
icon: material/eye
---

# Observability

xcoreSDK provides declarative observability: tracing, metrics, and health checks — all via decorators.

```python
from xcore.sdk import traced, counted, timed, health_check, get_logger
```

---

## get_logger

Returns a structured logger namespaced under `plugin.<name>`.

```python
from xcore.sdk import get_logger

logger = get_logger("my_plugin")
logger.info("started")
logger.warning("degraded: %s", reason)
logger.error("failed", exc_info=True)
```

Inside a plugin, `self.logger` is pre-wired via `ObservabilityMixin`:

```python
class Plugin(AutoMixin):
    async def on_load(self):
        await super().on_load()
        self.logger.info("plugin loaded")
```

---

## @traced

Wraps a handler in a distributed tracing span. No-ops gracefully when `self.ctx.tracer` is `None`.

```python
from xcore.sdk import traced

@action("get_user")
@traced("demo.get_user")
async def get_user(self, payload: dict) -> dict:
    ...
```

**Parameters**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `span_name` | `str \| None` | function name | Name for the tracing span |

On exception, the span is marked with `status="error"` before re-raising.

---

## @counted

Increments a counter metric after every successful call.

```python
from xcore.sdk import counted

@action("create_user")
@counted("demo.users.created")
async def create_user(self, payload: dict) -> dict:
    ...
```

**Parameters**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `metric_name` | `str` | — | Counter name in `self.ctx.metrics` |
| `labels` | `dict \| None` | `None` | Optional label dimensions |

No-ops when `self.ctx.metrics` is unavailable.

---

## @timed

Records handler duration as a histogram observation.

```python
from xcore.sdk import timed

@action("search")
@timed("demo.search.duration_seconds")
async def search(self, payload: dict) -> dict:
    ...
```

**Parameters**

| Name | Type | Description |
|------|------|-------------|
| `metric_name` | `str` | Histogram name in `self.ctx.metrics` |

Duration is measured from call entry to return, including any awaited I/O.

---

## @health_check

Registers a method as a health check with the kernel's health registry.

```python
from xcore.sdk import health_check

@health_check("demo.db")
async def check_db(self) -> tuple[bool, str]:
    try:
        db = self.get_service("db")
        await db.execute("SELECT 1")
        return True, "ok"
    except KeyError:
        return False, "service 'db' absent"
```

**Parameters**

| Name | Type | Description |
|------|------|-------------|
| `check_name` | `str` | Identifier exposed in `/health` endpoint |

**Return value:** `tuple[bool, str]` — `(healthy, message)`.

Health checks are registered during `on_load` by `ObservabilityMixin` and unregistered during `on_unload`.

---

## ObservabilityMixin

Composed by `AutoMixin`. Provides:

- `self.logger` property — pre-namespaced logger
- Auto-registration of all `@health_check`-decorated methods during `on_load`
- Auto-cleanup during `on_unload`

No manual wiring needed when using `AutoMixin`.

---

## Direct metrics access

For custom metric operations beyond the decorator API:

```python
# Counter
self.ctx.metrics.increment("my.counter", labels={"env": "prod"})

# Histogram
self.ctx.metrics.observe("my.histogram", value=0.42)

# Gauge
self.ctx.metrics.set_gauge("my.gauge", value=100)
```

Available when `self.ctx.metrics` is not `None` (i.e., the metrics service is registered).
