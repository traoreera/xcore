# Monitoring et Observabilité

XCore fournit un système d'observabilité complet pour surveiller vos plugins et services en production.

## Vue d'ensemble

Le système d'observabilité XCore comprend quatre piliers :

1. **Métriques** — Compteurs, gauges et histogrammes pour mesurer les performances
2. **Health Checks** — Vérification de l'état de santé des services
3. **Logging** — Journalisation structurée avec niveaux configurables
4. **Tracing** — Traçage distribué pour le debugging

## Métriques

Le registre de métriques supporte trois types de métriques :

- **Counter** — Valeurs qui s'incrémentent (ex: nombre de requêtes)
- **Gauge** — Valeurs qui montent ou descendent (ex: nombre de connexions)
- **Histogram** — Distribution de valeurs (ex: latence des requêtes)

### Utilisation de base

```python
from xcore.kernel.observability.metrics import MetricsRegistry
from xcore.sdk import TrustedBase


class Plugin(TrustedBase):

    async def on_load(self) -> None:
        # Créer un registre de métriques
        self.metrics = MetricsRegistry()

        # Créer des métriques
        self.request_count = self.metrics.counter("http.requests.total")
        self.active_connections = self.metrics.gauge("connections.active")
        self.request_latency = self.metrics.histogram("http.request.duration")

    def get_router(self):
        from fastapi import APIRouter, Request
        import time

        router = APIRouter()

        @router.get("/api/data")
        async def get_data(request: Request):
            start = time.monotonic()
            self.active_connections.inc()

            try:
                # Votre logique ici
                data = await self._fetch_data()

                # Incrémenter le compteur de requêtes
                self.request_count.inc()

                return {"data": data}
            finally:
                # Enregistrer la latence
                latency = time.monotonic() - start
                self.request_latency.observe(latency)
                self.active_connections.dec()

        return router
```

### Métriques avec labels

```python
class Plugin(TrustedBase):

    async def on_load(self) -> None:
        self.metrics = MetricsRegistry()

        # Métriques avec labels pour une meilleure granularité
        self.request_count = self.metrics.counter(
            "http.requests.total",
            labels={"plugin": "my_plugin"}
        )
        self.error_count = self.metrics.counter(
            "http.errors.total",
            labels={"plugin": "my_plugin"}
        )

    def get_router(self):
        from fastapi import APIRouter, Request

        router = APIRouter()

        @router.get("/items/{item_id}")
        async def get_item(item_id: str, request: Request):
            try:
                # Incrémenter avec un label dynamique
                self.metrics.counter(
                    "http.requests.total",
                    labels={"endpoint": "get_item", "method": "GET"}
                ).inc()

                item = await self._get_item(item_id)
                return item

            except Exception as e:
                # Compter les erreurs par type
                self.metrics.counter(
                    "http.errors.total",
                    labels={"endpoint": "get_item", "error_type": type(e).__name__}
                ).inc()
                raise

        return router
```

### Exposition des métriques

```python
def get_router(self):
    from fastapi import APIRouter

    router = APIRouter()

    @router.get("/metrics")
    async def get_metrics():
        """Exposer les métriques au format JSON."""
        return self.metrics.snapshot()

    return router
```

### Exemple de sortie

```json
{
  "counters": {
    "http.requests.total:{\"plugin\": \"my_plugin\"}": 42,
    "http.requests.total:{\"endpoint\": \"get_item\", \"method\": \"GET\"}": 15
  },
  "gauges": {
    "connections.active:{}": 5,
    "memory.usage_mb:{}": 128.5
  },
  "histograms": {
    "http.request.duration": {
      "count": 42,
      "sum": 0.840,
      "mean": 0.020
    }
  }
}
```

## Health Checks

Le système de health checks permet de vérifier l'état de santé des composants.

### Création de checks

