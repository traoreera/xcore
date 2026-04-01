# Monitoring et Observabilité

L'observabilité est un pilier central de XCore. Le framework intègre nativement des outils pour surveiller la santé, les performances et le comportement des plugins.

## Les 4 Piliers de l'Observabilité dans XCore

1. **Structured Logging** : Utilisation de `logging` avec contextes enrichis.
2. **Metrics** : Collecte de compteurs, jauges et histogrammes.
3. **Health Checks** : Vérification de la disponibilité des services et plugins.
4. **Tracing** : Suivi des appels à travers le pipeline de middleware.

## Feedback en Temps Réel (CLI UX)

XCore utilise la bibliothèque `rich` pour fournir un feedback visuel riche dans le CLI.

- **Spinners de statut** : Utilisation de `rich.console.Status` pour les opérations longues (ex: démarrage du sandbox, scan AST).
- **Panneaux de configuration** : Affichage des métadonnées dans des `rich.panel.Panel` pour une meilleure lisibilité.
- **Tableaux de santé** : La commande `xcore plugin health` génère un tableau récapitulatif avec les erreurs et avertissements formatés.

```python
# Exemple d'utilisation interne pour le feedback CLI
from rich.console import Console
from rich.status import Status

console = Console()
with console.status("[bold green]Analyse des plugins...") as status:
    # Effectuer le scan AST
    results = scanner.scan_all()
    status.update("[bold blue]Scan terminé, génération du rapport...")
```

## Métriques et Performance

Chaque appel de plugin passe par un pipeline de middleware qui enregistre automatiquement :
- La latence de l'appel.
- Le succès ou l'échec (code de statut).
- La consommation de ressources (en mode sandbox).

### Optimisation du Hot-Path
Pour minimiser l'impact du monitoring sur les performances, les métriques sont collectées de manière asynchrone ou via des compteurs atomiques synchrones très rapides (ex: `RateLimiter` optimisé).

## Health Checks Globaux

Le framework expose un endpoint de santé global et des commandes CLI :

- `xcore health` : Vérifie la connectivité à la DB, au Cache et l'état du Scheduler.
- `xcore services status` : Affiche un tableau détaillé de l'état de chaque service configuré.

## Intégration avec l'EventBus

Vous pouvez créer votre propre plugin de monitoring en écoutant les événements système :

```python
class MonitorPlugin(TrustedBase):
    async def on_load(self) -> None:
        # Écouter tous les refus de permission
        self.ctx.events.on("permission.deny", self.log_security_alert)

        # Écouter les erreurs de service
        self.ctx.events.on("service.error", self.report_to_sentry)
```

## Logs Structurés

Il est recommandé d'utiliser des logs structurés (JSON en production) pour faciliter l'indexation dans des outils comme ELK ou Loki.

```python
import logging
logger = logging.getLogger("xcore.plugin.my_plugin")

logger.info("Traitement action", extra={
    "plugin": "my_plugin",
    "action": "compute",
    "duration_ms": 15.4
})
```

## Export des Données

Toutes les données de monitoring (santé, métriques) peuvent être exportées au format JSON via le flag `--json` des commandes CLI, permettant une intégration facile avec Prometheus, Grafana ou des systèmes d'alerte externes.
