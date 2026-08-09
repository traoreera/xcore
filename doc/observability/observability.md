---
title: Observability
description: Structured logging, Prometheus metrics, and distributed tracing for Xcore.
icon: material/eye
---

# Observability

Xcore integrates three core pillars of observability: structured logging, metrics (memory or Prometheus), and tracing. These are available in every plugin via direct properties on `TrustedBase` without any additional configuration.

---

### Components

| Pillar | Class | Plugin Access |
|--------|--------|-------------|
| Logging | `XcoreLogger` | `self.logger` |
| Metrics | `MetricsRegistry` / `PrometheusMetricsRegistry` | `self.metrics` |
| Tracing | `Tracer` | `self.tracer` |
| Health | `HealthChecker` | `self.health` |

---

## 1. Structured Logging

The logger accepts arbitrary fields as kwargs. In `text` mode, these are appended to the end of the line. In `json` mode, they become JSON fields.

```python linenums="1"
class Plugin(TrustedBase):
    async def handle(self, action, payload):
        self.logger.info("action received", action=action, tenant=self.ctx.tenant_id)
        self.logger.error("database inaccessible", service="db", error=str(e))
        self.logger.debug("cache miss", key="user:123", ttl=300)
```

**Text Output:**
```
2026-05-29 14:08:03 [INFO    ] xcore.plugin.my_plugin — action received  action=ping  tenant=acme
```

**JSON Output:**
```json
{"ts":"2026-05-29T14:08:03.123+00:00","level":"INFO","logger":"xcore.plugin.my_plugin",
 "msg":"action received","action":"ping","tenant":"acme"}
```

---

## 2. Metrics

### Backends

| Backend | Usage | Endpoint |
|---------|-------|----------|
| `memory` (default) | Testing, development | `GET /ipc/metrics` → JSON |
| `prometheus` | Production | `GET /metrics` → Prometheus text format |

### Counters, Gauges, Histograms

```python linenums="1"
class Plugin(TrustedBase):
    async def handle(self, action, payload):
        # Counter — monotonically increasing value
        self.metrics.counter(
            "orders_created_total",
            labels={"plugin": "shop", "env": "prod"}
        ).inc()

        # Gauge — value that can go up and down
        self.metrics.gauge(
            "queue_size",
            labels={"queue": "emails"}
        ).set(42)

        # Histogram — distribution of values (latencies, sizes)
        self.metrics.histogram("order_processing_seconds").observe(0.142)
```

### Prometheus Endpoint

When `backend: prometheus` is configured, Xcore automatically mounts `/metrics` in the Prometheus text format:

```
# HELP plugin_calls_total_total
# TYPE plugin_calls_total_total counter
plugin_calls_total_total{action="create_order",plugin="shop"} 42.0
# HELP plugin_latency_seconds
# TYPE plugin_latency_seconds histogram
plugin_latency_seconds_sum 1.23
plugin_latency_seconds_count 42
```

!!! warning "Label Cardinality"
    Never use user IDs, raw URLs, or other high-cardinality values as metric labels. Doing so can cause memory exhaustion in Prometheus.

---

## 3. Tracing

The `PluginSupervisor` automatically creates a span for every plugin invocation. You can create child spans for your internal operations.

```python linenums="1"
async def handle(self, action, payload):
    with self.tracer.span("validate_order") as span:
        span.set_attribute("order_id", payload["id"])
        span.set_attribute("items", len(payload["items"]))
        result = await self._validate(payload)

    with self.tracer.span("persist") as span:
        await self.db.execute(...)
        span.set_attribute("table", "orders")

    return ok(result=result)
```

**Span Properties:**

| Property | Type | Description |
|-----------|------|-------------|
| `trace_id` | `str` | Trace identifier |
| `span_id` | `str` | Span identifier |
| `duration_ms` | `float` | Duration in milliseconds |
| `status` | `str` | `"ok"` or `"error"` |
| `attributes` | `dict` | Custom metadata |

---

## 4. Health Checks

Service health checks (`db`, `cache`, `scheduler`) are registered **automatically** at startup. Plugins can add custom health checks either via the SDK or directly.

