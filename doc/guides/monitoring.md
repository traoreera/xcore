# Surveillance et Observabilité XCore

XCore intègre des outils de surveillance pour vous aider à comprendre les performances de vos plugins et à diagnostiquer les problèmes en temps réel.

---

## 1. Journaux de Bord (Logs)

Les logs sont structurés pour faciliter le débogage. Chaque plugin possède son propre logger, préfixé par son nom.

### Niveaux de logs configurables

Modifiez le niveau de détail dans `xcore.yaml` :

```yaml
observability:
  logging:
    level: "DEBUG" # INFO, WARNING, ERROR, DEBUG
    format: "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    file: "logs/xcore.log" # Sortie vers un fichier (optionnel)
```

### Utiliser le logger dans un plugin

```python
class MonPlugin(TrustedBase):
    async def on_load(self):
        self.logger.info("Démarrage du plugin...")
        self.logger.debug("Données de configuration : %s", self.ctx.config)
```

---

## 2. Métriques (Metrics)

Le `MetricsRegistry` collecte des compteurs, des jauges et des histogrammes pour le framework et ses plugins.

### Consulter les métriques

```bash
# Via la CLI
xcore health

# Via l'API HTTP (Snapshot JSON)
curl http://localhost:8082/plugin/ipc/metrics
```

### Ajouter des métriques personnalisées

```python
class MonPlugin(TrustedBase):
    async def on_load(self):
        # Création d'un compteur personnalisé
        self.metrics.counter("processed_items_total", description="Nombre total d'items traités")

    async def process(self, item):
        # Incrémenter le compteur
        self.metrics.inc("processed_items_total", labels={"type": item.type})
```

---

## 3. Traces Distribuées (Tracing)

XCore supporte le tracing via **OpenTelemetry** pour suivre le cheminement d'une requête à travers plusieurs plugins.

### Configuration du Tracing

```yaml
observability:
  tracing:
    enabled: true
    backend: "jaeger" # noop, opentelemetry, jaeger
    endpoint: "http://localhost:14268/api/traces"
    service_name: "xcore-production"
```

### Utiliser le Tracer dans un plugin

```python
class MonPlugin(TrustedBase):
    async def handle(self, action, payload):
        with self.tracer.start_span(f"action_{action}") as span:
            span.set_attribute("payload_size", len(payload))
            # ... logique métier ...
            return ok()
```

---

## 4. Bilan de Santé (Health Check)

Le `HealthChecker` centralise l'état de santé de tous les composants :
- **Framework** (Boot, Registry).
- **Services** (DB, Cache, Scheduler).
- **Plugins** (Statut, Sandboxes).

### Consulter l'état global

```bash
# Rapport détaillé (CLI)
xcore health

# Rapport global (JSON)
xcore health --json
```

### Ajouter un Health Check personnalisé dans un plugin

```python
class MonPlugin(TrustedBase):
    async def on_init(self):
        # Enregistrer un check périodique
        self.ctx.health.register_check("api_connection", self.check_api)

    async def check_api(self):
        # Retourne (bool, message)
        is_up = await ping_api()
        return is_up, "API accessible" if is_up else "API hors ligne"
```

---

## 5. Middleware de Surveillance (Performance)

Le `MiddlewarePipeline` mesure automatiquement le temps d'exécution de chaque appel IPC vers un plugin. Si un appel dépasse un certain seuil, un warning est émis dans les logs.

- **Métriques automatiques** : `plugin_call_duration_seconds`, `plugin_call_total`.
- **Labels** : `plugin_name`, `action`, `status` (ok/error).

---

## Résumé

| Outil | Usage Principal | Configuration |
|-------|-----------------|---------------|
| **Logs** | Débogage détaillé | `logging` |
| **Metrics** | Tableaux de bord (Prometheus) | `metrics` |
| **Tracing** | Analyse de latence (Jaeger) | `tracing` |
| **Health** | Monitoring de disponibilité | Intégré |
