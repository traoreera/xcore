"""
router.py — Router FastAPI unique pour tous les plugins.
Construit dynamiquement à partir du PluginSupervisor.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field


class CallRequest(BaseModel):
    """Requête de appel de plugin."""

    payload: dict[str, Any] = Field(default_factory=dict)


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


def _hash_key(key: Optional[str | bytes]) -> bytes:
    """Hash SHA256 de la clé API."""
    if isinstance(key, bytes):
        return hashlib.sha256(key.decode("utf-8").encode("utf-8")).digest()
    else:
        return hashlib.sha256(key.encode("utf-8")).digest()


def build_router(
    supervisor,
    secret_key: str,  # ← on passe en str, pas bytes
    prefix: str = "",
    tags: list[str] | None = None,
    **kwargs,
) -> APIRouter:
    """
    Construit le router en capturant le supervisor.
    """

    tags = tags or []

    # On hash une seule fois au démarrage
    stored_hash = _hash_key(secret_key)

    async def verify_api_key(
        api_key: str | None = Security(_api_key_header),
    ) -> None:

        if api_key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key missing",
            )

        incoming_hash = _hash_key(api_key)

        # Comparaison sécurisée anti timing attack
        if not hmac.compare_digest(incoming_hash, stored_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized",
            )

    router = APIRouter(
        prefix=prefix,
        tags=tags,
        dependencies=[Depends(verify_api_key)],
        **kwargs,
    )

    # =========================
    # Routes
    # =========================

    @router.post(
        "/{plugin_name}/{action}",
        response_model=CallResponse,
    )
    async def call_plugin(
        plugin_name: str,
        action: str,
        body: CallRequest,
    ) -> CallResponse:

        result = await supervisor.call(plugin_name, action, body.payload)

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

    return router