```python
from xcore.kernel.observability.health import HealthChecker, HealthStatus
from xcore.sdk import TrustedBase


class Plugin(TrustedBase):

    async def on_load(self) -> None:
        self.db = self.get_service("db")
        self.cache = self.get_service("cache")

        # Créer le vérificateur de santé
        self.health = HealthChecker()

        # Enregistrer les vérifications
        @self.health.register("database")
        async def check_database():
            try:
                with self.db.session() as session:
                    session.execute("SELECT 1")
                return True, "Database connection OK"
            except Exception as e:
                return False, str(e)

        @self.health.register("cache")
        def check_cache():
            try:
                self.cache.set("health_check", "ok", ttl=1)
                return True, "Cache connection OK"
            except Exception as e:
                return False, str(e)

        @self.health.register("external_api")
        async def check_external_api():
            import httpx
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        "https://api.example.com/health",
                        timeout=5.0
                    )
                return response.status_code == 200, f"Status: {response.status_code}"
            except Exception as e:
                return False, str(e)

    def get_router(self):
        from fastapi import APIRouter

        router = APIRouter()

        @router.get("/health")
        async def health_check():
            """Endpoint de health check."""
            report = await self.health.run_all(timeout=5.0)

            status_code = 200
            if report["status"] == "unhealthy":
                status_code = 503
            elif report["status"] == "degraded":
                status_code = 200  # ou 429 selon vos besoins

            return JSONResponse(
                content=report,
                status_code=status_code
            )

        return router
```

### Structure du rapport

```json
{
  "status": "healthy",
  "checks": {
    "database": {
      "status": "healthy",
      "message": "Database connection OK",
      "duration_ms": 12.34
    },
    "cache": {
      "status": "healthy",
      "message": "Cache connection OK",
      "duration_ms": 2.15
    },
    "external_api": {
      "status": "degraded",
      "message": "Timeout after 5s",
      "duration_ms": 5001.42
    }
  }
}
```

## Logging

XCore fournit une configuration de logging centralisée.

### Configuration

```yaml
# integration.yaml
logging:
  level: INFO                    # DEBUG, INFO, WARNING, ERROR, CRITICAL
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: "logs/xcore.log"          # Optionnel: fichier de log
  max_bytes: 10485760             # 10 MB rotation
  backup_count: 5                 # Nombre de fichiers de backup
```

### Utilisation dans les plugins

```python
from xcore.kernel.observability.logging import get_logger
from xcore.sdk import TrustedBase

# Créer un logger pour votre plugin
logger = get_logger("my_plugin")


class Plugin(TrustedBase):

    async def on_load(self) -> None:
        logger.info("Plugin my_plugin loaded successfully")

        try:
            self.db = self.get_service("db")
            logger.debug("Database service connected")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    async def handle(self, action: str, payload: dict) -> dict:
        logger.debug(f"Handling action: {action}", extra={"payload": payload})

        try:
            result = await self._process_action(action, payload)
            logger.info(f"Action {action} completed successfully")
            return ok(result=result)
        except ValueError as e:
            logger.warning(f"Validation error in action {action}: {e}")
            return error(str(e), code="validation_error")
        except Exception as e:
            logger.exception(f"Unexpected error in action {action}")
            return error("Internal error", code="internal_error")
```

### Bonnes pratiques de logging

```python
# ❌ Mauvais
logger.info("User " + user_id + " logged in")
logger.info(f"Request took {end - start} seconds")

# ✅ Bon
logger.info("User logged in", extra={"user_id": user_id})
logger.info("Request completed", extra={"duration_ms": (end - start) * 1000})

# ❌ Mauvais
try:
    risky_operation()
except Exception as e:
    logger.error(f"Error: {e}")  # Stack trace perdue

# ✅ Bon
try:
    risky_operation()
except Exception:
    logger.exception("Operation failed")  # Capture la stack trace
```

## Tracing

Le système de tracing permet de suivre les requêtes à travers les différents composants.

### Utilisation basique

