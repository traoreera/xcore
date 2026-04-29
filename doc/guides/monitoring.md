# Monitoring & Observabilité

XCore embarque logging structuré, métriques et tracing. Tous sont configurables via `xcore.yaml`.

---

## Configuration

```yaml
observability:
  logging:
    level: "INFO"           # DEBUG | INFO | WARNING | ERROR
    format: "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    file: "log/app.log"     # null = stdout uniquement
    max_bytes: 10485760     # 10 MB
    backup_count: 5

  metrics:
    enabled: true
    backend: memory         # memory | prometheus | statsd
    prefix: "xcore"

  tracing:
    enabled: false
    backend: noop           # noop | opentelemetry | jaeger
    service_name: "xcore"
    endpoint: null          # ex: http://jaeger:14268/api/traces
```

---

## Logging

### Dans un plugin

```python
from xcore.kernel.observability import get_logger

class Plugin(TrustedBase):

    async def on_load(self):
        self.logger = get_logger(f"plugin.{self.ctx.name}")

    @action("process")
    async def process(self, payload: dict) -> dict:
        self.logger.info("Traitement démarré", extra={"payload_size": len(payload)})
        try:
            result = await self._do_work(payload)
            self.logger.debug("Succès", extra={"result_keys": list(result.keys())})
            return ok(**result)
        except Exception as e:
            self.logger.error(f"Échec: {e}", exc_info=True)
            return error(str(e), "processing_error")
```

### Configuration du niveau par module

```python
import logging
logging.getLogger("xcore.runtime").setLevel(logging.DEBUG)
logging.getLogger("xcore.permissions").setLevel(logging.WARNING)
```

---

## Métriques

```python
from xcore.kernel.observability import MetricsRegistry, Counter, Gauge, Histogram

class Plugin(TrustedBase):

    async def on_load(self):
        self.metrics: MetricsRegistry = self.ctx.metrics

        # Compteur d'appels
        self.requests = self.metrics.counter(
            "plugin_requests_total",
            labels={"plugin": "mon_plugin"},
        )
        # Gauge — valeur instantanée
        self.active_sessions = self.metrics.gauge("active_sessions")

        # Histogram — distribution de latences
        self.latency = self.metrics.histogram(
            "request_duration_seconds",
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0],
        )

    @action("process")
    async def process(self, payload: dict) -> dict:
        import time
        start = time.monotonic()
        self.requests.inc()

        result = await self._work(payload)

        self.latency.observe(time.monotonic() - start)
        return ok(**result)
```

---

## Tracing

```python
from xcore.kernel.observability import Tracer, Span

class Plugin(TrustedBase):

    async def on_load(self):
        self.tracer: Tracer = self.ctx.tracer

    @action("complex_operation")
    async def complex_operation(self, payload: dict) -> dict:
        with self.tracer.start_span("complex_operation") as span:
            span.set_attribute("user_id", payload.get("user_id"))

            with self.tracer.start_span("db_query") as db_span:
                result = await self._query_db(payload)
                db_span.set_attribute("rows_returned", len(result))

        return ok(data=result)
```

---

## Health Checks

```python
from xcore.kernel.observability import HealthChecker, HealthStatus

class Plugin(TrustedBase):

    async def on_load(self):
        health: HealthChecker = self.ctx.health

        # Enregistrer un check custom
        health.register("mon_plugin.db", self._check_db)
        health.register("mon_plugin.external_api", self._check_api)

    async def _check_db(self) -> HealthStatus:
        try:
            async with self.db.session() as s:
                await s.execute("SELECT 1")
            return HealthStatus(healthy=True, message="DB OK")
        except Exception as e:
            return HealthStatus(healthy=False, message=str(e))
```

```bash
# Vérifier l'état depuis le CLI
poetry run xcore health
poetry run xcore health --json

# État des services uniquement
poetry run xcore services status
```

---

## Logs en temps réel

Les logs structurés sont écrits dans `log/app.log` (configurable). Pour les filtrer :

```bash
# Tous les logs en live
tail -f log/app.log

# Erreurs uniquement
grep '"level":"ERROR"' log/app.log | jq .

# Logs d'un plugin spécifique
grep 'plugin.mon_plugin' log/app.log

# Logs de permissions
grep 'xcore.permissions' log/app.log
```
