# Utilisation des Services

Le framework XCore repose sur un `ServiceContainer` qui centralise l'accès aux ressources partagées (Bases de données, Cache, Scheduler, Extensions).

## Architecture du ServiceContainer

Les services sont initialisés de manière modulaire via des `BaseServiceProvider`. L'ordre d'initialisation est strict pour garantir la résolution des dépendances internes :

1. **Databases** (SQL/NoSQL)
2. **Cache** (Redis/Memory)
3. **Scheduler** (Planification de tâches)
4. **Extensions** (Services personnalisés tiers)

## Accès aux Services dans un Plugin

### Injection de dépendance via le SDK

La méthode recommandée est d'utiliser `self.get_service(name)` dans la méthode `on_load()`.

```python
class MyPlugin(TrustedBase):
    async def on_load(self) -> None:
        # Récupération des services standards
        self.db = self.get_service("db")
        self.cache = self.get_service("cache")
        self.scheduler = self.get_service("scheduler")

        # Récupération d'une extension spécifique
        self.mailer = self.get_service("ext.mailer")
```

### Protection des méthodes

Vous pouvez utiliser le décorateur `@require_service` pour garantir la présence d'un service avant l'exécution d'une méthode :

```python
from xcore.sdk import require_service

class MyPlugin(TrustedBase):
    @require_service("db", "cache")
    async def process_data(self, data: dict):
        # Cette méthode ne s'exécutera que si db et cache sont disponibles
        pass
```

## Types de Services Disponibles

### 1. Database Service
Supporte SQLAlchemy (Sync/Async) et Redis.
- **Sync** : Utilisez `with self.db.session() as session:`
- **Async** : Utilisez `async with self.db.connection() as conn:`

### 2. Cache Service
Fournit une interface unifiée pour Redis ou un stockage en mémoire.
- `await self.cache.get(key)`
- `await self.cache.set(key, value, ttl=300)`
- `await self.cache.get_or_set(key, factory_func)`

### 3. Scheduler Service
Basé sur APScheduler, il permet de planifier des tâches cron ou à intervalle.
```python
self.scheduler.add_job(
    func=self._my_task,
    trigger="interval",
    minutes=10,
    id="unique_task_id"
)
```

## Scoping des Services (Public vs Private)

Depuis la version 2.0, les services peuvent définir leur visibilité dans le manifest de l'extension :

- **Public** (défaut) : Le service est accessible par tous les plugins via `get_service()`.
- **Private** : Le service n'est accessible que par le plugin qui l'a exporté.

```yaml
# extension/plugin.yaml
resources:
  services:
    my_internal_tool:
      scope: private
```

## Initialisation Modulaire

Si vous développez une extension core, vous devez hériter de `BaseServiceProvider` :

```python
from xcore.services.base import BaseServiceProvider

class MyNewServiceProvider(BaseServiceProvider):
    def init(self):
        # Logique d'initialisation
        self.container.register("my_service", MyServiceInstance())

    def shutdown(self):
        # Nettoyage
        pass
```

## Bonnes Pratiques

1. **Initialisation dans `on_load`** : Ne récupérez pas les services dans le constructeur `__init__`, car le conteneur n'est peut-être pas encore prêt.
2. **Gestion des erreurs** : Toujours prévoir un cas où un service est indisponible (ex: `if not self.db: ...`).
3. **Shutdown propre** : Si votre plugin utilise des ressources spécifiques d'un service (comme des jobs scheduler), nettoyez-les dans `on_unload`.
