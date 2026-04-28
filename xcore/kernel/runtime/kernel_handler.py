# xcore/kernel/runtime/kernel_handler.py

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from supervisor import PluginSupervisor

    from ..context import KernelContext

from .state_machine import PluginState


class KernelHandler:
    """
    Plugin virtuel 'xcore' — expose les internals du kernel via l'IPC existant.

    Appel : supervisor.call("xcore", "plugins.list", {})
            supervisor.call("xcore", "metrics.snapshot", {})
            supervisor.call("xcore", "health.run", {})
            supervisor.call("xcore", "permissions.audit", {"plugin": "my_plugin"})
            supervisor.call("xcore", "registry.services", {})
    """

    # Sentinel — jamais en FAILED/UNLOADED, toujours READY
    state = PluginState.READY

    def __init__(self, ctx: "KernelContext", supervisor: "PluginSupervisor") -> None:
        self._ctx = ctx
        # ref circulaire volontaire (weak si besoin)
        self._supervisor = supervisor

    @property
    def is_available(self) -> bool:
        return True

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    def status(self) -> dict[str, Any]:
        return {"name": "xcore", "mode": "kernel", "state": "ready"}

    # ── Dispatch ──────────────────────────────────────────────

    async def call(self, action: str, payload: dict) -> dict:
        handler = self._ACTIONS.get(action)
        if handler is None:
            available = sorted(self._ACTIONS.keys())
            return {
                "status": "error",
                "msg": f"Action kernel inconnue : '{action}'",
                "code": "unknown_action",
                "available": available,
            }
        try:
            return await handler(self, payload)
        except Exception as e:
            return {"status": "error", "msg": str(e), "code": "kernel_error"}

    def __ok(self, data: dict | None = None, **kwargs) -> dict:
        """Construit une réponse succès standardisée."""
        return {"status": "ok", **(data or {}), **kwargs}

    # ── Actions ───────────────────────────────────────────────

    async def _plugins_list(self, payload: dict) -> dict:
        return self.__ok(
            plugins=self._supervisor.list_plugins(),
        )

    async def _xfow_integration(self, payload: dict) -> dict:
        return self.__ok(
            data={
                "plugin": "xform",
                "display_name": "XForm",
                "description": "Build forms. Launch workflows.",
                "xflow_supported": True,
                "ipc_actions": [
                    {
                        "name": "list plugins",
                        "qualified_name": "plugin.list",
                        "description": "Créer un nouveau formulaire",
                        "input_schema": {},
                        "output_schema": {
                            "status": {"type": "string"},
                            "data": {"type": "dict"},
                        },
                    },
                ],
            }
        )

    # ── Table de dispatch ─────────────────────────────────────

    _ACTIONS: dict = {}  # rempli ci-dessous


# Enregistrement déclaratif (évite les répétitions de string)
KernelHandler._ACTIONS = {
    "plugin.list": KernelHandler._plugins_list,
    "xflow.integration": KernelHandler._xfow_integration,
}
