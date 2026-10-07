"""
——— Router FastAPI unique pour tous les plugins.
Construit dynamiquement à partir du PluginSupervisor.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from ..observability import MetricsRegistry, HealthChecker

from fastapi import APIRouter, Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field


class CallRequest(BaseModel):
    """call request body."""

    payload: dict[str, Any] = Field(default_factory=dict)


class DisableRequest(BaseModel):
    """optional body for POST /{plugin_name}/disable."""

    reason: Optional[str] = None


class CallResponse(BaseModel):
    status: str
    plugin: str
    action: str
    result: dict[str, Any]


# =========================
# Security
# =========================

_api_key_header = APIKeyHeader(
    name="X-Plugin-Key",
    auto_error=False,
)


def _hash_key(
    key: Optional[str | bytes],
    server_key: Optional[str | bytes],
    server_key_iterations: int = 100000,
) -> bytes:

    if key is None:
        key_bytes = b""
    elif isinstance(key, bytes):
        key_bytes = key
    else:
        key_bytes = key.encode("utf-8")

    if server_key is None:
        raise ValueError("server_key cannot be None")

    if isinstance(server_key, str):
        server_key = server_key.encode("utf-8")
    return hashlib.pbkdf2_hmac(
        hash_name="sha256",
        password=key_bytes,
        salt=server_key,
        iterations=server_key_iterations,
    )


def build_router(
    supervisor,
    secret_key: bytes,
    server_key: bytes,
    server_key_iterations: int = 100000,
    prefix: str = "",
    tags: list[str] | None = None,
    metrics_registry: MetricsRegistry | None = None,
    health_checker: HealthChecker | None = None,
    **kwargs,
) -> APIRouter:
    """
    Build the router by capturing the supervisor.
    """

    tags = tags or []

    # On hash une seule fois au démarrage
    stored_hash = _hash_key(secret_key, server_key, server_key_iterations)

    async def verify_api_key(
        api_key: str | None = Security(_api_key_header),
    ) -> None:

        if api_key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key missing",
            )

        incoming_hash = _hash_key(api_key, server_key, server_key_iterations)

        # Comparaison sécurisée anti timing attack
        if not hmac.compare_digest(incoming_hash, stored_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized",
            )

    router = APIRouter(
        prefix=f"{prefix}/ipc",
        tags=tags,
        dependencies=[Depends(verify_api_key)],
        **kwargs,
    )

    # =========================
    # Routes
    # =========================
    #
    # NB : ces routes spécifiques (registry/enable/disable) doivent être
    # déclarées AVANT le catch-all POST /{plugin_name}/{action} ci-dessous —
    # Starlette matche dans l'ordre de déclaration, et un POST sur
    # "/{plugin_name}/enable" correspondrait sinon toujours à call_plugin()
    # en premier (action="enable"), qui échoue faute de corps CallRequest.

    @router.get("/registry")
    async def plugins_registry() -> dict[str, Any]:
        """
        Table de vérité complète : tous les plugins présents sur disque, avec
        leur flag persisté (enabled) et leur état live — y compris les
        plugins désactivés ou jamais chargés. Le vrai « centre de contrôle ».
        """
        return {"plugins": supervisor.registry_table()}

    @router.post("/{plugin_name}/enable")
    async def enable_plugin(plugin_name: str) -> dict[str, str]:
        await supervisor.enable(plugin_name)
        return {"status": "ok", "msg": f"Plugin '{plugin_name}' enabled"}

    @router.post("/{plugin_name}/disable")
    async def disable_plugin(
        plugin_name: str, body: DisableRequest | None = None
    ) -> dict[str, str]:
        reason = body.reason if body else None
        await supervisor.disable(plugin_name, reason=reason)
        return {"status": "ok", "msg": f"Plugin '{plugin_name}' disabled"}

    @router.post(
        "/{plugin_name}/{action}",
        response_model=CallResponse,
    )
    async def call_plugin(
        plugin_name: str,
        action: str,
        body: CallRequest,
        request: Request,
    ) -> CallResponse:
        from .auth import resolve_principal_from_request

        tenant_id = getattr(request.state, "tenant_id", "default")
        # Résolution best-effort de l'utilisateur appelant via l'AuthBackend
        # enregistré — None si pas de backend/token, jamais d'erreur ici.
        principal = await resolve_principal_from_request(request)
        result = await supervisor.call(
            plugin_name,
            action,
            body.payload,
            tenant_id=tenant_id,
            principal=principal,
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid supervisor response",
            )

        if result.get("status") == "error" and result.get("code") == "not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result.get("msg", "Plugin not found"),
            )

        return CallResponse(
            status=result.get("status", "ok"),
            plugin=plugin_name,
            action=action,
            result=result,
        )

    @router.get("/status")
    async def plugins_status() -> dict[str, Any]:
        return supervisor.status()

    @router.get("/audit")
    async def ipc_audit(
        plugin: Optional[str] = None, limit: int = 100
    ) -> dict[str, Any]:
        """Journal des appels IPC (qui a appelé quoi, quand) + stats par plugin."""
        return {
            "calls": supervisor.ipc_audit(plugin, limit),
            "stats": supervisor.ipc_stats(),
        }

    @router.get("/events")
    async def events_activity(
        event: Optional[str] = None, limit: int = 100
    ) -> dict[str, Any]:
        """Activité récente de l'EventBus et du HookManager — plus de zone d'ombre sur les events."""
        return {
            "events": supervisor.events_activity(event, limit),
            "hooks": supervisor.hooks_activity(event, limit),
        }

    @router.post("/{plugin_name}/reload")
    async def reload_plugin(plugin_name: str) -> dict[str, str]:
        await supervisor.reload(plugin_name)
        return {"status": "ok", "msg": f"Plugin '{plugin_name}' reloaded"}

    @router.post("/{plugin_name}/load")
    async def load_plugin(plugin_name: str) -> dict[str, str]:
        await supervisor.load(plugin_name)
        return {"status": "ok", "msg": f"Plugin '{plugin_name}' loaded"}

    @router.delete("/{plugin_name}/unload")
    async def unload_plugin(plugin_name: str) -> dict[str, str]:
        await supervisor.unload(plugin_name)
        return {"status": "ok", "msg": f"Plugin '{plugin_name}' unloaded"}

    @router.get("/health")
    async def health_check() -> dict:
        if health_checker is None:
            return {"status": "healthy", "checks": {}}
        return await health_checker.run_all()

    @router.get("/metrics")
    async def metrics_snapshot() -> dict:
        if metrics_registry is None:
            return {}
        return metrics_registry.snapshot()

    return router, verify_api_key
