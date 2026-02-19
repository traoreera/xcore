# integration.py (Integration Framework)

Le fichier `integration.py` contient l'orchestrateur central du framework d'intégration de services de xcore.

## Rôle

La classe `Integration` est le point d'entrée unique pour initialiser et accéder à tous les services configurés dans `integration.yaml`. Elle gère :
- Le chargement et la résolution de la configuration.
- L'instanciation et l'initialisation de chaque service (DB, Cache, Scheduler, etc.).
- L'enregistrement automatique de ces services dans le `ServiceRegistry`.
- Le cycle de vie complet des services (`init()`, `shutdown()`).

## Structure de la classe `Integration`

```python
class Integration:
    def __init__(self, config_path: Optional[str | Path] = None):
        ...
    async def init(self):
        ...
    async def shutdown(self):
        ...
```

### Méthodes Clés

- `async init()`: Charge la configuration, initialise tous les services (bases de données, cache, planificateur) et les enregistre dans le registre.
- `async shutdown()`: Ferme proprement toutes les connexions aux services (dispose des pools de connexions SQL, ferme les sockets Redis, arrête le scheduler).
- `get(name: str)`: Raccourci vers `ServiceRegistry.get(name)`.
- `init_sync()`: Wrapper synchrone pour `init()` (pratique pour les scripts simples).

## Exemple d'utilisation dans FastAPI

```python
from fastapi import FastAPI
from xcore.integration.core.integration import Integration

app = FastAPI()
integration = Integration()

@app.on_event("startup")
async def startup():
    await integration.init()
    # On peut maintenant injecter les services dans le manager
    # manager.update_services(integration.registry.all())

@app.on_event("shutdown")
async def shutdown():
    await integration.shutdown()
```

## Détails Techniques

- L'ordre d'initialisation est important :
  1. Configuration
  2. Bases de données
  3. Cache
  4. Scheduler
  5. Extensions (services externes chargés dynamiquement)
- `Integration` utilise des singletons internes pour garantir qu'une seule instance de chaque service existe.

## Contribution

- Pour ajouter un nouveau type de service (ex: `NotificationService`), ajoutez une nouvelle étape d'initialisation dans `init()`.
- N'oubliez pas d'ajouter l'étape de fermeture correspondante dans `shutdown()`.
- Assurez-vous de capturer les exceptions pendant l'initialisation pour éviter que l'application ne s'arrête si un service secondaire échoue.
