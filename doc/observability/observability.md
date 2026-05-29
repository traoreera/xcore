---
title: Observabilité
description: Logging structuré, métriques Prometheus et tracing distribué pour xcore.
icon: material/eye
---

# Observabilité

xcore intègre trois piliers d'observabilité : logging structuré, métriques (mémoire ou Prometheus) et tracing. Ils sont disponibles dans chaque plugin via des propriétés directes sur `TrustedBase`, sans configuration supplémentaire.

---

### Composants

| Pilier | Classe | Accès plugin |
|--------|--------|-------------|
| Logging | `XcoreLogger` | `self.logger` |
| Métriques | `MetricsRegistry` / `PrometheusMetricsRegistry` | `self.metrics` |
| Tracing | `Tracer` | `self.tracer` |
| Health | `HealthChecker` | `self.health` |

---

## 1. Logging structuré

Le logger accepte des champs arbitraires en kwargs. En mode `text` ils s'affichent en fin de ligne, en mode `json` ils deviennent des champs JSON.

```python linenums="1"
class Plugin(TrustedBase):
    async def handle(self, action, payload):
        self.logger.info("action reçue", action=action, tenant=self.ctx.tenant_id)
        self.logger.error("base de données inaccessible", service="db", erreur=str(e))
        self.logger.debug("cache miss", clé="user:123", ttl=300)
```

**Sortie texte :**
```
2026-05-29 14:08:03 [INFO    ] xcore.plugin.my_plugin — action reçue  action=ping  tenant=acme
```

**Sortie JSON :**
```json
{"ts":"2026-05-29T14:08:03.123+00:00","level":"INFO","logger":"xcore.plugin.my_plugin",
 "msg":"action reçue","action":"ping","tenant":"acme"}
```

---

## 2. Métriques

### Backends

| Backend | Usage | Endpoint |
|---------|-------|----------|
| `memory` (défaut) | Tests, développement | `GET /ipc/metrics` → JSON |
| `prometheus` | Production | `GET /metrics` → format texte Prometheus |

### Counters, Gauges, Histograms

```python linenums="1"
class Plugin(TrustedBase):
    async def handle(self, action, payload):
        # Counter — valeur qui ne fait qu'augmenter
        self.metrics.counter(
            "orders_created_total",
            labels={"plugin": "shop", "env": "prod"}
        ).inc()

        # Gauge — valeur qui monte et descend
        self.metrics.gauge(
            "queue_size",
            labels={"queue": "emails"}
        ).set(42)

        # Histogram — distribution de valeurs (latences, tailles)
        self.metrics.histogram("order_processing_seconds").observe(0.142)
```

### Endpoint Prometheus

Quand `backend: prometheus`, xcore monte automatiquement `/metrics` au format Prometheus :

```
# HELP plugin_calls_total_total
# TYPE plugin_calls_total_total counter
plugin_calls_total_total{action="create_order",plugin="shop"} 42.0
# HELP plugin_latency_seconds
# TYPE plugin_latency_seconds histogram
plugin_latency_seconds_sum 1.23
plugin_latency_seconds_count 42
```

!!! warning "Cardinale des labels"
    N'utilisez jamais d'IDs utilisateurs, d'URLs brutes ou d'autres valeurs à forte cardinalité comme labels. Cela peut provoquer une explosion mémoire dans Prometheus.

---

## 3. Tracing

Le `PluginSupervisor` crée automatiquement un span par appel de plugin. Vous pouvez créer des spans enfants pour vos opérations internes.

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

**Propriétés d'un `Span` :**

| Propriété | Type | Description |
|-----------|------|-------------|
| `trace_id` | `str` | Identifiant de trace |
| `span_id` | `str` | Identifiant de span |
| `duration_ms` | `float` | Durée en millisecondes |
| `status` | `str` | `"ok"` ou `"error"` |
| `attributes` | `dict` | Metadata custom |

---

## 4. Health Checks

