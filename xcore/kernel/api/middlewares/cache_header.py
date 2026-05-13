"""
CacheHeaderMiddleware — middleware de démonstration avec params internes et externes.

Params :
    header_prefix  (external) — préfixe du header de réponse (ex: "X-App")
    cache          (internal) — service cache (résolu paresseusement via services.get)

Headers ajoutés à chaque réponse :
    {header_prefix}-Cache-Backend : backend du cache (redis, memory…)
    {header_prefix}-Process-Time  : temps de traitement en ms

Déclaration dans integration.yaml :
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
"""

import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class CacheHeaderMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        header_prefix: str = "X-App",
        cache_getter: Callable | None = None,
    ) -> None:
        super().__init__(app)
        self._prefix = header_prefix
        self._cache_getter = cache_getter  # callable () → CacheService

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000

        response.headers[f"{self._prefix}-Process-Time"] = f"{elapsed_ms:.2f}ms"

        # Param interne : on récupère le service au moment de la requête
        if self._cache_getter is not None:
            try:
                cache = self._cache_getter()
                backend = getattr(getattr(cache, "_config", None), "backend", "unknown")
                response.headers[f"{self._prefix}-Cache-Backend"] = backend
            except Exception:
                response.headers[f"{self._prefix}-Cache-Backend"] = "unavailable"

        return response
