"""
tenancy/middleware.py — Middleware FastAPI d'extraction du tenant.

Lit le tenant depuis (par ordre de priorité) :
  1. Header HTTP  X-Tenant-ID
  2. Sous-domaine : acme.myapp.com → "acme"
  3. Fallback     : "default"

Injecte le résultat dans request.state.tenant_id pour que le router
puisse le transmettre à supervisor.call().
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

if TYPE_CHECKING:
    from ...configurations.sections import TenancyConfig


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Extrait le tenant_id de chaque requête HTTP et l'injecte dans
    request.state.tenant_id.

    Configuré via integration.yaml section `tenancy`.
    Si tenancy.enabled=false → tenant_id = default_tenant sur toutes les requêtes.
    """

    def __init__(self, app, config: "TenancyConfig | None" = None) -> None:
        super().__init__(app)
        from ...configurations.sections import TenancyConfig as _TC

        self._cfg = config or _TC()

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self._cfg.enabled:
            request.state.tenant_id = self._cfg.default_tenant
            return await call_next(request)

        tenant_id = (
            request.headers.get(self._cfg.header)
            or (self._from_subdomain(request) if self._cfg.subdomain else None)
            or self._cfg.default_tenant
        )
        request.state.tenant_id = tenant_id
        return await call_next(request)

    @staticmethod
    def _from_subdomain(request: Request) -> str | None:
        host = request.headers.get("host", "")
        parts = host.split(".")
        # acme.myapp.com → ["acme", "myapp", "com"] → "acme"
        # localhost ou myapp.com → pas de sous-domaine
        if len(parts) >= 3:
            return parts[0]
        return None
