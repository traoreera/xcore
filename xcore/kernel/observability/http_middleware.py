"""
http_middleware.py — Middleware ASGI d'extraction du contexte de trace W3C.

Lit le header `traceparent` (et `tracestate`) de chaque requête HTTP entrante
et l'attache comme contexte OpenTelemetry actif le temps de la requête, pour
que tout span ouvert plus loin dans la pile (TracingMiddleware du pipeline
plugin, hop IPC vers un sandbox…) soit corrélé au bon trace_id plutôt que
d'en démarrer un nouveau. Sans header entrant (client non instrumenté), le
contexte extrait est vide — comportement inchangé, un nouveau trace démarre.
"""

from __future__ import annotations

from opentelemetry import context as otel_context
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .tracing import extract_trace_context


class TraceContextMiddleware(BaseHTTPMiddleware):
    """Extrait le traceparent entrant et l'attache comme contexte OTel actif."""

    async def dispatch(self, request: Request, call_next) -> Response:
        ctx = extract_trace_context(dict(request.headers))
        token = otel_context.attach(ctx)
        try:
            return await call_next(request)
        finally:
            otel_context.detach(token)