```python
from xcore.kernel.observability.tracing import Tracer
from xcore.sdk import TrustedBase


class Plugin(TrustedBase):

    async def on_load(self) -> None:
        self.tracer = Tracer(service_name="my_plugin")

    async def handle(self, action: str, payload: dict) -> dict:
        with self.tracer.span("handle_action", action=action) as span:
            span.set_attribute("payload_size", len(str(payload)))

            # Sous-opération 1
            with self.tracer.span("validate_input") as val_span:
                validated = await self._validate(payload)
                val_span.set_attribute("validation_time_ms", validated.duration)

            # Sous-opération 2
            with self.tracer.span("process_request") as proc_span:
                try:
                    result = await self._process(validated)
                    proc_span.set_attribute("result_size", len(str(result)))
                except Exception as e:
                    proc_span.set_status("error")
                    proc_span.set_attribute("error.message", str(e))
                    raise

            return ok(result=result)
```

### Export des traces

```python
def get_router(self):
    from fastapi import APIRouter

    router = APIRouter()

    @router.get("/traces")
    async def get_traces():
        """Exporter les traces collectées."""
        return {"spans": self.tracer.export()}

    return router
```

### Exemple de trace

```json
{
  "spans": [
    {
      "name": "handle_action",
      "trace_id": "a1b2c3d4e5f6...",
      "span_id": "1234567890abcd",
      "duration_ms": 45.2,
      "status": "ok",
      "attributes": {
        "action": "create_user",
        "payload_size": 256
      }
    },
    {
      "name": "validate_input",
      "trace_id": "a1b2c3d4e5f6...",
      "span_id": "fedcba098765...",
      "duration_ms": 2.1,
      "status": "ok",
      "attributes": {
        "validation_time_ms": 1.8
      }
    }
  ]
}
```

## Exemple complet

```python
from xcore.kernel.observability.health import HealthChecker
from xcore.kernel.observability.logging import get_logger
from xcore.kernel.observability.metrics import MetricsRegistry
from xcore.kernel.observability.tracing import Tracer
from xcore.sdk import TrustedBase, ok, error


logger = get_logger("api_plugin")


class Plugin(TrustedBase):

    async def on_load(self) -> None:
        # Initialisation des services
        self.db = self.get_service("db")
        self.cache = self.get_service("cache")

        # Initialisation de l'observabilité
        self.metrics = MetricsRegistry()
        self.health = HealthChecker()
        self.tracer = Tracer(service_name="api_plugin")

        # Métriques
        self.request_count = self.metrics.counter(
            "api.requests.total",
            labels={"plugin": "api_plugin"}
        )
        self.request_latency = self.metrics.histogram("api.request.duration")

        # Health checks
        @self.health.register("database")
        async def check_db():
            try:
                with self.db.session() as session:
                    session.execute("SELECT 1")
                return True, "Database OK"
            except Exception as e:
                return False, str(e)

        @self.health.register("cache")
        def check_cache():
            try:
                self.cache.set("health_check", "ok", ttl=1)
                return True, "Cache OK"
            except Exception as e:
                return False, str(e)

        logger.info("API plugin initialized")

    def get_router(self):
        from fastapi import APIRouter, Request, HTTPException
        import time

        router = APIRouter()

        @router.get("/users/{user_id}")
        async def get_user(user_id: str, request: Request):
            """Récupérer un utilisateur avec monitoring complet."""
            start_time = time.monotonic()

            with self.tracer.span("get_user", user_id=user_id) as span:
                try:
                    # Métriques
                    self.request_count.inc()

                    # Cache lookup
                    with self.tracer.span("cache_lookup"):
                        cached = await self.cache.get(f"user:{user_id}")
                        if cached:
                            span.set_attribute("cache_hit", True)
                            return {"user": cached, "cached": True}

                        span.set_attribute("cache_hit", False)

                    # Database lookup
                    with self.tracer.span("db_query") as db_span:
                        with self.db.session() as session:
                            result = session.execute(
                                "SELECT * FROM users WHERE id = :id",
                                {"id": user_id}
                            )
                            user = result.fetchone()

                            if not user:
                                raise HTTPException(404, "User not found")

                            db_span.set_attribute("rows_returned", 1)

                    # Cache le résultat
                    await self.cache.set(f"user:{user_id}", dict(user), ttl=300)

                    # Latence
                    latency = time.monotonic() - start_time
                    self.request_latency.observe(latency)

                    return {"user": dict(user), "cached": False}

                except HTTPException:
                    raise
                except Exception as e:
                    logger.exception(f"Error fetching user {user_id}")
                    span.set_status("error")
                    span.set_attribute("error.message", str(e))
                    raise HTTPException(500, "Internal error")

        @router.get("/health")
        async def health():
            """Health check endpoint."""
            return await self.health.run_all()

        @router.get("/metrics")
        async def metrics():
            """Métriques endpoint."""
            return self.metrics.snapshot()

        return router
```

