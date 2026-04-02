# Référence du SDK XCore

Le SDK XCore fournit tous les outils nécessaires pour créer des plugins puissants, sécurisés et maintenables.

## Vue d'ensemble des imports

```python
from xcore.sdk import (
    TrustedBase,         # Classe de base pour tous les plugins
    ok, error,           # Helpers de réponse standardisée
    action,              # Décorateur pour dispatcher les actions IPC
    route,               # Décorateur pour déclarer des routes HTTP
    RoutedPlugin,        # Mixin pour le montage automatique des routes
    AutoDispatchMixin,   # Mixin pour le dispatch automatique de handle()
    require_service,     # Décorateur de protection par dépendance
    validate_payload,    # Décorateur de validation Pydantic
    trusted, sandboxed,  # Marqueurs de compatibilité de mode
    BaseSyncRepository,  # Repository SQL synchrone
    BaseAsyncRepository, # Repository SQL asynchrone
)
```

## Classe `TrustedBase`

C'est la classe mère de tout plugin XCore. Elle fournit l'accès au contexte et aux services.

### Méthodes du cycle de vie

```python
class Plugin(TrustedBase):
    async def on_load(self) -> None:
        """Appelé au chargement initial du plugin."""
        pass

    async def on_unload(self) -> None:
        """Appelé avant le déchargement du plugin (nettoyage)."""
        pass

    async def on_reload(self) -> None:
        """Appelé lors d'un rechargement à chaud (hot-reload)."""
        pass

    async def handle(self, action: str, payload: dict) -> dict:
        """
        Point d'entrée obligatoire pour les appels IPC.
        Doit retourner un dictionnaire (utilisez ok() ou error()).
        """
        return ok()
```

### Accès au contexte (`self.ctx`)

L'objet `ctx` (PluginContext) contient les métadonnées et les bus système :
- `self.ctx.name` : Nom du plugin.
- `self.ctx.config` : Configuration spécifique au plugin définie dans `xcore.yaml`.
- `self.ctx.env` : Variables d'environnement résolues.
- `self.ctx.events` : Accès au bus d'événements global.
- `self.ctx.hooks` : Accès au gestionnaire de hooks.

## Décorateurs de Fonctionnalité

### `@action(name: str)`
Définit une méthode comme gestionnaire d'une action IPC. À utiliser avec `AutoDispatchMixin`.

- **Paramètre** : `name` est l'identifiant de l'action envoyé par le `PluginSupervisor`.

### `@route(path: str, method: str = "GET", ...)`
Expose une méthode comme endpoint HTTP FastAPI. À utiliser avec `RoutedPlugin`.

- **Paramètres** :
    - `path` : Chemin de la route (ex: `"/items/{id}"`).
    - `method` : Méthode HTTP (`"GET"`, `"POST"`, etc.).
    - `tags` : Liste de tags pour OpenAPI.
    - `status_code` : Code HTTP de succès (défaut: 200).
    - `permissions` : Liste de permissions RBAC requises (ex: `["admin"]`).

### `@validate_payload(schema: Type[BaseModel])`
Valide le payload entrant via un modèle Pydantic avant l'exécution de la méthode. En cas d'échec, une erreur `validation_error` est retournée automatiquement.

### `@require_service(*service_names: str)`
Vérifie la présence d'un ou plusieurs services avant l'appel. Lève une `KeyError` si un service manque, empêchant l'exécution de la logique métier dans un état instable.

### `@trusted` / `@sandboxed`
Marqueurs de compatibilité indiquant si une méthode ne peut s'exécuter qu'en mode `trusted` ou si elle est explicitement compatible avec le mode `sandboxed`.

---

## Repositories SQL

Le SDK simplifie l'accès aux données avec le pattern Repository (`xcore.sdk.adapter`).

### `BaseSyncRepository[T]`
Fournit des méthodes CRUD synchrones standard :
- `get_by_id(id)`
- `get_all()`
- `create(obj)`
- `update(id, data)`
- `delete(id)`
- `get_by_name(name)`

### `BaseAsyncRepository[T]`
Équivalent asynchrone pour une utilisation avec `async with self.db.connection()`.
*Note : Les méthodes asynchrones nécessitent de passer explicitement l'objet `session` en premier argument.*

```python
# Exemple Async
repo = ProductRepository(Product)
product = await repo.get_by_id(session, "123")
```

---

## PluginContext (`self.ctx`)

Chaque plugin `trusted` reçoit un objet `ctx` riche en fonctionnalités :

| Propriété | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Nom du plugin. |
| `services` | `dict` | Dictionnaire brut des services disponibles. |
| `events` | `EventBus` | Accès au bus d'événements. |
| `hooks` | `HookManager` | Accès au gestionnaire de hooks. |
| `env` | `dict` | Variables d'environnement résolues (depuis `plugin.yaml`). |
| `config` | `dict` | Bloc `extra` du manifeste. |
| `metrics` | `MetricsRegistry` | Registre pour les compteurs et jauges. |
| `tracer` | `Tracer` | Système de tracing pour les spans. |
| `health` | `HealthChecker` | Registre de health checks locaux. |

## Helpers de Réponse

Utilisez toujours ces helpers pour garantir la compatibilité avec le framework.

- `ok(**kwargs)` : Retourne `{"status": "ok", ...kwargs}`.
- `error(msg, code=None, status_code=400, **kwargs)` : Retourne `{"status": "error", "msg": msg, "code": code, ...kwargs}`.

## Mixins Utilitaires

- **`AutoDispatchMixin`** : Implémente automatiquement la méthode `handle` en dispatchant vers les méthodes décorées avec `@action`.
- **`RoutedPlugin`** : Implémente automatiquement `get_router` en collectant toutes les méthodes décorées avec `@route`.

### Exemple de Plugin Combiné
```python
class SuperPlugin(RoutedPlugin, AutoDispatchMixin, TrustedBase):
    @action("compute")
    async def ipc_compute(self, payload: dict):
        return ok(result=42)

    @route("/status", method="GET")
    async def http_status(self):
        return {"active": True}
```
