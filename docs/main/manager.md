# manager.py

Le fichier `manager.py` contient la classe `Manager`, l'orchestrateur principal du système de plugins de xcore.

## Rôle

La classe `Manager` agit comme une couche d'abstraction de haut niveau au-dessus du `PluginManager`. Son rôle est de :
1. Centraliser l'injection des services (Integration Framework).
2. Gérer le cycle de vie des plugins (chargement, arrêt, rechargement).
3. Attacher les routes d'API des plugins à l'application FastAPI.
4. Surveiller les changements sur le disque (watcher) pour le rechargement à chaud (hot reload).

## Structure de la classe `Manager`

```python
class Manager:
    def __init__(
        self,
        app,
        base_routes,
        plugins_dir: str = "plugins",
        secret_key: bytes = b"...",
        services: dict = None,
        interval: int = 2,
        strict_trusted: bool = True,
    ):
        ...
```

### Paramètres principaux

- `app`: L'application FastAPI.
- `plugins_dir`: Le répertoire où sont stockés les plugins (défaut: `plugins/`).
- `services`: Un dictionnaire contenant les instances de services injectées (DB, Redis, etc.).
- `strict_trusted`: Si `True`, les plugins ne sont autorisés à s'exécuter qu'en mode `trusted` (signature requise).
- `interval`: Intervalle de vérification pour le rechargement à chaud (watcher).

## Méthodes Clés

- `update_services(services: dict)`: Injecte les services (provenant de l'intégration) dans le `PluginManager`.
- `async start()`: Charge tous les plugins du répertoire `plugins/` et attache le routeur FastAPI.
- `async call(plugin_name, action, payload)`: Appelle directement un plugin par son nom et une action spécifique.
- `start_watching()`: Lance une boucle de surveillance sur le répertoire des plugins pour détecter les changements.
- `async stop()`: Arrête proprement tous les plugins et leurs processus (si sandboxed).
- `status()`: Retourne un dictionnaire avec l'état actuel de tous les plugins chargés.

## Exemples d'utilisation

### Démarrage dans le cycle de vie FastAPI

```python
from fastapi import FastAPI
from xcore.manager import Manager

app = FastAPI()

@app.on_event("startup")
async def startup():
    manager = Manager(app, base_routes=app.routes)
    # Injectez vos services ici si nécessaire
    # manager.update_services({"db": db_instance})
    await manager.start()
    app.state.manager = manager
```

### Appel d'un plugin

```python
# Depuis une route FastAPI
@app.post("/call/{plugin}")
async def call_plugin(plugin: str, action: str, data: dict):
    manager: Manager = app.state.manager
    return await manager.call(plugin, action, data)
```

## Détails Techniques

- Le `Manager` délègue la gestion bas niveau (sandbox, trusted runner) à la classe `PluginManager` située dans `xcore.sandbox.manager`.
- La route `/plugin/{plugin_name}/{action}` est automatiquement enregistrée lors de l'appel à `start()`.
- Le système de `Snapshot` est utilisé par le watcher pour comparer l'état du disque (fichiers modifiés, ajoutés, supprimés).

## Contribution

- Pour toute nouvelle méthode de gestion du cycle de vie, assurez-vous qu'elle est idempotente et thread-safe (ou compatible `asyncio`).
- Si une nouvelle capacité est ajoutée au `PluginManager`, elle doit être exposée dans `Manager` pour faciliter son utilisation par les développeurs de l'application.