## Dashboard de monitoring

Voici un exemple simple de dashboard HTML pour visualiser les métriques :

```python
@router.get("/dashboard")
async def dashboard():
    """Simple dashboard de monitoring."""
    health = await self.health.run_all()
    metrics = self.metrics.snapshot()

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Monitoring Dashboard</title>
        <style>
            body {{ font-family: system-ui, sans-serif; padding: 20px; }}
            .card {{ border: 1px solid #ddd; border-radius: 8px; padding: 20px; margin: 10px 0; }}
            .healthy {{ border-left: 4px solid #22c55e; }}
            .degraded {{ border-left: 4px solid #f59e0b; }}
            .unhealthy {{ border-left: 4px solid #ef4444; }}
            pre {{ background: #f5f5f5; padding: 10px; border-radius: 4px; overflow-x: auto; }}
        </style>
    </head>
    <body>
        <h1>Monitoring Dashboard</h1>

        <div class="card {health['status']}">
            <h2>Health Status: {health['status'].upper()}</h2>
            <pre>{json.dumps(health, indent=2)}</pre>
        </div>

        <div class="card">
            <h2>Métriques</h2>
            <pre>{json.dumps(metrics, indent=2)}</pre>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)
```

## Alerting

Exemple d'implémentation d'alertes basiques :

```python
import asyncio
from datetime import datetime


class MonitoringAlerts:

    def __init__(self, metrics: MetricsRegistry, health: HealthChecker):
        self.metrics = metrics
        self.health = health
        self.alerts = []

    async def check_thresholds(self):
        """Vérifier les seuils d'alerte."""
        snapshot = self.metrics.snapshot()

        # Alerte: erreurs HTTP élevées
        error_count = snapshot["counters"].get("http.errors.total:{}", 0)
        if error_count > 100:
            await self.send_alert(
                "high_error_rate",
                f"Error count is high: {error_count}"
            )

        # Alerte: latence élevée
        latency = snapshot["histograms"].get("http.request.duration", {})
        if latency.get("mean", 0) > 1.0:  # > 1 seconde
            await self.send_alert(
                "high_latency",
                f"Mean latency is {latency['mean']:.3f}s"
            )

    async def send_alert(self, alert_type: str, message: str):
        """Envoyer une alerte."""
        alert = {
            "type": alert_type,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.alerts.append(alert)

        # Envoyer vers Slack, PagerDuty, etc.
        logger.error(f"ALERT [{alert_type}]: {message}")

    async def run_checks(self, interval: int = 60):
        """Exécuter les vérifications périodiquement."""
        while True:
            await self.check_thresholds()
            await asyncio.sleep(interval)
```

## Intégration avec Prometheus

Pour exporter vers Prometheus, créez un endpoint compatible :

```python
@router.get("/prometheus")
async def prometheus_metrics():
    """Exporter les métriques au format Prometheus."""
    snapshot = self.metrics.snapshot()

    output = []

    # Counters
    for key, value in snapshot["counters"].items():
        name, labels = key.split(":", 1)
        labels_dict = eval(labels) if labels != "{}" else {}
        label_str = ",".join(f'{k}="{v}"' for k, v in labels_dict.items())
        output.append(f"# HELP {name} Counter metric")
        output.append(f"# TYPE {name} counter")
        output.append(f"{name}{{{label_str}}} {value}")

    # Gauges
    for key, value in snapshot["gauges"].items():
        name, labels = key.split(":", 1)
        labels_dict = eval(labels) if labels != "{}" else {}
        label_str = ",".join(f'{k}="{v}"' for k, v in labels_dict.items())
        output.append(f"# HELP {name} Gauge metric")
        output.append(f"# TYPE {name} gauge")
        output.append(f"{name}{{{label_str}}} {value}")

    return Response(content="\n".join(output), media_type="text/plain")
```

