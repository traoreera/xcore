---
title: Observability
description: Integrated logging, metrics, and distributed tracing for Xcore applications.
icon: material/eye
---

# Observability

Xcore provides built-in tools for monitoring the health, performance, and behavior of your application and its plugins. It integrates logging, metrics collection, and distributed tracing into a unified observability stack.

---

### Prerequisites

- [x] [Service Container](./services.md) overview understood
- [x] [Prometheus](https://prometheus.io/) (optional, for metrics collection)
- [x] [Jaeger/Zipkin](https://www.jaegertracing.io/) (optional, for trace visualization)

---

### Key Components

#### 1. Structured Logging
Xcore uses a structured logging approach. Logs are categorized by subsystem (kernel, services, plugins) and include contextual metadata like `tenant_id` and `request_id`.

```bash
# View real-time logs via CLI
make logs-live
```

#### 2. Metrics Registry
A lightweight registry for collecting application-level metrics. It supports Counters, Gauges, and Histograms.

```python linenums="1"
class Plugin(TrustedBase):
    async def on_load(self):
        # Register a counter
        self.call_counter = self.ctx.metrics.counter(
            "plugin_calls_total",
            labels={"plugin": self.name}
        )

    async def handle(self, action, payload):
        self.call_counter.inc()
        return ok()
```

#### 3. Distributed Tracing
Xcore automatically traces every call made through the `PluginSupervisor`. You can also create manual spans inside your plugin logic.

```python linenums="1"
async def process_data(self, data):
    with self.ctx.tracer.span("data_transformation", layer="processing") as span:
        result = await self.transform(data)
        span.set_attribute("items_count", len(data))
        return result
```

#### 4. Health Checks
The `HealthChecker` monitors the status of all framework components and plugins. It exposes a JSON endpoint (usually `/health`) that can be used by orchestrators like Kubernetes.

---

### Practical Guide

#### Instrumenting your Plugin
Always include basic metrics and spans in your `handle` method for production readiness.

```python linenums="1" hl_lines="6 10"
async def handle(self, action, payload):
    # The framework already started a span for this call.
    # You can access it via the current context if needed.

    start_time = time.monotonic()
    try:
        # Business logic here
        result = await self._do_work(payload)
        return ok(result=result)
    finally:
        # Record execution time in a histogram
        duration = time.monotonic() - start_time
        self.ctx.metrics.histogram("action_duration_seconds").observe(duration)
```

---

### API Reference

#### `MetricsRegistry`
| Method | Return Type | Description |
|--------|-------------|-------------|
| `counter(name, labels)` | `Counter` | Increment-only metric. |
| `gauge(name, labels)` | `Gauge` | Metric that can go up and down (e.g., queue size). |
| `histogram(name)` | `Histogram` | Tracks the distribution of values (e.g., latency). |

#### `Tracer`
| Method | Return Type | Description |
|--------|-------------|-------------|
| `span(name, **attrs)` | `ContextManager` | Starts a new child span. |
| `set_attribute(k, v)` | `None` | Adds metadata to the current span. |

---

### YAML Configuration

```yaml linenums="1" title="xcore.yaml"
observability:
  logging:
    level: "INFO"
    format: "json"      # str — "text" | "json". Default: "text"

  metrics:
    enabled: true
    export_interval: 60 # int — Seconds between exports. Default: 60

  tracing:
    enabled: true
    sample_rate: 1.0    # float — 0.0 to 1.0. Default: 1.0
```

---

### Common Errors & Pitfalls

!!! danger "Metric Name Collisions"
    If two plugins try to register a metric with the same name but different labels, the registry may raise a `ValueError` or return the wrong metric instance.
    **Fix**: Always prefix your metric names with your plugin name (e.g., `myplugin_request_total`).

!!! warning "Excessive Cardinality"
    Avoid using high-cardinality values (like user IDs or raw URLs) as labels in your metrics. This can lead to memory exhaustion in your metrics backend.

!!! failure "Trace Leakage"
    Always use the `with tracer.span(...)` context manager. If you manually start a span but forget to `end()` it, your traces will be incomplete and resources may leak.

---

### Best Practices

!!! success "Use Health Checks"
    Implement a custom health check in your plugin if it depends on an external API or hardware. This allows the supervisor to know if your plugin is functionally degraded.

!!! tip "Contextual Logging"
    Use `logger.info("message", extra={"key": "val"})` instead of f-strings. This allows structured log parsers (like ELK or Datadog) to index your data efficiently.
