# Exemple de Plugin Basique

Cet exemple présente un plugin de calculatrice simple utilisant les fonctionnalités de base de XCore v2 : actions IPC, routes HTTP, services et mixins du SDK.

## Structure du Plugin

```text
plugins/calculator/
├── plugin.yaml
└── src/
    └── main.py
```

## `plugin.yaml`

```yaml
name: calculator
version: 1.0.0
author: XCore Team
description: Une calculatrice simple avec IPC et HTTP

execution_mode: trusted
framework_version: ">=2.0"
entry_point: src/main.py

permissions:
  - resource: "cache.*"
    actions: ["read", "write"]
    effect: allow

resources:
  timeout_seconds: 10
  rate_limit:
    calls: 1000
    period_seconds: 60
```

## `src/main.py`

Utilisation des mixins `AutoDispatchMixin` et `RoutedPlugin` pour simplifier le code.

```python
"""Plugin calculatrice démontrant les fonctionnalités de XCore."""
from __future__ import annotations

import time
from fastapi import APIRouter, HTTPException, Query
from xcore.sdk import (
    TrustedBase,
    AutoDispatchMixin,
    RoutedPlugin,
    action,
    route,
    ok,
    error
)

class Plugin(RoutedPlugin, AutoDispatchMixin, TrustedBase):
    """Plugin calculatrice avec opérations de base."""

    def __init__(self) -> None:
        super().__init__()
        self.operations_count = 0

    async def on_load(self) -> None:
        """Initialisation au chargement."""
        self.cache = self.get_service("cache")
        self.ctx.metrics.counter("calc.load").inc()
        print("✅ Calculator plugin chargé")

    async def on_unload(self) -> None:
        """Nettoyage au déchargement."""
        print(f"📊 Total des opérations: {self.operations_count}")

    # --- Actions IPC (Appelables via xcore.plugins.call) ---

    @action("add")
    async def add_action(self, payload: dict):
        res = payload.get("a", 0) + payload.get("b", 0)
        await self._cache_operation("add", payload.get("a"), payload.get("b"), res)
        return ok(result=res)

    @action("divide")
    async def divide_action(self, payload: dict):
        b = payload.get("b", 0)
        if b == 0:
            return error("Division par zéro", code="zero_div")
        res = payload.get("a", 0) / b
        await self._cache_operation("divide", payload.get("a"), b, res)
        return ok(result=res)

    # --- Routes HTTP (FastAPI) ---

    @route("/add", method="GET", tags=["public"])
    async def add_http(
        self,
        a: float = Query(..., description="Premier nombre"),
        b: float = Query(..., description="Deuxième nombre")
    ):
        """Additionne deux nombres."""
        result = a + b
        await self._cache_operation("add", a, b, result)
        return {"operation": "add", "a": a, "b": b, "result": result}

    @route("/history", method="GET")
    async def get_history(self):
        """Récupère l'historique depuis le cache."""
        history = await self.cache.get("calc:history") or []
        return {"history": history}

    # --- Méthodes internes ---

    async def _cache_operation(self, op: str, a: float, b: float, res: float):
        self.operations_count += 1
        entry = {"op": op, "a": a, "b": b, "res": res, "ts": time.time()}
        history = await self.cache.get("calc:history") or []
        history.insert(0, entry)
        await self.cache.set("calc:history", history[:50], ttl=3600)
```

## Points clés démontrés

1.  **Héritage multiple** : Utilisation de `RoutedPlugin` et `AutoDispatchMixin`.
2.  **Décorateurs** : `@action` pour l'IPC et `@route` pour le Web.
3.  **Observabilité** : Utilisation de `self.ctx.metrics` pour compter les chargements.
4.  **Services** : Utilisation de `self.get_service("cache")` pour la persistance temporaire.
5.  **Cycle de vie** : Utilisation de `on_load` et `on_unload`.