## Bonnes pratiques

1. **Métriques**
   - Utilisez des noms descriptifs avec préfixe (ex: `http_requests_total`)
   - Ajoutez des labels pour permettre l'agrégation
   - Évitez les cardinalités trop élevées (millions de valeurs uniques)

2. **Health Checks**
   - Gardez les checks rapides (< 5 secondes)
   - Vérifiez les dépendances critiques uniquement
   - Retournez des codes HTTP appropriés

3. **Logging**
   - Utilisez le bon niveau de log (DEBUG pour le dev, INFO/ERROR pour la prod)
   - Structurez vos logs avec des champs extra
   - Évitez de logger des données sensibles

4. **Tracing**
   - Créez des spans pour les opérations lentes (> 10ms)
   - Ajoutez des attributs pertinents pour le debugging
   - Propaguez les trace_id entre les services

## Monitoring avec EventBus

Le EventBus permet de monitorer les événements système en temps réel.

### S'abonner aux événements système

```python
from xcore.sdk import TrustedBase


class MonitoringPlugin(TrustedBase):
    """Plugin de monitoring via EventBus."""

    async def on_load(self) -> None:
        self.events = self.ctx.events
        self.metrics = MetricsRegistry()

        # Créer les métriques
        self.event_counter = self.metrics.counter("events.total")
        self.event_latency = self.metrics.histogram("event.processing.duration")

        # S'abonner aux événements système
        self.events.on("plugin.*.loaded", self._on_plugin_loaded)
        self.events.on("plugin.*.error", self._on_plugin_error)
        self.events.on("service.*.error", self._on_service_error)

        # Monitoring des performances
        self.events.on("request.start", self._on_request_start, priority=100)
        self.events.on("request.end", self._on_request_end, priority=10)

        self._request_timings = {}

    async def _on_plugin_loaded(self, event):
        """Logger le chargement des plugins."""
        logger.info(
            f"Plugin {event.name} loaded",
            extra={"source": event.source, "data": event.data}
        )
        self.event_counter.inc()

    async def _on_plugin_error(self, event):
        """Logger les erreurs de plugin."""
        logger.error(
            f"Plugin error: {event.data.get('error')}",
            extra={
                "plugin": event.data.get("plugin"),
                "action": event.data.get("action"),
                "error": event.data.get("error")
            }
        )

        # Émettre une alerte
        await self.events.emit("alert.critical", {
            "type": "plugin_error",
            "message": event.data.get("error"),
            "timestamp": time.time()
        })

    async def _on_service_error(self, event):
        """Logger les erreurs de service."""
        logger.error(
            f"Service {event.data.get('service')} error",
            extra={"error": event.data.get("error")}
        )

    async def _on_request_start(self, event):
        """Démarrer le timing d'une requête."""
        request_id = event.data.get("request_id")
        self._request_timings[request_id] = time.monotonic()

    async def _on_request_end(self, event):
        """Terminer le timing et enregistrer les métriques."""
        request_id = event.data.get("request_id")
        start_time = self._request_timings.pop(request_id, None)

        if start_time:
            duration = time.monotonic() - start_time
            self.event_latency.observe(duration)

            # Alerte si latence trop élevée
            if duration > 1.0:  # > 1 seconde
                await self.events.emit("alert.warning", {
                    "type": "high_latency",
                    "duration": duration,
                    "request_id": request_id
                })

    async def on_unload(self) -> None:
        """Nettoyer les souscriptions."""
        self.events.unsubscribe("plugin.*.loaded", self._on_plugin_loaded)
        self.events.unsubscribe("plugin.*.error", self._on_plugin_error)
        self.events.unsubscribe("service.*.error", self._on_service_error)
```

