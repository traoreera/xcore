# Monitoring & Observability

XCore provides a comprehensive observability system to monitor your plugins and services in production.

## Overview

The XCore observability system is built on four pillars:

1.  **Metrics**: Counters, gauges, and histograms to measure performance.
2.  **Health Checks**: Real-time status monitoring of services and plugins.
3.  **Logging**: Structured logging with configurable levels and rotation.
4.  **Tracing**: Distributed tracing for debugging complex request flows.

## Metrics

The metrics registry supports three primary types:

-   **Counter**: Values that only increase (e.g., total requests).
-   **Gauge**: Values that can go up or down (e.g., active connections).
-   **Histogram**: Distribution of values (e.g., request latency).

### Basic Usage

```python
from xcore.kernel.observability.metrics import MetricsRegistry
from xcore.sdk import TrustedBase

class Plugin(TrustedBase):
    async def on_load(self) -> None:
        self.metrics = MetricsRegistry()

        # Define metrics
        self.request_count = self.metrics.counter("http.requests.total")
        self.active_connections = self.metrics.gauge("connections.active")
        self.request_latency = self.metrics.histogram("http.request.duration")

    def get_router(self):
        from fastapi import APIRouter
        import time
        router = APIRouter()

        @router.get("/data")
        async def get_data():
            start = time.monotonic()
            self.active_connections.inc()
            try:
                # Logic here...
                self.request_count.inc()
                return {"status": "ok"}
            finally:
                self.request_latency.observe(time.monotonic() - start)
                self.active_connections.dec()
        return router
```

### Metrics with Labels

Labels allow you to add dimensions to your metrics for more granular analysis.

```python
self.request_count = self.metrics.counter(
    "http.requests.total",
    labels={"plugin": "my_plugin", "method": "GET"}
)
```

## Health Checks

Health checks allow you to monitor the status of your dependencies and internal state.

### Registering Checks

```python
from xcore.kernel.observability.health import HealthChecker

class Plugin(TrustedBase):
    async def on_load(self) -> None:
        self.health = HealthChecker()
        self.db = self.get_service("db")

        @self.health.register("database")
        async def check_db():
            try:
                async with self.db.session() as session:
                    await session.execute("SELECT 1")
                return True, "Database OK"
            except Exception as e:
                return False, str(e)
```

## Logging

XCore uses structured logging to make logs easier to parse and analyze.

### Configuration (`xcore.yaml`)

```yaml
observability:
  logging:
    level: INFO
    format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: "logs/app.log"
```

### Usage in Plugins

```python
import logging
logger = logging.getLogger("xcore.plugin.my_plugin")

class Plugin(TrustedBase):
    async def on_load(self):
        logger.info("Plugin loaded successfully", extra={"version": "1.0.0"})
```

## Tracing

Tracing helps you visualize the flow of requests across multiple plugins and services.

```python
from xcore.kernel.observability.tracing import Tracer

class Plugin(TrustedBase):
    async def on_load(self):
        self.tracer = Tracer(service_name="my_plugin")

    async def handle(self, action, payload):
        with self.tracer.span("process_action", action=action) as span:
            # Operation logic...
            span.set_attribute("result", "success")
            return ok()
```

## Best Practices

1.  **Meaningful Names**: Use clear, dot-separated names for metrics (e.g., `api.user.login_success`).
2.  **Avoid High Cardinality**: Don't use unique IDs (like user IDs) as labels in metrics.
3.  **Use Appropriate Levels**: Use `DEBUG` for verbose info, `INFO` for general flow, and `ERROR` for actual failures.
4.  **Monitor Dependencies**: Always include health checks for external APIs or databases your plugin relies on.
