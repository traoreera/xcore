# Référence de l'API

Référence complète de l'API pour les classes et interfaces de XCore.

## Xcore

Classe orchestratrice principale.

```python
from xcore import Xcore

class Xcore:
    def __init__(self, config_path: str | None = None)
    async def boot(self, app=None) -> "Xcore"
    async def shutdown(self) -> None
```

### Attributs

| Attribut | Type | Description |
|-----------|------|-------------|
| `services` | `ServiceContainer` | Conteneur de services |
| `plugins` | `PluginSupervisor` | Superviseur de plugins |
| `events` | `EventBus` | Bus d'événements |
| `hooks` | `HookManager` | Gestionnaire de hooks |
| `registry` | `PluginRegistry` | Registre de plugins |

### Méthodes

#### `__init__`

```python
def __init__(self, config_path: str | None = None)
```

Initialise l'instance XCore.

**Paramètres**:
- `config_path`: Chemin vers le fichier de configuration YAML (par défaut : `xcore.yaml`)

#### `boot`

```python
async def boot(self, app=None) -> "Xcore"
```

Démarre tous les sous-systèmes.

**Paramètres**:
- `app`: Instance de l'application FastAPI (optionnel)

**Retourne**:
- L'instance elle-même (pour chaînage)

#### `shutdown`

```python
async def shutdown(self) -> None
```

Arrête proprement tous les sous-systèmes.

---

## TrustedBase

Classe de base pour les plugins de confiance (mode `trusted`).

```python
from xcore.sdk import TrustedBase

class Plugin(TrustedBase):
    ...
```

### Attributs

| Attribut | Type | Description |
|-----------|------|-------------|
| `ctx` | `PluginContext` | Contexte du plugin (injecté) |

### Méthodes

#### `get_service`

```python
def get_service(self, name: str) -> Any
```

Récupère un service par son nom.

#### `get_router`

```python
def get_router(self) -> APIRouter | None
```

Retourne un router FastAPI personnalisé. À surcharger pour exposer des endpoints HTTP.

#### `handle`

```python
@abstractmethod
async def handle(self, action: str, payload: dict) -> dict
```

Gère les actions IPC.

### Hooks de Cycle de Vie

- `on_load()`: Appelé au chargement.
- `on_unload()`: Appelé au déchargement.
- `on_reload()`: Appelé au rechargement.

---

## PluginSupervisor

Interface de haut niveau pour la gestion des plugins.

```python
from xcore.kernel.runtime.supervisor import PluginSupervisor
```

### Méthodes

#### `call`

```python
async def call(
    self,
    plugin_name: str,
    action: str,
    payload: dict
) -> dict
```

Appelle une action sur un plugin via la pipeline de middlewares.

#### `load` / `unload` / `reload`

Gère dynamiquement l'état d'un plugin par son nom.

#### `status`

```python
def status(self) -> dict
```

Retourne l'état actuel de tous les plugins.

---

## PluginLoader

Gère la découverte et le chargement ordonné des plugins.

```python
from xcore.kernel.runtime.loader import PluginLoader
```

### Méthodes

#### `load_all`

```python
async def load_all(self) -> dict[str, list[str]]
```

Scanne le répertoire et charge tous les plugins en respectant le tri topologique des dépendances.

#### `get`

```python
def get(self, name: str) -> PluginHandler
```

Récupère le handler (LifecycleManager ou SandboxProcessManager) pour un plugin.

---

## LifecycleManager

Gère le cycle de vie d'un plugin spécifique en mode `trusted`.

```python
from xcore.kernel.runtime.lifecycle import LifecycleManager
```

### Méthodes

#### `load` / `unload` / `reload`

Effectue les transitions d'état et invoque les hooks du plugin.

#### `propagate_services`

```python
def propagate_services(self, *, is_reload: bool = False) -> dict
```

Expose les services internes du plugin au conteneur global.

---

## EventBus

Gestion des abonnements et de l'émission d'événements.

```python
from xcore.kernel.events.bus import EventBus, Event
```

### Méthodes

#### `on` / `once`

Décorateurs pour s'abonner à un événement (une seule fois pour `once`).

**Paramètres**:
- `event_name`: Nom ou pattern de l'événement.
- `priority`: Priorité (0-100, défaut 50).

#### `emit`

```python
async def emit(self, event_name: str, data: dict = None) -> list[Any]
```

Émet un événement de manière asynchrone.

---

## Sécurité

### ASTScanner

Analyse statique du code source pour les plugins `sandboxed`.

```python
from xcore.kernel.security.validation import ASTScanner
```

- `scan(plugin_dir)`: Scanne tous les fichiers `.py` et retourne un `ScanResult`.

### FilesystemGuard

Protection du système de fichiers par monkey-patching.

```python
from xcore.kernel.sandbox.worker import FilesystemGuard
```

- `install()`: Installe les protections sur `open`, `os`, `pathlib`, etc.
- `is_allowed(path)`: Vérifie si un chemin respecte la politique du manifeste.

### PermissionEngine

Moteur de contrôle d'accès granulaire (RBAC/ABAC).

```python
from xcore.kernel.permissions.engine import PermissionEngine
```

- `check(plugin, resource, action)`: Lève `PermissionDenied` si non autorisé.

---

## Observabilité

### HealthChecker

Registre de diagnostics de santé.

```python
from xcore.kernel.observability.health import HealthChecker
```

- `register(name)`: Décorateur pour enregistrer un check.
- `run_all()`: Exécute tous les diagnostics en parallèle.

### MetricsRegistry

Registre de métriques léger.

```python
from xcore.kernel.observability.metrics import MetricsRegistry
```

- `counter(name, labels)` / `gauge(name, labels)` / `histogram(name)`: Crée ou récupère une métrique.
- `snapshot()`: Retourne l'état actuel de toutes les métriques.

### Tracer

Système de tracing distribué.

```python
from xcore.kernel.observability.tracing import Tracer
```

- `span(name, **attrs)`: Gestionnaire de contexte pour créer un span.

---

## Services Intégrés

### ServiceContainer

Gestion et accès aux services.

```python
from xcore.services.container import ServiceContainer
```

- `get(name)`: Récupère un service (lève `KeyError` si absent).
- `health()`: Vérifie la santé de tous les services.

### CacheService

Opérations de cache.

```python
from xcore.services.cache.service import CacheService
```

- `get(key)` / `set(key, value, ttl)` / `delete(key)`: Opérations standards.
- `get_or_set(key, factory, ttl)`: Récupère ou calcule et met en cache.

---

## Fonctions Utilitaires

### `ok` / `error`

Helpers pour standardiser les réponses IPC et HTTP.

```python
from xcore.kernel.api.contract import ok, error

return ok(data="valeur")
# {"status": "ok", "data": "valeur"}

return error("Message", code="err_code")
# {"status": "error", "msg": "Message", "code": "err_code"}
```

---

## Exceptions

- `RateLimitExceeded`: Limite de débit atteinte.
- `PermissionDenied`: Accès refusé par le moteur de permissions.
- `LoadError`: Échec critique lors du chargement d'un plugin.
- `ValidationError`: Manifeste ou code source invalide.
