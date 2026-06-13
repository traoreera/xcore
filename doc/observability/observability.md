---
title: Observability
description: Structured logging, Prometheus metrics, distributed tracing (OpenTelemetry), liveness/readiness health checks, and per-plugin CPU/memory profiling for XCore.
icon: material/eye
---

# Observability

XCore intègre quatre piliers d'observabilité disponibles sans configuration : logging structuré, métriques (Prometheus-ready), tracing distribué (OpenTelemetry), health checks liveness/readiness, et profilage CPU/mémoire par plugin.

---

### Composants

| Pilier | Classe | Accès plugin |
|--------|--------|--------------|
| Logging | `XcoreLogger` | `self.logger` |
| Métriques | `MetricsRegistry` | `self.metrics` |
| Tracing | `Tracer` | `self.tracer` |
| Health | `HealthChecker` | `self.health` |
| Profilage | `PluginProfiler` | — (kernel uniquement) |

---

## 1. Logging structuré

Le logger accepte des kwargs arbitraires comme champs contextuels. En mode `text` ils sont appendés en fin de ligne ; en mode `json` ils deviennent des champs JSON.

```python linenums="1"
class Plugin(TrustedBase):
    async def handle(self, action, payload):
        self.logger.info("action reçue", action=action, tenant=self.ctx.tenant_id)
        self.logger.error("db injoignable", service="db", error=str(e))
```

Ne jamais utiliser `logging.getLogger()` — toujours `get_logger()` ou `self.logger`.

```yaml title="integration.yaml"
observability:
  logging:
    level: INFO          # DEBUG | INFO | WARNING | ERROR | CRITICAL
    output: json         # "text" | "json"
    file: log/app.log    # null pour désactiver la rotation fichier
    max_bytes: 52428800  # 50 MB
    backup_count: 10
```

---

## 2. Métriques

### Backends

| Backend | Usage | Scrape |
|---------|-------|--------|
| `memory` | Dev / tests | — |
| `prometheus` | Production | `GET {prefix}/ipc/metrics` |

```python linenums="1"
class Plugin(TrustedBase):
    async def handle(self, action, payload):
        self.metrics.counter("orders_total", labels={"status": "ok"}).inc()
        self.metrics.gauge("queue_size").set(42)
        self.metrics.histogram("response_bytes").observe(len(str(result)))
```

```yaml title="integration.yaml"
observability:
  metrics:
    enabled: true
    backend: prometheus   # "memory" | "prometheus"
    prefix: myapp
```

---

## 3. Tracing distribué (OpenTelemetry)

Chaque appel plugin est automatiquement encapsulé dans un span par `TracingMiddleware`. La propagation du contexte est assurée par un `ContextVar` : si le Plugin A appelle le Plugin B via `supervisor.call()`, les deux spans partagent le même `trace_id`.

```python linenums="1"
async def handle(self, action, payload):
    with self.tracer.span("heavy_task") as span:
        span.set_attribute("items", len(payload))
        await self._process(payload)
```

Pour les plugins **sandboxed**, le `trace_id` est injecté dans le payload sous la clé `__trace__` pour que le subprocess puisse logger avec le même identifiant.

### Backends

| Backend | Comportement |
|---------|-------------|
| `noop` (défaut) | In-memory, zéro export — utile en dev |
| `opentelemetry` | Export OTLP vers Jaeger, Tempo, ou OTel Collector |

### Activation OpenTelemetry

```bash
pip install "xcore[otel]"
# ou: opentelemetry-sdk opentelemetry-exporter-otlp-proto-grpc
```

```yaml title="integration.yaml"
observability:
  tracing:
    enabled: true
    backend: opentelemetry
    service_name: my-service
    endpoint: otel-collector:4317     # gRPC (Jaeger / Tempo / OTel Collector)
    # endpoint: http://host:4318/v1/traces  # HTTP alternatif
    use_grpc: true    # true = OTLP gRPC, false = OTLP HTTP
```

### Accès au trace_id courant

```python
from xcore.kernel.observability import get_current_trace_id, get_current_span_id

trace_id = get_current_trace_id()   # None hors d'un span
```

---

