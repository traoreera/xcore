# SDK Reference

---

## Classes principales

### `TrustedBase`

Classe de base pour les plugins qui s'exécutent dans le processus principal.

```python
from xcore.kernel.api.contract import TrustedBase

class Plugin(TrustedBase):
    async def handle(self, action: str, payload: dict) -> dict: ...
```

**Attributs injectés par le framework :**

| Attribut | Type | Description |
|:---------|:-----|:------------|
| `self.ctx` | `PluginContext` | Contexte complet (services, events, hooks, config) |

**Méthodes :**

| Méthode | Signature | Description |
|:--------|:----------|:------------|
| `get_service` | `(name: str) → Any` | Retourne un service du container (typé) |
| `get_service_as` | `(name: str, type_: Type[T]) → T` | Variante avec type explicite |
| `call_plugin` | `(plugin: str, action: str, payload: dict) → dict` | Appel inter-plugins |
| `get_router` | `() → APIRouter \| None` | Surcharger pour exposer des routes HTTP |

**Clés typées de `get_service` :**

| Clé | Type retourné |
|:----|:--------------|
| `"db"` | `AsyncSQLAdapter` |
| `"cache"` | `CacheService` |
| `"scheduler"` | `SchedulerService` |
| `"syncdb"` | `SQLAdapter` |
| `"mongodb"` | `MongoDBAdapter` |
| `"redisAdapter"` | `RedisAdapter` |

**Hooks de cycle de vie (optionnels) :**

```python
async def on_init(self) -> None: ...    # avant injection du contexte
async def on_load(self) -> None: ...    # après injection — services disponibles
async def on_start(self) -> None: ...   # serveur prêt à recevoir
async def on_reload(self) -> None: ...  # après hot-reload
async def on_stop(self) -> None: ...    # avant arrêt
async def on_unload(self) -> None: ...  # après déchargement
```

---

### `BasePlugin` (Protocol)