Les health checks des services (`db`, `cache`, `scheduler`) sont enregistrés **automatiquement** au démarrage. Les plugins peuvent en ajouter via le SDK ou directement.

```python linenums="1"
from xcore.sdk import health_check

class Plugin(TrustedBase):

    # Via décorateur SDK
    @health_check("shop.payment_gateway")
    async def check_gateway(self) -> tuple[bool, str]:
        try:
            await self._ping_gateway()
            return True, "ok"
        except Exception as e:
            return False, str(e)

    # Via accès direct
    async def on_load(self):
        @self.health.register("shop.inventory_db")
        async def check_inventory():
            return await self.get_service("db").health_check()
```

**Réponse `GET /ipc/health` :**
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

| Méthode | Retour | Description |
|---------|--------|-------------|
| `counter(name, labels)` | `Counter` | Crée ou récupère un counter. |
| `gauge(name, labels)` | `Gauge` | Crée ou récupère un gauge. |
| `histogram(name)` | `Histogram` | Crée ou récupère un histogram. |
| `snapshot()` | `dict` | Instantané mémoire — non disponible avec backend Prometheus. |

### `Counter` / `Gauge` / `Histogram`

| Méthode | Description |
|---------|-------------|
| `Counter.inc(amount=1.0)` | Incrémente. |
| `Gauge.set(v)` | Fixe la valeur. |
| `Gauge.inc(v)` / `Gauge.dec(v)` | Incrémente / décrémente. |
| `Histogram.observe(v)` | Enregistre une observation. |

### `Tracer`

| Méthode | Retour | Description |
|---------|--------|-------------|
| `span(name, **attrs)` | `ContextManager[Span]` | Démarre un span, le ferme à la sortie du bloc. |

### `HealthChecker`

| Méthode | Description |
|---------|-------------|
| `register(name)` | Décorateur — enregistre une fonction `async () -> (bool, str)`. |
| `run_all(timeout=5.0)` | Lance tous les checks et retourne le rapport. |

---

## Configuration YAML

```yaml linenums="1" title="xcore.yaml"
observability:
  logging:
    level: "INFO"           # DEBUG | INFO | WARNING | ERROR | CRITICAL
    output: "text"          # "text" | "json"
    file: "log/app.log"     # optionnel — rotation automatique
    max_bytes: 52428800     # 50 MB par fichier
    backup_count: 10

  metrics:
    enabled: true
    backend: "memory"       # "memory" | "prometheus"
    prefix: "myapp"

  tracing:
    enabled: true
    backend: "noop"         # "noop" | "opentelemetry"
    service_name: "myapp"
    endpoint: ~             # URL OTLP si opentelemetry
```

---

## Erreurs fréquentes

!!! danger "Collision de noms Prometheus"
    Prometheus enregistre chaque metric globalement. Si deux plugins utilisent le même nom avec des labels différents, une erreur est levée.
    **Fix** : préfixer les noms par le plugin — `shop_orders_total`, pas `orders_total`.

!!! warning "Span non fermé"
    Toujours utiliser `with self.tracer.span(...)`. Le context manager garantit que `span.end()` est appelé même en cas d'exception.

!!! info "prometheus-client absent"
    Si `backend: prometheus` est configuré mais que `prometheus_client` n'est pas installé, xcore bascule silencieusement sur le backend mémoire.
    **Fix** : `pip install prometheus-client`

---

## Bonnes pratiques

!!! success "Nommage des métriques"
    Convention Prometheus : `<plugin>_<objet>_<unité>_total` — ex: `shop_orders_created_total`, `auth_login_duration_seconds`.

!!! tip "Health check pour les dépendances externes"
    Si votre plugin appelle une API tierce, enregistrez un `@health_check` dédié — utilisé par Kubernetes pour les readiness probes.

!!! tip "Logs JSON en production"
    Passez à `output: json` en production pour que les agrégateurs (Datadog, Loki, ELK) indexent les champs structurés directement.
