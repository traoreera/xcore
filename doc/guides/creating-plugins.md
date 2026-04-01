# Créer des Plugins

Ce guide vous explique comment créer des plugins pour XCore, du plus simple au plus complexe.

## Structure d'un Plugin

Un plugin est un dossier situé dans le répertoire `plugins/` (configurable dans `xcore.yaml`) contenant au minimum :

```text
mon-plugin/
├── plugin.yaml      # Manifeste du plugin
└── src/
    └── main.py     # Code source principal
```

## 1. Le Manifeste (`plugin.yaml`)

C'est ici que vous définissez l'identité, le mode d'exécution et les permissions de votre plugin.

```yaml
name: mon-plugin
version: 1.0.0
author: "Votre Nom"
description: "Une brève description"

# Modes : trusted (accès total) ou sandboxed (isolé)
execution_mode: trusted
entry_point: src/main.py

# Dépendances vers d'autres plugins
requires:
  - plugin-auth

# Permissions d'accès aux services core
permissions:
  - resource: "db.*"
    actions: ["read", "write"]
    effect: allow
```

## 2. Le SDK XCore

Pour créer un plugin, vous devez hériter de `TrustedBase`. Le SDK fournit des outils pour simplifier le développement.

### Exemple minimaliste

```python
from xcore.sdk import TrustedBase, ok

class MyPlugin(TrustedBase):
    async def handle(self, action: str, payload: dict) -> dict:
        if action == "ping":
            return ok(message="pong")
        return ok()
```

### Utilisation des Mixins (Recommandé)

Les mixins permettent d'automatiser le dispatch des actions et la création de routes HTTP.

```python
from xcore.sdk import TrustedBase, AutoDispatchMixin, RoutedPlugin, action, route

class AdvancedPlugin(AutoDispatchMixin, RoutedPlugin, TrustedBase):

    @action("greet")
    async def greet_action(self, payload: dict):
        return ok(msg=f"Hello {payload.get('name')}")

    @route("/hello", method="GET")
    async def hello_route(self, name: str):
        return {"hello": name}
```

## 3. Cycle de Vie

Vous pouvez surcharger des méthodes pour gérer le cycle de vie de votre plugin :

- `on_load()` : Appelé au démarrage du plugin. Idéal pour initialiser des connexions ou récupérer des services.
- `on_unload()` : Appelé à l'arrêt du plugin. Utilisez-le pour nettoyer les ressources.
- `on_reload()` : Appelé lors d'un rechargement à chaud.

```python
async def on_load(self):
    self.db = self.get_service("db")
    self.logger.info("Base de données connectée")
```

## 4. Accès aux Services

Utilisez `self.get_service("nom_du_service")` pour accéder aux fonctionnalités globales :
- `db` : Accès SQL/NoSQL.
- `cache` : Accès Redis/Mémoire.
- `scheduler` : Planification de tâches.
- `events` : Bus d'événements.

## 5. Validation des Données

Il est fortement conseillé d'utiliser le décorateur `@validate_payload` avec des modèles Pydantic pour sécuriser vos actions.

```python
from pydantic import BaseModel
from xcore.sdk import validate_payload

class GreetSchema(BaseModel):
    name: str

@action("greet")
@validate_payload(GreetSchema)
async def greet(self, validated_data: GreetSchema):
    return ok(msg=f"Hi {validated_data.name}")
```

## 6. Tester votre Plugin

Vous pouvez tester un plugin sans lancer tout le framework via le CLI :

```bash
xcore sandbox run ./mon-plugin
```

Cela lancera le plugin dans un environnement isolé pour vérifier qu'il n'y a pas d'erreurs de syntaxe ou de violation de sécurité (si mode sandboxed).
