# Concepts du Scheduler

xcore intègre un système de tâches planifiées (`BackgroundTask`) qui permet aux plugins d'exécuter du code de manière périodique ou différée, sans bloquer l'API.

---

## Qu'est-ce que le Scheduler ?

Le scheduler est un **orchestrateur de tâches d'arrière-plan** géré par le `Manager`. Il s'appuie sur les `BackgroundTasks` de FastAPI et peut être étendu avec des tâches récurrentes (cron-like).

Il est accessible via l'endpoint `/manager` pour le monitoring et la gestion des tâches.

---

## Types de tâches

### Tâches ponctuelles (one-shot)

Déclenchées une seule fois, généralement en réponse à un événement (requête HTTP, webhook, etc.). FastAPI les exécute en arrière-plan sans bloquer la réponse.

```python
from fastapi import BackgroundTasks

@router.post("/envoyer")
async def envoyer(background_tasks: BackgroundTasks):
    background_tasks.add_task(ma_fonction, argument1, argument2)
    return {"status": "en cours"}
```

### Tâches périodiques (récurrentes)

Exécutées à intervalles réguliers, définies par les plugins au moment de leur chargement. Utiles pour les synchronisations, les nettoyages, les rapports automatiques, etc.

```python
# Exemple de déclaration d'une tâche périodique dans un plugin
PLUGIN_TASKS = [
    {
        "name": "nettoyage_cache",
        "interval_seconds": 3600,  # toutes les heures
        "function": nettoyer_cache,
        "async": True,
    }
]
```

---

## Priorités et dépendances

Les tâches peuvent déclarer une **priorité** (haute, normale, basse) et des **dépendances** entre elles :

- Une tâche de haute priorité s'exécute avant les tâches normales.
- Une tâche peut attendre qu'une autre soit terminée avant de démarrer.

```python
PLUGIN_TASKS = [
    {
        "name": "export_rapport",
        "depends_on": ["calcul_stats"],   # attend la fin de cette tâche
        "priority": "normal",
        "function": exporter_rapport,
    },
    {
        "name": "calcul_stats",
        "priority": "high",
        "function": calculer_statistiques,
    }
]
```

---

## Exécution : sync vs async

Le scheduler supporte les deux modes d'exécution :

| Mode | Quand l'utiliser |
|------|-----------------|
| `async` | Tâches I/O-bound : appels HTTP, requêtes DB, envoi d'emails |
| `sync` (`concured()`) | Tâches CPU-bound : calculs, traitement de fichiers |

Les tâches synchrones sont exécutées dans un thread pool pour ne pas bloquer la boucle asyncio.

---

## Monitoring des tâches

Le Manager expose des endpoints pour inspecter l'état des tâches :

| Endpoint | Description |
|----------|-------------|
| `GET /manager/tasks` | Liste toutes les tâches enregistrées |
| `GET /manager/tasks/{name}` | Détail et historique d'une tâche |
| `POST /manager/tasks/{name}/run` | Déclenche manuellement une tâche |
| `DELETE /manager/tasks/{name}` | Annule une tâche planifiée |

---

## Alerting

Si une tâche échoue plusieurs fois consécutivement, le système d'alerting du Manager le signale dans les logs et peut déclencher une notification (email, webhook) selon la configuration.

```yaml
# dans config.yaml d'un plugin
tasks:
  - name: "sync_donnees"
    alert_on_failure: true
    max_retries: 3
    retry_delay_seconds: 60
```

---

## Bonnes pratiques

- Préférez les tâches `async` pour tout ce qui touche au réseau ou à la base de données.
- Donnez des noms explicites à vos tâches (visibles dans le monitoring).
- Gérez toujours les exceptions dans vos fonctions de tâche — une exception non catchée arrête la tâche définitivement.
- Évitez les tâches avec des intervalles très courts (< 5 secondes) qui pourraient saturer les ressources.
