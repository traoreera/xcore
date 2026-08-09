---
title: Observability SDK
description: Decorators and mixins for logging, metrics, tracing, and health checks in plugins.
icon: material/eye
---

# Observability SDK

The SDK provides declarative decorators and direct properties on `TrustedBase` to instrument your plugins without boilerplate.

---

## Direct Properties

Any plugin inheriting from `TrustedBase` has access to these properties without any configuration:

| Property | Type | Description |
|-----------|------|-------------|
| `self.logger` | `XcoreLogger` | Structured logger bound to the plugin namespace |
| `self.metrics` | `MetricsRegistry` | Metrics registry |
| `self.tracer` | `Tracer` | Tracer for spans |
| `self.health` | `HealthChecker` | Health checks registry |

---

## 1. Structured Logging

Structured logger — accepts arbitrary kwargs as contextual fields.

```python linenums="1"
class Plugin(TrustedBase):
    async def handle(self, action, payload):
        self.logger.info("action executed", action=action, user_id=payload.get("user_id"))
```

Outside of a plugin, use `get_logger` directly:

```python
from xcore.kernel.observability import get_logger
logger = get_logger("my_namespace")
```

---

## 2. Tracing Decorator

Wraps a method in a tracing span. No-op if `self.tracer` is `None`.

```python linenums="1"
from xcore.sdk import traced

class Plugin(TrustedBase):
    @traced("process_payment")
    async def process(self, payload: dict):
        ...
```

If an exception occurs, the span is marked as `status="error"` before the exception is re-raised.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `span_name` | `str \| None` | function name | Name of the span in the tracer |

---

## 3. Metrics Decorators

### `@counted`

Increments a counter after each successful call. No-op if `self.metrics` is `None`.

```python linenums="1"
from xcore.sdk import counted

class Plugin(TrustedBase):
    @counted("payment_processed_total")
    async def process(self, payload: dict):
        ...
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `metric_name` | `str` | — | Name of the counter in `self.metrics` |

### `@timed`

Records the execution duration in a histogram. No-op if `self.metrics` is `None`.

```python linenums="1"
from xcore.sdk import timed

class Plugin(TrustedBase):
    @timed("payment_duration_seconds")
    async def process(self, payload: dict):
        ...
```

The duration is measured from method entry to exit, including any awaited I/O.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `metric_name` | `str` | — | Name of the histogram in `self.metrics` |

---

## 4. Health Checks Decorator

Marks a method as a health check. The method must return `(bool, str)`.

```python linenums="1"
from xcore.sdk import health_check

class Plugin(TrustedBase):
    @health_check("shop.inventory")
    async def check_inventory(self) -> tuple[bool, str]:
        # Return status and descriptive message
        return True, "ok"
```

Checks are registered automatically in `self.ctx.health` during `on_load()` via `ObservabilityMixin`.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `check_name` | `str` | — | Identifier exposed in `GET /ipc/health` |

---

## `ObservabilityMixin`

Provides:

- Automatic registration of all `@health_check` methods during `on_load()`
- Injection of `self.logger`, `self.metrics`, `self.tracer`, and `self.health`

```python
from xcore.sdk import ObservabilityMixin

class Plugin(ObservabilityMixin, TrustedBase):
    pass
```

---

## Decorator Combination

Decorators can be combined. Recommended order: `@traced` → `@counted` → `@timed` (from outside to inside).

```python linenums="1"
class Plugin(TrustedBase):
    @traced("process_payment")
    @counted("payment_processed_total")
    @timed("payment_duration_seconds")
    async def process(self, payload: dict):
        ...
```

---

## Advanced Usage

For operations not covered by decorators:

```python linenums="1"
# Counter with dynamic labels
self.metrics.counter(
    "shop_orders_total",
    labels={"payment_type": "stripe"}
).inc()

# Gauge — queue size
self.metrics.gauge("shop_queue_size").set(42)

# Histogram — response size
self.metrics.histogram("shop_response_bytes").observe(1024)
```
