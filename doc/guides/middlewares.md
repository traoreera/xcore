# Middlewares

xcore supporte le chargement automatique de middlewares ASGI déclarés dans `integration.yaml`.

---

## Concept

Un middleware intercepte chaque requête HTTP **avant** qu'elle atteigne les routes et **après** que la réponse est générée. xcore charge les middlewares au démarrage via `xcore.setup(app)`, avant que le serveur accepte des connexions.

---

## Déclarer un middleware

```yaml
# integration.yaml
middleware:
  - name: mon_middleware
    module: myapp.middlewares.auth:AuthMiddleware
    config:
      - name: secret
        type: external
        value: "${JWT_SECRET}"
      - name: cache_getter
        type: internal
        value: cache        # clé du ServiceContainer
```

| Champ | Description |
|:------|:------------|
| `name` | Identifiant (logs uniquement) |
| `module` | Chemin Python `package.module:ClassName` |
| `config` | Liste de paramètres |

### Types de paramètres

| `type` | Comportement |
|:-------|:-------------|
| `external` | Valeur passée directement au constructeur |
| `internal` | Callable `() → service` passé — service résolu paresseusement à chaque requête |

> Les params `internal` sont paresseux : `setup()` est appelé avant `boot()`, donc les services ne sont pas encore disponibles. Le middleware reçoit un callable et doit appeler `mon_param()` dans `dispatch()`.

---

## Écrire un middleware

Tout middleware doit hériter de `BaseHTTPMiddleware` (Starlette).

### Middleware simple (params externes)

```python
# myapp/middlewares/timing.py
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class RequestTimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Process-Time"] = f"{elapsed_ms:.2f}ms"
        return response
```

```yaml
middleware:
  - name: timing
    module: myapp.middlewares.timing:RequestTimingMiddleware
```

### Middleware avec service interne

```python
# myapp/middlewares/cache_header.py
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class CacheHeaderMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        header_prefix: str = "X-App",
        cache_getter: Callable | None = None,   # () → CacheService
    ) -> None:
        super().__init__(app)
        self._prefix = header_prefix
        self._cache_getter = cache_getter

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers[f"{self._prefix}-OK"] = "true"

        if self._cache_getter is not None:
            cache = self._cache_getter()          # résolution paresseuse ici
            backend = getattr(getattr(cache, "_config", None), "backend", "unknown")
            response.headers[f"{self._prefix}-Cache-Backend"] = backend

        return response
```

```yaml
middleware:
  - name: cache_header
    module: myapp.middlewares.cache_header:CacheHeaderMiddleware
    config:
      - name: header_prefix
        type: external
        value: "X-App"
      - name: cache_getter
        type: internal
        value: cache
```

---

## Enregistrement dans l'application

```python
# main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from xcore import Xcore

xcore = Xcore()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await xcore.boot(app)
    yield
    await xcore.shutdown()

app = FastAPI(lifespan=lifespan)
xcore.setup(app)     # ← AVANT le démarrage, APRÈS FastAPI()
```

> `xcore.setup(app)` doit être appelé après `FastAPI()` et avant que uvicorn démarre — jamais à l'intérieur du lifespan.

---

## Middlewares intégrés

| Classe | Module | Description |
|:-------|:-------|:------------|
| `RequestTimingMiddleware` | `xcore.kernel.api.middlewares.timing` | Ajoute `X-Process-Time` à chaque réponse |
| `CacheHeaderMiddleware` | `xcore.kernel.api.middlewares.cache_header` | Headers de diagnostic cache et timing |

---

## Ordre d'exécution

Les middlewares sont appliqués dans l'**ordre inverse** de déclaration (comportement Starlette) : le dernier déclaré enveloppe en premier.

```yaml
middleware:
  - name: auth       # enveloppe externe — vu en 2e
  - name: timing     # enveloppe interne — vu en 1er (plus proche des routes)
```