### Émettre des événements de monitoring

```python
class MonitoredPlugin(TrustedBase):
    """Plugin qui émet des événements de monitoring."""

    def get_router(self):
        from fastapi import APIRouter, Request
        import uuid

        router = APIRouter()

        @router.get("/items/{item_id}")
        async def get_item(item_id: str, request: Request):
            request_id = str(uuid.uuid4())

            # Émettre début de requête
            await self.ctx.events.emit("request.start", {
                "request_id": request_id,
                "method": "GET",
                "path": f"/items/{item_id}",
                "client_ip": request.client.host
            })

            try:
                item = await self._fetch_item(item_id)

                # Émettre fin de requête
                await self.ctx.events.emit("request.end", {
                    "request_id": request_id,
                    "status": "success",
                    "item_found": item is not None
                })

                return {"item": item}

            except Exception as e:
                # Émettre erreur
                await self.ctx.events.emit("request.end", {
                    "request_id": request_id,
                    "status": "error",
                    "error": str(e)
                })
                raise

        return router
```

## Monitoring avec HookManager

Le HookManager permet de créer des points de monitoring dans le flux d'exécution.

### Hooks de monitoring

```python
from xcore.kernel.events.hooks import HookManager
from xcore.sdk import TrustedBase


class HookMonitoringPlugin(TrustedBase):
    """Plugin de monitoring via HookManager."""

    async def on_load(self) -> None:
        self.hooks = HookManager()
        self.metrics = MetricsRegistry()

        # Enregistrer des hooks de monitoring
        @self.hooks.on("api.request", priority=100)
        async def track_request(event):
            """Suivre les requêtes API."""
            self.metrics.counter("api.requests", labels={
                "method": event.data.get("method"),
                "endpoint": event.data.get("endpoint")
            }).inc()

        @self.hooks.on("db.query", priority=50)
        async def track_db_query(event):
            """Suivre les requêtes DB."""
            start = time.monotonic()

            # Le hook s'exécute avant la requête
            # On peut ajouter un callback pour après
            event.data["_start_time"] = start

            # Retourner un callback qui sera exécuté après
            return {"start_time": start}

        @self.hooks.on("db.query.complete", priority=50)
        async def track_db_complete(event):
            """Suivre la complétion des requêtes DB."""
            start_time = event.data.get("start_time")
            if start_time:
                duration = time.monotonic() - start_time
                self.metrics.histogram("db.query.duration").observe(duration)

        @self.hooks.on("cache.miss", priority=10)
        async def track_cache_miss(event):
            """Suivre les cache misses."""
            self.metrics.counter("cache.miss", labels={
                "key": event.data.get("key")
            }).inc()

    async def emit_monitored_event(self, event_name: str, data: dict):
        """Émettre un événement avec monitoring."""
        results = await self.hooks.emit(event_name, data)

        # Analyser les résultats des hooks
        for result in results:
            if result.error:
                logger.error(f"Hook {result.hook_name} failed: {result.error}")

        return results
```

### Intercepteurs de monitoring

```python
class InterceptorMonitoringPlugin(TrustedBase):
    """Monitoring avec intercepteurs."""

    async def on_load(self) -> None:
        self.hooks = HookManager()
        self.metrics = MetricsRegistry()

        # Intercepteur pré-exécution
        async def pre_interceptor(event):
            """Exécuté avant les hooks."""
            event.data["_monitor_start"] = time.monotonic()
            return InterceptorResult.CONTINUE

        # Intercepteur post-exécution
        async def post_interceptor(event, results):
            """Exécuté après les hooks."""
            start = event.data.get("_monitor_start")
            if start:
                duration = time.monotonic() - start

                # Enregistrer les métriques
                self.metrics.histogram("hook.execution.duration").observe(duration)

                # Alerte si trop lent
                if duration > 0.1:  # > 100ms
                    logger.warning(
                        f"Slow hook execution: {duration:.3f}s",
                        extra={"event": event.name}
                    )

        # Enregistrer les intercepteurs
        self.hooks.register_pre_interceptor("api.*", pre_interceptor)
        self.hooks.register_post_interceptor("api.*", post_interceptor)
```

