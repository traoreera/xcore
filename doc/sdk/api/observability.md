---
title: Observabilité SDK
description: Décorateurs et mixin pour le logging, métriques, tracing et health checks dans les plugins.
icon: material/eye-outline
---

# Observabilité SDK

Le SDK fournit des décorateurs déclaratifs et des propriétés directes sur `TrustedBase` pour instrumenter vos plugins sans boilerplate.

```python
from xcore.sdk import traced, counted, timed, health_check, ObservabilityMixin
```

---

## Propriétés TrustedBase

Tout plugin héritant de `TrustedBase` dispose de ces propriétés sans aucune configuration :

| Propriété | Type | Description |
|-----------|------|-------------|
| `self.logger` | `XcoreLogger` | Logger structuré namespaced `xcore.plugin.<nom>` |
| `self.metrics` | `MetricsRegistry` | Registry de métriques |
| `self.tracer` | `Tracer` | Tracer pour les spans |
| `self.health` | `HealthChecker` | Registre de health checks |

```python linenums="1"
class Plugin(TrustedBase):
    async def handle(self, action, payload):
        self.logger.info("action reçue", action=action)
        self.metrics.counter("calls_total", labels={"plugin": "shop"}).inc()

        with self.tracer.span("process") as span:
            span.set_attribute("action", action)
            result = await self._process(payload)

        return ok(result=result)
```

---

## self.logger

Logger structuré — accepte des kwargs arbitraires comme champs contextuels.

```python linenums="1"
self.logger.info("commande créée", order_id="ORD-42", tenant="acme")
self.logger.warning("stock faible", produit="SKU-99", quantité=3)
self.logger.error("paiement échoué", raison="fonds insuffisants", code=402)
self.logger.debug("cache hit", clé="user:123", ttl_restant=240)
```

En dehors d'un plugin, utiliser `get_logger` directement :

```python
from xcore.sdk import get_logger

logger = get_logger("mon_module")
logger.info("démarrage", version="1.0")
```

---

## @traced

Enveloppe une méthode dans un span de tracing. Sans effet si `self.tracer` est `None`.

```python linenums="1"
from xcore.sdk import traced

@traced("get_user")
async def get_user(self, payload: dict) -> dict:
    user = await self.db.fetch_one("SELECT * FROM users WHERE id = :id", {"id": payload["id"]})
    return ok(user=user)
```

En cas d'exception, le span est marqué `status="error"` avant que l'exception soit relancée.

**Paramètres**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `span_name` | `str \| None` | nom de la fonction | Nom du span dans le tracer |

---

## @counted

Incrémente un counter après chaque appel réussi. Sans effet si `self.metrics` est `None`.

```python linenums="1"
from xcore.sdk import counted

@counted("shop_orders_created_total", labels={"type": "standard"})
async def create_order(self, payload: dict) -> dict:
    ...
```

**Paramètres**

| Nom | Type | Défaut | Description |
|-----|------|--------|-------------|
| `metric_name` | `str` | — | Nom du counter dans `self.metrics` |
| `labels` | `dict \| None` | `None` | Labels Prometheus |

---

## @timed

Enregistre la durée d'exécution dans un histogram. Sans effet si `self.metrics` est `None`.

```python linenums="1"
from xcore.sdk import timed

@timed("shop_search_duration_seconds")
async def search(self, payload: dict) -> dict:
    results = await self.db.fetch_all("SELECT ...")
    return ok(results=results)
```

La durée est mesurée de l'entrée de la méthode au retour, incluant toute attente I/O.

**Paramètres**

| Nom | Type | Description |
|-----|------|-------------|
| `metric_name` | `str` | Nom de l'histogram dans `self.metrics` |

---

## @health_check

Marque une méthode comme health check. La méthode doit retourner `(bool, str)`.

```python linenums="1"
from xcore.sdk import health_check

@health_check("shop.payment_gateway")
async def check_gateway(self) -> tuple[bool, str]:
    try:
        await self._ping_gateway()
        return True, "ok"
    except Exception as e:
        return False, str(e)

@health_check("shop.db")
async def check_db(self) -> tuple[bool, str]:
    try:
        await self.get_service("db").execute("SELECT 1")
        return True, "ok"
    except KeyError:
        return False, "service 'db' absent"
```

Les checks sont enregistrés automatiquement dans `self.ctx.health` au `on_load()` via `ObservabilityMixin`.

**Paramètres**

| Nom | Type | Description |
|-----|------|-------------|
| `check_name` | `str` | Identifiant exposé dans `GET /ipc/health` |

---

## ObservabilityMixin

Composé automatiquement par `AutoMixin`. Fournit :

- Enregistrement automatique de tous les `@health_check` au `on_load()`
- Désenregistrement automatique au `on_unload()`

Sans `AutoMixin`, hériter explicitement :

```python linenums="1"
from xcore.sdk import ObservabilityMixin
from xcore import TrustedBase

class Plugin(ObservabilityMixin, TrustedBase):

    @health_check("my_plugin.db")
    async def check_db(self) -> tuple[bool, str]:
        ...

    async def handle(self, action, payload):
        self.logger.info("handling", action=action)
        return ok()
```

---

## Combinaison de décorateurs

Les décorateurs se combinent. L'ordre recommandé : `@traced` → `@counted` → `@timed` (de l'extérieur vers l'intérieur).

```python linenums="1"
from xcore.sdk import traced, counted, timed

class Plugin(TrustedBase):

    @traced("process_order")
    @counted("shop_orders_processed_total", labels={"status": "success"})
    @timed("shop_order_processing_seconds")
    async def process_order(self, payload: dict) -> dict:
        self.logger.info("traitement commande", order_id=payload["id"])

        with self.tracer.span("validate") as span:
            span.set_attribute("items", len(payload["items"]))
            await self._validate(payload)

        result = await self._persist(payload)
        self.metrics.gauge("shop_pending_orders", labels={"region": "eu"}).dec()
        return ok(result=result)
```

---

## Accès direct aux métriques

Pour des opérations non couvertes par les décorateurs :

```python linenums="1"
# Counter avec labels dynamiques
self.metrics.counter(
    "shop_api_calls_total",
    labels={"endpoint": action, "status": "ok"}
).inc()

# Gauge — file d'attente
self.metrics.gauge("shop_queue_size", labels={"queue": "emails"}).set(len(queue))

# Histogram — taille des réponses
self.metrics.histogram("shop_response_bytes").observe(len(str(result)))
```