Interface minimale duck-typing (pas d'héritage requis) :

```python
class BasePlugin(Protocol):
    async def handle(self, action: str, payload: dict) -> dict: ...
    async def on_init(self) -> None: ...
    async def on_start(self) -> None: ...
    async def on_stop(self) -> None: ...
```

---

### `AutoDispatchMixin`

Génère automatiquement `handle()` en routant vers les méthodes `@action`.

```python
from xcore.sdk.decorators import AutoDispatchMixin, action

class Plugin(AutoDispatchMixin, TrustedBase):

    @action("greet")
    async def greet(self, payload: dict) -> dict:
        return ok(msg="hello")

    # handle("greet", {}) → appelle self.greet({})
    # handle("unknown", {}) → {"status":"error","code":"unknown_action"}
```

---

### `RoutedPlugin`

Génère automatiquement `get_router()` à partir des méthodes `@route`.

```python
from xcore.sdk.decorators import RoutedPlugin, route

class Plugin(RoutedPlugin, AutoDispatchMixin, TrustedBase):

    @route("/items", method="GET", tags=["items"])
    async def list_items(self):
        return []

    @route("/items/{item_id}", method="DELETE",
           permissions=["admin"])          # RBAC déclaratif
    async def delete_item(self, item_id: int):
        return {"deleted": item_id}

    async def handle(self, action: str, payload: dict) -> dict:
        return error("unknown", "unknown_action")
```

---

## Décorateurs

### `@action(name: str)`

Marque une méthode comme handler d'action. Utilisé par `AutoDispatchMixin`.

```python
@action("create_user")
async def create_user(self, payload: dict) -> dict: ...
```

---

### `@validate_payload(schema, type_response="dict", unset=True)`

Valide le payload avec Pydantic avant d'appeler le handler.

| Paramètre | Type | Description |
|:----------|:-----|:------------|
| `schema` | `Type[BaseModel]` ou `dict` | Schéma de validation |
| `type_response` | `"dict"` ou `"model"` | `"dict"` = `.model_dump()`, `"model"` = instance Pydantic |
| `unset` | `bool` | `True` = exclure les champs non fournis du dict |

```python
from pydantic import BaseModel

class OrderPayload(BaseModel):
    product_id: int
    quantity: int = 1
    note: str | None = None

@action("create_order")
@validate_payload(OrderPayload, type_response="model")
async def create_order(self, payload: OrderPayload) -> dict:
    # payload est un OrderPayload typé
    return ok(product=payload.product_id, qty=payload.quantity)
```

En cas d'erreur de validation, retourne automatiquement :
```json
{"status": "error", "msg": "Validation error", "code": "validation_error", "errors": [...]}
```

---

### `@require_service(*names: str)`

Vérifie que les services sont disponibles avant l'exécution.

```python
@action("save")
@require_service("db", "cache")
async def save(self, payload: dict) -> dict: ...
```

Lève `KeyError` avec message clair si un service est absent.

---

### `@route(path, method, *, tags, summary, status_code, response_model, dependencies, permissions, scopes)`

Déclare une route HTTP FastAPI sur le plugin.

| Paramètre | Défaut | Description |
|:----------|:-------|:------------|
| `path` | — | Chemin relatif (ex : `"/items/{id}"`) |
| `method` | `"GET"` | Verbe HTTP |
| `tags` | `[]` | Tags OpenAPI |
| `summary` | nom de la méthode | Description OpenAPI |
| `status_code` | `200` | Code HTTP de succès |
| `response_model` | `None` | Modèle Pydantic de réponse |
| `dependencies` | `[]` | `Depends()` FastAPI par route |
| `permissions` | `[]` | Permissions RBAC requises |
| `scopes` | `[]` | OAuth2 scopes |

---

### `@trusted` / `@sandboxed`

Marqueurs informatifs — n'affectent pas l'exécution mais documentent l'intention.

```python
@action("admin_action")
@trusted
async def admin_action(self, payload: dict) -> dict: ...
```

---

## Fonctions helpers

### `ok(**kwargs) → dict`

```python
from xcore.kernel.api.contract import ok

return ok(user={"id": 1}, created=True)
# → {"status": "ok", "user": {"id": 1}, "created": True}
```

### `error(msg, code=None, **kwargs) → dict`

```python
from xcore.kernel.api.contract import error

return error("Utilisateur introuvable", code="not_found", user_id=42)
# → {"status": "error", "msg": "Utilisateur introuvable", "code": "not_found", "user_id": 42}
```

---

## PluginManifest (dataclass)

Représentation typée du `plugin.yaml` parsé.

```python
@dataclass
class PluginManifest:
    name: str
    version: str
    plugin_dir: Path
    author: str = "unknown"
    description: str = ""
    framework_version: str = ">=2.0"
    entry_point: str = "src/main.py"
    execution_mode: ExecutionMode = ExecutionMode.LEGACY
    requires: list[PluginDependency] = field(default_factory=list)
    allowed_imports: list[str] = field(default_factory=list)
    permissions: list[dict] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    resources: ResourceConfig = field(default_factory=ResourceConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    filesystem: FilesystemConfig = field(default_factory=FilesystemConfig)
    extra: dict[str, Any] = field(default_factory=dict)
```

### `ResourceConfig`

```python
@dataclass
class ResourceConfig:
    timeout_seconds: int = 10
    max_memory_mb: int = 128
    max_disk_mb: int = 50
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)

@dataclass
class RateLimitConfig:
    calls: int = 100
    period_seconds: int = 60
```

### `PluginDependency`

```python
@dataclass
class PluginDependency:
    name: str
    version_constraint: str = "*"  # "*" ou ">=1.0,<2.0"
```

Formats YAML supportés :
```yaml
requires:
  - other_plugin                  # version="*"
  - name: other_plugin
    version: ">=2.0,<3.0"
```
