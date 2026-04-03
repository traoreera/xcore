# Monitoring et Observabilité

XCore fournit un système d'observabilité complet pour surveiller vos plugins et services en production.

## Les Quatre Piliers

L'observabilité dans XCore repose sur quatre composants intégrés, accessibles via `self.ctx` :

1.  **Métriques** (`MetricsRegistry`) : Compteurs, jauges et histogrammes pour mesurer les performances.
2.  **Health Checks** (`HealthChecker`) : Diagnostics de santé en temps réel des services et plugins.
3.  **Logging** : Journalisation structurée avec niveaux configurables et rotation.
4.  **Tracing** (`Tracer`) : Suivi des flux d'exécution complexes via des spans distribuées.

---

## Métriques (`self.ctx.metrics`)

Le registre de métriques permet de mesurer les performances de vos plugins en temps réel.

### Types de métriques supportés

-   **Counter** : Valeurs strictement croissantes (ex: nombre total de requêtes).
-   **Gauge** : Valeurs pouvant monter ou descendre (ex: nombre de connexions actives).
-   **Histogram** : Distribution de valeurs (ex: latence des requêtes, taille des payloads).

### Utilisation de base

```python
from xcore.kernel.observability.metrics import MetricsRegistry
from xcore.sdk import TrustedBase

class Plugin(TrustedBase):
    async def on_load(self) -> None:
        # Création des métriques dans le registre local
        self.metrics = MetricsRegistry()

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
                # Logique métier ici...
                self.request_count.inc()
                return {"status": "ok"}
            finally:
                # Enregistrement de la latence
                self.request_latency.observe(time.monotonic() - start)
                self.active_connections.dec()
        return router
```

### Métriques avec Labels

Les labels permettent d'ajouter des dimensions à vos métriques pour une analyse plus fine (ex: par endpoint, par méthode HTTP).

```python
self.request_count = self.metrics.counter(
    "http.requests.total",
    labels={"plugin": "mon_plugin", "method": "GET"}
)
```

---

## Health Checks (`self.ctx.health`)

Le système de health checks permet de monitorer l'état de vos dépendances et de vos composants internes.

### Enregistrer un diagnostic

```python
from xcore.kernel.observability.health import HealthChecker

class Plugin(TrustedBase):
    async def on_load(self) -> None:
        self.health = HealthChecker()
        self.db = self.get_service("db")

        @self.health.register("database")
        async def check_db():
            try:
                # Tentative d'exécution d'une requête simple
                async with self.db.session() as session:
                    await session.execute("SELECT 1")
                return True, "Base de données OK"
            except Exception as e:
                return False, str(e)
```

Les résultats sont agrégés par le framework et exposés via la CLI `xcore health` ou l'endpoint système `/health`.

---

## Journalisation (Logging)

XCore utilise des loggers nommés et configurés globalement. Il est recommandé d'utiliser `get_logger` pour bénéficier du formatage structuré (JSON en production).

### Configuration (`xcore.yaml`)

```yaml
observability:
  logging:
    level: INFO
    format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: "logs/app.log"
```

### Utilisation dans les plugins

```python
from xcore.kernel.observability import get_logger
logger = get_logger("mon_plugin")

class Plugin(TrustedBase):
    async def on_load(self):
        logger.info("Plugin chargé avec succès", extra={"version": "1.0.0"})
```

---

## Tracing (`self.ctx.tracer`)

Le tracing permet de suivre le cheminement d'une requête à travers les différents middlewares et plugins.

```python
from xcore.kernel.observability.tracing import Tracer

class Plugin(TrustedBase):
    async def on_load(self):
        self.tracer = Tracer(service_name="mon_plugin")

    async def handle(self, action, payload):
        with self.tracer.span("traitement_action", action=action) as span:
            # Instrumentation de la logique métier
            span.set_attribute("user_id", payload.get("user_id"))

            # ... exécution ...

            span.set_attribute("resultat", "succès")
            return ok()
```

---

## Bonnes Pratiques

1.  **Noms explicites** : Utilisez des noms clairs séparés par des points (ex: `api.user.login_success`).
2.  **Cardinalité contrôlée** : N'utilisez jamais d'IDs uniques (comme des IDs utilisateurs) comme labels dans les métriques.
3.  **Niveaux de log appropriés** : `DEBUG` pour les informations verbeuses, `INFO` pour le flux général, et `ERROR` pour les échecs réels.
4.  **Monitorer les dépendances** : Incluez toujours des health checks pour les API externes ou les bases de données dont votre plugin dépend.
