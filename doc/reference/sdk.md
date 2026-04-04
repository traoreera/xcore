# Référence du SDK XCore

Le SDK XCore fournit tous les outils nécessaires pour créer des plugins performants, sécurisés et hautement intégrés au framework.

---

## 1. Classes de Base (Base Classes)

### `TrustedBase`
C'est la classe mère recommandée pour tout plugin XCore de confiance (`trusted`). Elle fournit un accès natif au contexte et aux services.

**Usage :**
```python
from xcore.sdk import TrustedBase

class Plugin(TrustedBase):
    async def on_load(self):
        # Accès au service de cache
        self.cache = self.get_service("cache")
```

### `BasePlugin`
Protocole de base (Interface) définissant les méthodes minimales requises pour qu'une classe soit reconnue comme un plugin par XCore.

---

## 2. Décorateurs de Fonctionnalité

### `@action(name: str)`
Définit une méthode comme gestionnaire d'une action IPC. À utiliser en combinaison avec `AutoDispatchMixin`.

- **Paramètre** : `name` est l'identifiant de l'action reçu via `PluginSupervisor.call`.

### `@route(path: str, method: str = "GET", ...)`
Expose une méthode comme endpoint HTTP FastAPI. À utiliser en combinaison avec `RoutedPlugin`.

**Arguments :**
- `path` : Chemin relatif de la route (ex: `"/status"`).
- `method` : Méthode HTTP (`"GET"`, `"POST"`, `"PUT"`, `"DELETE"`, etc.).
- `tags` : Liste de tags pour le schéma OpenAPI/Swagger.
- `status_code` : Code HTTP de succès (défaut: 200).
- `permissions` : Liste de permissions RBAC requises (ex: `["user:read"]`).
- `summary` : Description courte de la route.

### `@validate_payload(schema: Type[BaseModel])`
Valide le payload entrant via un modèle **Pydantic** avant l'exécution de la méthode. En cas d'échec, une erreur de validation standard est retournée automatiquement au demandeur.

### `@require_service(*service_names: str)`
Vérifie la présence d'un ou plusieurs services avant l'appel de la méthode. Lève une `KeyError` si un service manque, empêchant l'exécution de la logique métier dans un état instable.

---

## 3. Mixins Utilitaires

### `AutoDispatchMixin`
Implémente automatiquement la méthode obligatoire `handle(action, payload)` en dispatchant les appels vers les méthodes décorées avec `@action`.

### `RoutedPlugin`
Implémente automatiquement le montage du router FastAPI en collectant toutes les méthodes décorées avec `@route`.

**Exemple de Plugin combiné :**
```python
from xcore.sdk import TrustedBase, AutoDispatchMixin, RoutedPlugin, action, route

class MyPlugin(RoutedPlugin, AutoDispatchMixin, TrustedBase):
    @action("ping")
    async def ping_action(self, payload: dict):
        return {"status": "ok", "msg": "pong"}

    @route("/ping", method="GET")
    async def ping_http(self):
        return {"pong": True}
```

---

## 4. Repositories SQL (`BaseSyncRepository` / `BaseAsyncRepository`)

Fournit des méthodes CRUD prêtes à l'emploi pour vos modèles SQLAlchemy.

**Méthodes disponibles :**
- `get_by_id(id)` : Récupère un objet par sa clé primaire.
- `get_all()` : Liste tous les objets.
- `create(obj)` : Ajoute un nouvel objet en base.
- `update(id, data)` : Met à jour les champs spécifiés d'un objet.
- `delete(id)` : Supprime un objet.
- `get_by_name(name)` : Helper pour récupérer par le champ `name`.

---

## 5. Helpers de Réponse

Utilisez toujours ces helpers pour garantir la compatibilité avec le framework XCore.

- **`ok(**kwargs)`** : Retourne un dictionnaire `{"status": "ok", ...kwargs}`.
- **`error(msg, code=None, status_code=400, **kwargs)`** : Retourne un dictionnaire `{"status": "error", "msg": msg, "code": code, ...kwargs}`.

---

## 6. Contexte du Plugin (`self.ctx`)

L'objet `ctx` (PluginContext) contient les métadonnées et les points d'accès au framework :

| Propriété | Description |
|-----------|-------------|
| `self.ctx.name` | Nom unique du plugin. |
| `self.ctx.version` | Version du plugin (depuis `plugin.yaml`). |
| `self.ctx.config` | Bloc `extra` du manifeste résolu. |
| `self.ctx.events` | Accès au bus d'événements global. |
| `self.ctx.hooks` | Accès au gestionnaire de hooks. |
| `self.ctx.metrics` | Registre pour les compteurs et jauges locaux. |
| `self.ctx.tracer` | Système de tracing pour les spans locaux. |
| `self.ctx.health` | Registre de health checks locaux. |
