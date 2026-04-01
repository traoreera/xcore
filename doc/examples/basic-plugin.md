# Exemple : Plugin Basique (Calculator)

Cet exemple montre comment créer un plugin simple utilisant les fonctionnalités de base du SDK XCore : Actions, Routes HTTP et services.

## Structure du Plugin

```text
plugins/calculator/
├── plugin.yaml
└── src/
    └── main.py
```

## 1. Le Manifeste (`plugin.yaml`)

Le manifeste définit l'identité et les besoins du plugin.

```yaml
name: calculator
version: 1.0.0
author: "Développeur Senior"
description: "Un plugin de calcul simple démontrant le SDK"

execution_mode: trusted
entry_point: src/main.py

# On demande l'accès au service de cache
permissions:
  - resource: "cache.*"
    actions: ["*"]
    effect: allow

# On définit des limites de taux (Rate Limiting)
resources:
  rate_limit:
    calls: 100
    period_seconds: 60
```

## 2. Le Code (`src/main.py`)

Nous utilisons les mixins `AutoDispatchMixin` et `RoutedPlugin` pour simplifier le code.

```python
from xcore.sdk import (
    TrustedBase,
    AutoDispatchMixin,
    RoutedPlugin,
    action,
    route,
    ok,
    error
)

class CalculatorPlugin(AutoDispatchMixin, RoutedPlugin, TrustedBase):

    async def on_load(self) -> None:
        """Initialisation au chargement du plugin."""
        self.cache = self.get_service("cache")
        self.logger.info("Plugin Calculator prêt !")

    # --- Actions IPC (appelées via xcore call ou API interne) ---

    @action("add")
    async def add_action(self, payload: dict):
        a = payload.get("a", 0)
        b = payload.get("b", 0)
        result = a + b

        # Enregistrement dans le cache
        await self.cache.set("last_result", result)

        return ok(result=result)

    # --- Routes HTTP (FastAPI) ---

    @route("/multiply", method="GET")
    async def multiply_route(self, a: float, b: float):
        result = a * b
        return {"operation": "multiply", "result": result}

    @route("/last", method="GET")
    async def get_last_result(self):
        last = await self.cache.get("last_result")
        return {"last_result": last}
```

## 3. Utilisation

### Appel via l'API HTTP (FastAPI)
```bash
curl http://localhost:8000/plugins/calculator/multiply?a=5&b=10
# Réponse : {"operation": "multiply", "result": 50.0}
```

### Appel via le système d'actions (IPC)
```bash
# Via le CLI
xcore plugin call calculator add --payload '{"a": 10, "b": 20}'
# Réponse : {"status": "ok", "result": 30}
```

## Points Clés de l'Exemple
- **Mixins** : `AutoDispatchMixin` génère automatiquement la méthode `handle()`.
- **Décorateurs** : `@action` et `@route` permettent une déclaration claire des points d'entrée.
- **Services** : Utilisation de `self.get_service("cache")` pour la persistance simple.
- **Standardisation** : Utilisation de `ok()` pour des réponses JSON uniformes.