```python linenums="1"
from xcore.sdk import health_check

class Plugin(TrustedBase):

    # Via SDK decorator
    @health_check("shop.payment_gateway")
    async def check_gateway(self) -> tuple[bool, str]:
        try:
            await self._ping_gateway()
            return True, "ok"
        except Exception as e:
            return False, str(e)

    # Via direct access
    async def on_load(self):
        @self.health.register("shop.inventory_db")
        async def check_inventory():
            return await self.get_service("db").health_check()
```

**`GET /ipc/health` Response:**
```json
{
  "status": "healthy",
  "checks": {
    "db":                    {"status": "healthy", "message": "ok", "duration_ms": 1.2},
    "cache":                 {"status": "healthy", "message": "ok", "duration_ms": 0.8},
    "scheduler":             {"status": "healthy", "message": "ok", "duration_ms": 0.1},
    "shop.payment_gateway":  {"status": "degraded", "message": "timeout", "duration_ms": 5001.0}
  }
}
```

---

## API Reference

### `MetricsRegistry`

| Method | Returns | Description |
|---------|--------|-------------|
| `counter(name, labels)` | `Counter` | Creates or retrieves a counter. |
| `gauge(name, labels)` | `Gauge` | Creates or retrieves a gauge. |
| `histogram(name)` | `Histogram` | Creates or retrieves an histogram. |
| `snapshot()` | `dict` | In-memory snapshot — not available with Prometheus backend. |

### `Counter` / `Gauge` / `Histogram`

| Method | Description |
|---------|-------------|
| `Counter.inc(amount=1.0)` | Increments the counter. |
| `Gauge.set(v)` | Sets the gauge value. |
| `Gauge.inc(v)` / `Gauge.dec(v)` | Increments or decrements the gauge. |
| `Histogram.observe(v)` | Records an observation. |

### `Tracer`

| Method | Returns | Description |
|---------|--------|-------------|
| `span(name, **attrs)` | `ContextManager[Span]` | Starts a span and closes it when exiting the block. |

### `HealthChecker`

| Method | Description |
|---------|-------------|
| `register(name)` | Decorator — registers an `async () -> (bool, str)` function. |
| `run_all(timeout=5.0)` | Runs all checks and returns the report. |

---

## YAML Configuration

```yaml linenums="1" title="xcore.yaml"
observability:
  logging:
    level: "INFO"           # DEBUG | INFO | WARNING | ERROR | CRITICAL
    output: "text"          # "text" | "json"
    file: "log/app.log"     # optional — automatically rotated
    max_bytes: 52428800     # 50 MB per file
    backup_count: 10

  metrics:
    enabled: true
    backend: "memory"       # "memory" | "prometheus"
    prefix: "myapp"

  tracing:
    enabled: true
    backend: "noop"         # "noop" | "opentelemetry"
    service_name: "myapp"
    endpoint: ~             # OTLP URL if opentelemetry is used
```

---

## Common Gotchas

!!! danger "Prometheus Name Collision"
    Prometheus registers each metric globally. If two plugins use the same metric name with different labels, an error will be raised.
    **Fix**: Prefix metric names with the plugin name — e.g., `shop_orders_total`, not `orders_total`.

!!! warning "Unclosed Span"
    Always use `with self.tracer.span(...)`. The context manager guarantees that `span.end()` is called even if an exception is raised.

!!! info "Missing prometheus-client"
    If `backend: prometheus` is configured but `prometheus-client` is not installed, Xcore will silently fall back to the memory backend.
    **Fix**: `pip install prometheus-client`

---

## Best Practices

!!! success "Metric Naming"
    Prometheus convention: `<plugin>_<object>_<unit>_total` — e.g., `shop_orders_created_total`, `auth_login_duration_seconds`.

!!! tip "Health Check for External Dependencies"
    If your plugin calls a third-party API, register a dedicated `@health_check` — this is used by Kubernetes for readiness probes.

!!! tip "JSON Logs in Production"
    Switch to `output: json` in production environments so that log aggregators (Datadog, Loki, ELK) can directly index structured fields.
