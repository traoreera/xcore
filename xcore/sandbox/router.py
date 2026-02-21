"""
router.py
──────────
Route FastAPI unique pour tous les plugins.
Le Core expose /plugin/{name}/{action} — les plugins n'exposent jamais leurs propres routes.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

from .manager import PluginManager, PluginNotFound

# ──────────────────────────────────────────────
# Schémas
# ──────────────────────────────────────────────


class PluginCallRequest(BaseModel):
    payload: dict[str, Any] = {}


class PluginCallResponse(BaseModel):
    status: str
    plugin: str
    action: str
    result: dict[str, Any]


# ──────────────────────────────────────────────
# Auth — API Key via header X-Plugin-Key
# ✅ Nouveau : les routes d'administration (reload, load, unload)
# nécessitent une clé API passée dans le header X-Plugin-Key.
# La clé est lue depuis app.state.plugin_api_key au démarrage.
# ──────────────────────────────────────────────

_api_key_header = APIKeyHeader(name="X-Plugin-Key", auto_error=False)


async def verify_admin_key(
    request: Request,
    api_key: str | None = Security(_api_key_header),
) -> None:
    """
    Vérifie la clé d'administration.
    Si aucune clé n'est configurée dans app.state, la vérification est ignorée
    (pratique pour le développement local).
    """
    expected: str | None = getattr(request.app.state, "plugin_api_key", None)
    if expected is None:
        return  # Pas de clé configurée → mode dev, pas de restriction
    if api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API invalide ou manquante (header X-Plugin-Key requis)",
        )


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
    action: str,
    body: PluginCallRequest,
    manager: PluginManager = Depends(get_plugin_manager),
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
    dependencies=[Depends(verify_admin_key)],  # ✅ protégé
)
async def plugins_status(
    manager: PluginManager = Depends(get_plugin_manager),
) -> dict:
    """Retourne l'état de tous les plugins (Trusted + Sandboxed)."""
    return manager.status()


@router.post(
    "/{plugin_name}/reload",
    summary="Recharge un plugin à chaud",
    dependencies=[Depends(verify_admin_key)],  # ✅ protégé
)
async def reload_plugin(
    plugin_name: str,
    manager: PluginManager = Depends(get_plugin_manager),
) -> dict:
    """Recharge un plugin Trusted (hot reload) ou redémarre son subprocess (Sandbox)."""
    try:
        await manager.reload(plugin_name)
        return {"status": "ok", "msg": f"Plugin '{plugin_name}' rechargé"}
    except PluginNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plugin '{plugin_name}' non chargé",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post(
    "/{plugin_name}/load",
    summary="Charge un plugin par son nom de dossier",
    dependencies=[Depends(verify_admin_key)],  # ✅ protégé
)
async def load_plugin(
    plugin_name: str,
    manager: PluginManager = Depends(get_plugin_manager),
) -> dict:
    """✅ Nouveau : charge un plugin unique sans redémarrer l'application."""
    try:
        await manager.load(plugin_name)
        return {"status": "ok", "msg": f"Plugin '{plugin_name}' chargé"}
    except PluginNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dossier plugin '{plugin_name}' introuvable",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.delete(
    "/{plugin_name}/unload",
    summary="Décharge un plugin sans arrêter l'application",
    dependencies=[Depends(verify_admin_key)],  # ✅ protégé
)
async def unload_plugin(
    plugin_name: str,
    manager: PluginManager = Depends(get_plugin_manager),
) -> dict:
    """✅ Nouveau : décharge un plugin unique proprement."""
    try:
        await manager.unload(plugin_name)
        return {"status": "ok", "msg": f"Plugin '{plugin_name}' déchargé"}
    except PluginNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plugin '{plugin_name}' non chargé",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
