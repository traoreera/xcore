# Quick Start

Créez votre première application XCore et votre premier plugin en **5 minutes**.

---

## Étape 1 — Configuration

Créez `xcore.yaml` à la racine :

```yaml
app:
  name: "mon-app"
  debug: true
  secret_key: "change-me-in-production"
  plugin_prefix: "/plugin"

plugins:
  directory: "./plugins"
  secret_key: "change-me-in-production"
  strict_trusted: false

services:
  databases:
    db:
      type: sqlasync
      url: sqlite+aiosqlite:///./app.db

  cache:
    backend: memory
    ttl: 300

  scheduler:
    enabled: false
```

---

## Étape 2 — Point d'entrée FastAPI

```python
# main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from xcore import Xcore

xcore = Xcore(config_path="xcore.yaml")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await xcore.boot(app)   # démarre kernel + services + plugins
    yield
    await xcore.shutdown()  # arrêt propre

app = FastAPI(title="Mon App XCore", lifespan=lifespan)
```

---

## Étape 3 — Premier plugin

```
plugins/
└── hello/
    ├── plugin.yaml
    └── src/
        └── main.py
```

**`plugins/hello/plugin.yaml`** :

```yaml
name: hello
version: "1.0.0"
author: moi
description: Plugin de démonstration
execution_mode: trusted
entry_point: src/main.py

permissions:
  - resource: "cache.*"
    actions: ["read", "write"]
    effect: allow
```

**`plugins/hello/src/main.py`** :

```python
from xcore.kernel.api.contract import TrustedBase, ok, error
from xcore.sdk.decorators import AutoDispatchMixin, action, validate_payload
from pydantic import BaseModel

class GreetPayload(BaseModel):
    name: str

class Plugin(AutoDispatchMixin, TrustedBase):

    async def on_load(self):
        self.cache = self.get_service("cache")

    @action("greet")
    @validate_payload(GreetPayload)
    async def greet(self, payload: GreetPayload) -> dict:
        cached = await self.cache.get(f"greet:{payload.name}")
        if cached:
            return ok(message=cached, from_cache=True)

        msg = f"Bonjour, {payload.name} !"
        await self.cache.set(f"greet:{payload.name}", msg, ttl=60)
        return ok(message=msg)

    @action("ping")
    async def ping(self, payload: dict) -> dict:
        return ok(pong=True)
```

---

## Étape 4 — Lancer et tester

```bash
# Démarrer
poetry run uvicorn main:app --reload

# Tester via curl
curl -X POST http://localhost:8000/plugin/hello/action \
     -H "Content-Type: application/json" \
     -d '{"action": "greet", "payload": {"name": "Dev"}}'

# Réponse
{"status": "ok", "message": "Bonjour, Dev !"}
```

---

## Étape 5 — CLI

```bash
# Lister les plugins chargés
poetry run xcore plugin list

# Inspecter un plugin
poetry run xcore plugin info hello

# Recharger à chaud
poetry run xcore plugin reload hello
```

---

## Prochaines étapes

| Objectif | Doc |
|:---------|:----|
| Ajouter des routes HTTP au plugin | [Créer un plugin](../guides/creating-plugins.md) |
| Connecter une base de données | [Services](../guides/services.md) |
| Mettre en place la sécurité | [Sécurité](../guides/security.md) |
| Comprendre l'architecture | [Architecture](../architecture/overview.md) |
