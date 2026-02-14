"""
router.py
──────────
Route FastAPI unique pour tous les plugins.
Le Core expose /plugin/{name}/{action} — les plugins n'exposent jamais leurs propres routes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from typing import Any

from .manager import PluginManager, PluginNotFound


# ──────────────────────────────────────────────
# Schémas
# ──────────────────────────────────────────────

class PluginCallRequest(BaseModel):
    payload: dict[str, Any] = {}


class PluginCallResponse(BaseModel):
    status:  str
    plugin:  str
    action:  str
    result:  dict[str, Any]


# ──────────────────────────────────────────────
# Dépendance — injecte le PluginManager depuis app.state
# ──────────────────────────────────────────────

async def get_plugin_manager(request: Request) -> PluginManager:
    manager: PluginManager | None = getattr(request.app.state, "plugin_manager", None)
    if manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PluginManager non initialisé",
        )
    return manager


# ──────────────────────────────────────────────
# Router
# ──────────────────────────────────────────────

router = APIRouter(prefix="/app", tags=["plugins"])


@router.post(
    "/{plugin_name}/{action}",
    response_model=PluginCallResponse,
    summary="Appelle une action sur un plugin",
)
async def call_plugin(
    plugin_name: str,
    action:      str,
    body:        PluginCallRequest,
    manager:     PluginManager = Depends(get_plugin_manager),
) -> PluginCallResponse:
    """
    Point d'entrée unique pour tous les appels aux plugins.
    Le Core route vers Trusted (in-process) ou Sandboxed (subprocess IPC).
    """
    result = await manager.call(plugin_name, action, body.payload)

    if result.get("status") == "error" and result.get("code") == "not_found":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("msg", f"Plugin '{plugin_name}' introuvable"),
        )

    return PluginCallResponse(
        status=result.get("status", "ok"),
        plugin=plugin_name,
        action=action,
        result=result,
    )


@router.get(
    "/status",
    summary="Status de tous les plugins chargés",
)
async def plugins_status(
    manager: PluginManager = Depends(get_plugin_manager),
) -> dict:
    """Retourne l'état de tous les plugins (Trusted + Sandboxed)."""
    return manager.status()


@router.post(
    "/{plugin_name}/reload",
    summary="Recharge un plugin à chaud",
)
async def reload_plugin(
    plugin_name: str,
    manager:     PluginManager = Depends(get_plugin_manager),
) -> dict:
    """Recharge un plugin Trusted (hot reload) ou redémarre son subprocess (Sandbox)."""
    try:
        await manager.reload(plugin_name)
        return {"status": "ok", "msg": f"Plugin '{plugin_name}' rechargé"}
    except PluginNotFound as e :
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plugin '{plugin_name}' non chargé",
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e 