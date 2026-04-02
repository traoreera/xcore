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

### `@action(name)`
Utilisé avec `AutoDispatchMixin` pour lier une méthode à une action IPC.

```python
class MyPlugin(AutoDispatchMixin, TrustedBase):
    @action("ping")
    async def do_ping(self, payload: dict):
        return ok(message="pong")
```

### `@route(path, method="GET", ...)`
Utilisé avec `RoutedPlugin` pour exposer un endpoint HTTP via FastAPI.

```python
class MyPlugin(RoutedPlugin, TrustedBase):
    @route("/hello/{name}", method="GET", tags=["public"])
    async def say_hello(self, name: str):
        return {"message": f"Hello {name}"}
```

### `@validate_payload(Model)`
Valide automatiquement le payload entrant avec un modèle Pydantic.

```python
from pydantic import BaseModel

class LoginData(BaseModel):
    username: str
    password: str

class AuthPlugin(TrustedBase):
    @validate_payload(LoginData)
    async def handle_login(self, data: LoginData):
        # 'data' est ici une instance de LoginData validée
        return ok(logged_in=True)
```

### `@require_service(*service_names)`
Empêche l'exécution de la méthode si les services requis ne sont pas disponibles.

```python
class DataPlugin(TrustedBase):
    @require_service("db", "cache")
    async def process_data(self, payload: dict):
        # On est certain que self.get_service("db") fonctionne
        pass
```

## Repositories SQL

Le SDK inclut des classes de base pour implémenter le pattern Repository avec SQLAlchemy.

### `BaseSyncRepository[T]`
```python
class UserRepository(BaseSyncRepository[User]):
    def get_active_users(self):
        return self.session.query(User).filter(User.active == True).all()

# Usage dans le plugin
with self.db.session() as session:
    repo = UserRepository(User, session)
    users = repo.get_active_users()
```

### `BaseAsyncRepository[T]`
```python
class ProductRepository(BaseAsyncRepository[Product]):
    async def find_by_sku(self, sku: str):
        stmt = select(Product).where(Product.sku == sku)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
```

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
