"""
RequestTimingMiddleware — ajoute X-Process-Time (ms) à chaque réponse.

Déclaration dans integration.yaml :
    middleware:
      - name: timing
        module: xcore.kernel.api.middlewares.timing:RequestTimingMiddleware
"""

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
