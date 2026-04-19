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
        self._supervisor = supervisor  # ref circulaire volontaire (weak si besoin)

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

    # ── Actions ───────────────────────────────────────────────

    async def _plugins_list(self, payload: dict) -> dict:
        return {
            "status": "ok",
            "plugins": self._supervisor.list_plugins(),
        }

    # ── Table de dispatch ─────────────────────────────────────

    _ACTIONS: dict = {}  # rempli ci-dessous


# Enregistrement déclaratif (évite les répétitions de string)
KernelHandler._ACTIONS = {
    "plugin.list": KernelHandler._plugins_list,
}
