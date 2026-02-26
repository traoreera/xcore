"""
router.py — Router FastAPI unique pour tous les plugins.
Construit dynamiquement à partir du PluginSupervisor.
"""
from __future__ import annotations
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel


class CallRequest(BaseModel):
    payload: dict[str, Any] = {}


class CallResponse(BaseModel):
    status: str
    plugin: str
    action: str
    result: dict[str, Any]


_api_key_header = APIKeyHeader(name="X-Plugin-Key", auto_error=False)


async def _verify_admin_key(request: Request, api_key: str | None = Security(_api_key_header)) -> None:
    expected: str | None = getattr(request.app.state, "plugin_api_key", None)
    if expected and api_key != expected:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Clé API invalide")


def build_router(supervisor) -> APIRouter:
    """Construit le router en capturant le supervisor."""

    router = APIRouter(prefix="/app", tags=["plugins"])

    @router.post("/{plugin_name}/{action}", response_model=CallResponse)
    async def call_plugin(plugin_name: str, action: str, body: CallRequest) -> CallResponse:
        result = await supervisor.call(plugin_name, action, body.payload)
        if result.get("status") == "error" and result.get("code") == "not_found":
            raise HTTPException(status.HTTP_404_NOT_FOUND, result.get("msg", "Plugin introuvable"))
        return CallResponse(status=result.get("status", "ok"), plugin=plugin_name, action=action, result=result)

    @router.get("/status", dependencies=[Depends(_verify_admin_key)])
    async def plugins_status() -> dict:
        return supervisor.status()

    @router.post("/{plugin_name}/reload", dependencies=[Depends(_verify_admin_key)])
    async def reload_plugin(plugin_name: str) -> dict:
        await supervisor.reload(plugin_name)
        return {"status": "ok", "msg": f"Plugin '{plugin_name}' rechargé"}

    @router.post("/{plugin_name}/load", dependencies=[Depends(_verify_admin_key)])
    async def load_plugin(plugin_name: str) -> dict:
        await supervisor.load(plugin_name)
        return {"status": "ok", "msg": f"Plugin '{plugin_name}' chargé"}

    @router.delete("/{plugin_name}/unload", dependencies=[Depends(_verify_admin_key)])
    async def unload_plugin(plugin_name: str) -> dict:
        await supervisor.unload(plugin_name)
        return {"status": "ok", "msg": f"Plugin '{plugin_name}' déchargé"}

    return router