### Pattern: Wildcards pour monitoring global

```python
class GlobalMonitoringPlugin(TrustedBase):
    """Monitoring global avec wildcards."""

    async def on_load(self) -> None:
        self.hooks = HookManager()

        # Intercepter tous les événements
        @self.hooks.on("*", priority=1)  # Basse priorité = s'exécute en dernier
        async def global_monitor(event):
            """Monitorer tous les événements."""
            logger.debug(
                f"Event: {event.name}",
                extra={
                    "event_name": event.name,
                    "data_keys": list(event.data.keys()),
                    "cancelled": event.cancelled
                }
            )

        # Monitorer les erreurs uniquement
        @self.hooks.on("*.error", priority=100)
        async def error_monitor(event):
            """Monitorer toutes les erreurs."""
            logger.error(
                f"Error event: {event.name}",
                extra={
                    "error": event.data.get("error"),
                    "stack": event.data.get("stack_trace")
                }
            )

            # Envoyer alerte si erreur critique
            if event.data.get("critical"):
                await self._send_alert(event)
```

## Intégration EventBus + HookManager

Utilisez les deux systèmes ensemble pour un monitoring complet :

```python
class CompleteMonitoringPlugin(TrustedBase):
    """Plugin de monitoring complet."""

    async def on_load(self) -> None:
        self.events = self.ctx.events
        self.hooks = HookManager()
        self.metrics = MetricsRegistry()

        # EventBus pour la communication inter-plugin
        self.events.on("monitoring.metrics.request", self._on_metrics_request)
        self.events.on("monitoring.health.request", self._on_health_request)

        # HookManager pour le monitoring interne
        @self.hooks.on("plugin.action")
        async def monitor_plugin_action(event):
            start = time.monotonic()

            # Publier via EventBus
            await self.events.emit("action.started", {
                "plugin": event.data.get("plugin"),
                "action": event.data.get("action")
            })

            # Attendre la fin (via callback ou autre mécanisme)
            return {"start_time": start}

    async def _on_metrics_request(self, event):
        """Répondre aux demandes de métriques."""
        await self.events.emit("monitoring.metrics.response", {
            "request_id": event.data.get("request_id"),
            "metrics": self.metrics.snapshot()
        })

    async def _on_health_request(self, event):
        """Répondre aux demandes de health check."""
        await self.events.emit("monitoring.health.response", {
            "request_id": event.data.get("request_id"),
            "status": await self._check_health()
        })
```

## Dashboard de monitoring en temps réel

```python
class MonitoringDashboardPlugin(TrustedBase):
    """Dashboard avec SSE pour temps réel."""

    async def on_load(self) -> None:
        self.events = self.ctx.events
        self.subscribers = []

        # S'abonner aux événements système
        self.events.on("*", self._broadcast_event)

    async def _broadcast_event(self, event):
        """Diffuser les événements aux subscribers."""
        message = json.dumps({
            "event": event.name,
            "data": event.data,
            "timestamp": time.time()
        })

        for queue in self.subscribers:
            await queue.put(message)

    def get_router(self):
        from fastapi import APIRouter
        from fastapi.responses import StreamingResponse
        import asyncio

        router = APIRouter()

        @router.get("/events/stream")
        async def event_stream():
            """Stream d'événements SSE."""
            queue = asyncio.Queue()
            self.subscribers.append(queue)

            async def generate():
                try:
                    while True:
                        message = await queue.get()
                        yield f"data: {message}\n\n"
                finally:
                    self.subscribers.remove(queue)

            return StreamingResponse(
                generate(),
                media_type="text/event-stream"
            )

        return router
```

## Next Steps

- [Services](./services.md) — Utiliser les services de cache et base de données
- [Security](./security.md) — Sécuriser vos endpoints de monitoring
- [Events](./events.md) — Système d'événements complet
- [Deployment](../deployment/guide.md) — Déployer avec monitoring en production
