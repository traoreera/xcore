# Référence API (Python)

Cette section fournit une référence exhaustive des classes, méthodes et interfaces du noyau XCore.

## `Xcore` (L'Orchestrateur)

La classe principale qui gère le démarrage et l'arrêt de tous les sous-systèmes.

### `__init__(config_path: str = None)`
Initialise l'instance XCore.
- **`config_path`** : Chemin vers le fichier YAML (défaut : `integration.yaml`).

### `async boot(app: FastAPI = None) -> Xcore`
Démarre séquentiellement :
1. Le chargement de la configuration.
2. Le `ServiceContainer` (DB, Cache, etc.).
3. L' `EventBus` et le `HookManager`.
4. Le `PluginSupervisor` et le chargement des plugins.
Si un objet `app` FastAPI est fourni, XCore y attachera automatiquement les routes HTTP des plugins.

### `async shutdown()`
Arrête proprement tous les services et décharge les plugins.

---

## `PluginSupervisor` (Gestion des Plugins)

Gère le cycle de vie et l'exécution sécurisée des plugins.

### `async call(plugin_name: str, action: str, payload: dict) -> dict`
Exécute une action sur un plugin. L'appel traverse le pipeline de middleware :
`Tracing` -> `RateLimit` -> `Permission` -> `Retry` -> `Exécution`.

### `async reload(plugin_name: str)`
Recharge un plugin à chaud, en préservant si possible son état interne via `on_reload`.

### `status() -> dict`
Retourne un état complet de tous les plugins chargés (version, mode, état).

---

## `TrustedBase` (Classe de base des Plugins)

Tous les plugins doivent hériter de cette classe.

### Méthodes du SDK
- **`get_service(name: str) -> Any`** : Récupère un service du conteneur.
- **`get_router() -> APIRouter`** : (Optionnel) Retourne un routeur FastAPI à monter sur le framework.
- **`async handle(action: str, payload: dict) -> dict`** : Point d'entrée obligatoire pour les actions IPC (sauf si `AutoDispatchMixin` est utilisé).

### Hooks de Cycle de Vie
- **`async on_load()`** : Initialisation (connexions DB, etc.).
- **`async on_unload()`** : Nettoyage avant déchargement.
- **`async on_reload()`** : Logique de transition lors d'un rechargement.

---

## `EventBus` (Communication Événementielle)

Permet une communication découplée entre plugins.

### `on(event_pattern: str, priority: int = 50)`
Décorateur pour souscrire à un événement. Supporte les wildcards (`*`).
```python
@events.on("user.*")
async def on_user_event(event):
    print(event.name, event.data)
```

### `async emit(event_name: str, data: dict, source: str = None)`
Diffuse un événement asynchrone à tous les souscripteurs par ordre de priorité.

### `emit_sync(event_name: str, data: dict)`
Version "fire-and-forget" utilisée dans les contextes synchrones.

---

## `ServiceContainer` (Gestion des Services)

Centralise l'accès aux ressources système.

### `get(name: str) -> Any`
Récupère un service. Lève `KeyError` s'il n'existe pas.

### `async health() -> dict`
Exécute les checks de santé de tous les services enregistrés.

---

## `CacheService` (Abstraction du Cache)

Interface unifiée pour Redis ou le cache en mémoire.

### `async get(key: str) -> Any`
### `async set(key: str, value: Any, ttl: int = None)`
### `async get_or_set(key: str, factory: Callable, ttl: int = None)`
Exécute `factory` et met en cache le résultat si la clé est absente.

---

## Décorateurs SDK (`xcore.sdk`)

### `@action(name: str)`
Utilisé avec `AutoDispatchMixin` pour enregistrer automatiquement une méthode comme action IPC.

### `@route(path: str, method: str = "GET", ...)`
Utilisé avec `RoutedPlugin` pour déclarer une route HTTP FastAPI directement sur une méthode.

### `@validate_payload(PydanticModel)`
Valide et injecte automatiquement le payload dans la méthode sous forme d'objet typé.

### `@require_service(*names: str)`
Vérifie la disponibilité des services avant l'exécution.

---

## Helpers de Réponse

### `ok(**kwargs) -> dict`
Retourne `{"status": "ok", ...}`.

### `error(msg: str, code: str = None, **kwargs) -> dict`
Retourne `{"status": "error", "msg": msg, "code": code, ...}`.
