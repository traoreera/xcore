# Middlewares

XCore supports automatic loading of ASGI middlewares declared in `integration.yaml`. Two built-in middlewares are included, and you can add your own.

---

## Declaration in `integration.yaml`

```yaml
middleware:
  - name: timing
    module: xcore.kernel.api.middlewares.timing:RequestTimingMiddleware

  - name: cache_header
    module: xcore.kernel.api.middlewares.cache_header:CacheHeaderMiddleware
    config:
      - name: header_prefix
        type: external       # passed as a static value
        value: "X-App"
      - name: cache_getter
        type: internal       # resolved lazily to a service at request time
        value: cache
```

Middlewares are registered on the FastAPI app during `xcore.setup(app)`, which must be called **before** uvicorn starts.

### Parameter types

| `type` | Behavior |
|:-------|:---------|
| `external` | The `value` string is passed directly as a keyword argument |
| `internal` | `value` is a service name; a callable `() → service` is passed — resolved at request time |
| `events` | A callable `() → EventBus` is passed |

---

## Built-in Middlewares

### `RequestTimingMiddleware`

Adds an `X-Process-Time` header (in seconds) to every response.

```yaml
middleware:
  - name: timing
    module: xcore.kernel.api.middlewares.timing:RequestTimingMiddleware
```

### `CacheHeaderMiddleware`

Adds cache-related response headers. Configurable prefix and cache backend.

```yaml
middleware:
  - name: cache_header
    module: xcore.kernel.api.middlewares.cache_header:CacheHeaderMiddleware
    config:
      - name: header_prefix
        type: external
        value: "X-App"
      - name: cache_getter
        type: internal
        value: cache
```

---

## CORS

CORS is configured separately from the middleware list, in its own section:

```yaml
cors:
  allow_origins: ["*", "http://localhost:3000"]
  allow_credentials: false
  allow_methods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
  allow_headers: ["*"]
```

XCore applies `starlette.middleware.cors.CORSMiddleware` with these settings in `main.py`.

---

## Writing a Custom Middleware

```python
# myapp/middlewares/auth_check.py
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class ApiKeyMiddleware(BaseHTTPMiddleware):

    def __init__(self, app, api_key: str = "") -> None:
        super().__init__(app)
        self._api_key = api_key

    async def dispatch(self, request: Request, call_next) -> Response:
        key = request.headers.get("X-API-Key")
        if key != self._api_key:
            from starlette.responses import JSONResponse
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)
```

Register it in `integration.yaml`:

```yaml
middleware:
  - name: api_key
    module: myapp.middlewares.auth_check:ApiKeyMiddleware
    config:
      - name: api_key
        type: external
        value: "${API_KEY}"
```

---

## Middleware Using a Service

If your middleware needs access to a service (e.g., cache for rate limiting), use `type: internal`:

```python
class RateLimitMiddleware(BaseHTTPMiddleware):

    def __init__(self, app, cache_getter=None) -> None:
        super().__init__(app)
        self._cache = cache_getter   # callable: () → CacheService

    async def dispatch(self, request: Request, call_next) -> Response:
        cache = self._cache()        # resolved at request time
        key = f"rate:{request.client.host}"
        count = await cache.get(key) or 0
        if count > 100:
            from starlette.responses import JSONResponse
            return JSONResponse({"error": "Rate limit exceeded"}, status_code=429)
        await cache.set(key, count + 1, ttl=60)
        return await call_next(request)
```

```yaml
middleware:
  - name: rate_limit
    module: myapp.middlewares.rate_limit:RateLimitMiddleware
    config:
      - name: cache_getter
        type: internal
        value: cache
```

---

## Per-Plugin Middleware Pipeline

In addition to global ASGI middlewares, every plugin call passes through a **kernel-level middleware pipeline** configured per plugin:

```
IPC Auth → Tracing → Rate Limit → Permissions → Retry → plugin.handle()
```

This pipeline is configured via `plugin.yaml` (permissions, rate limits, retry) and `integration.yaml` (global security defaults).

---

## Middleware Loading Order

Middlewares are applied in **reverse declaration order** (standard Starlette behavior). The last declared middleware wraps the innermost layer.

```yaml
middleware:
  - name: timing        # outermost — applied last
  - name: cache_header  # innermost — applied first
```

!!! tip
    Always put `timing` first so it measures the total request time including all other middlewares.