## 4. Health Checks (liveness / readiness)

XCore distingue deux types de checks :

| Type | Question | Endpoint k8s |
|------|----------|-------------|
| **liveness** | Le processus est-il vivant ? | `/health/live` → livenessProbe |
| **readiness** | Peut-il recevoir du trafic ? | `/health/ready` → readinessProbe |

### Checks enregistrés automatiquement

Au démarrage, `HealthChecker` enregistre deux checks de liveness :

| Nom | Kind | Description |
|-----|------|-------------|
| `process` | liveness | Toujours `healthy` — confirme que le processus tourne |
| `event_loop` | liveness | Coroutine vide — confirme que la boucle async répond |

Les services (`db`, `cache`, etc.) sont enregistrés automatiquement en **readiness**.

### Dans un plugin (SDK)

```python linenums="1"
from xcore.sdk import health_check

class Plugin(TrustedBase):

    @health_check("payment_api", kind="readiness")
    async def check_api(self) -> tuple[bool, str]:
        ok = await self._ping_api()
        return ok, "ok" if ok else "timeout"

    @health_check("internal_queue", kind="liveness")
    async def check_queue(self) -> tuple[bool, str]:
        return len(self.queue) < 1000, "queue ok"
```

### Endpoints

| Endpoint | Contenu |
|----------|---------|
| `GET {prefix}/ipc/health` | Tous les checks (liveness + readiness) |
| `GET {prefix}/ipc/health/live` | Liveness seul |
| `GET {prefix}/ipc/health/ready` | Readiness seul |

Réponse type :

```json
{
  "status": "healthy",
  "checks": {
    "process":     { "status": "healthy",   "message": "running",    "duration_ms": 0.01 },
    "event_loop":  { "status": "healthy",   "message": "responsive", "duration_ms": 0.12 },
    "db":          { "status": "healthy",   "message": "ok",         "duration_ms": 3.40 },
    "cache":       { "status": "degraded",  "message": "slow",       "duration_ms": 280.0 }
  }
}
```

!!! tip "Load balancer"
    Pointez votre load balancer (ou Kubernetes readinessProbe) sur `/health/ready`. En cas de DB down, ce endpoint retourne `unhealthy` et le pod est retiré du pool — sans redémarrer le processus.

---

## 5. Profilage CPU / Mémoire par plugin

`PluginProfiler` collecte toutes les 15 secondes le RSS et le CPU de chaque plugin via `psutil`.

- **Plugins trusted** : mesure le processus principal (partagé)
- **Plugins sandboxed** : mesure le subprocess isolé via son PID ; le PID est mis à jour automatiquement après chaque restart

### Accès aux métriques

**JSON (debug rapide) :**

```
GET {prefix}/ipc/plugins/metrics
```

```json
{
  "status": "enabled",
  "plugins": {
    "shop":    { "pid": null,  "rss_mb": 45.2, "cpu_percent": 1.3, "sampled_at": 1234.5 },
    "billing": { "pid": 12345, "rss_mb": 18.7, "cpu_percent": 0.4, "sampled_at": 1234.5 }
  }
}
```

**Prometheus (si `backend: prometheus`) :**

| Métrique | Labels | Description |
|----------|--------|-------------|
| `plugin_memory_rss_mb` | `plugin` | RSS en mégaoctets |
| `plugin_cpu_percent` | `plugin` | CPU % (moyenne sur l'intervalle) |

Ces métriques sont visibles dans `GET {prefix}/ipc/metrics` et scrapables par Prometheus.

!!! note "psutil requis"
    `psutil` est inclus dans les dépendances dev. En production, vérifier qu'il est installé : `pip install psutil`.

---

## Configuration YAML complète

```yaml linenums="1" title="integration.yaml"
observability:
  logging:
    level: INFO
    output: json          # "text" | "json"
    file: log/app.log

  metrics:
    enabled: true
    backend: prometheus   # "memory" | "prometheus"
    prefix: myapp

  tracing:
    enabled: true
    backend: opentelemetry  # "noop" | "opentelemetry"
    service_name: my-service
    endpoint: otel-collector:4317
    use_grpc: true
```
