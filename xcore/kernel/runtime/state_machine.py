"""
state_machine.py — Machine à états finie pour le cycle de vie d'un plugin.

Transitions valides :
    UNLOADED  ──load──►  LOADING  ──►  READY
    READY     ──call──►  RUNNING  ──►  READY
    READY     ──unload►  UNLOADING──►  UNLOADED
    READY     ──reload►  RELOADING──►  READY
    *         ──error──►  FAILED
    FAILED    ──reset──►  UNLOADED
"""

from __future__ import annotations

from enum import Enum
from typing import Callable


class PluginState(str, Enum):
    UNLOADED = "unloaded"
    LOADING = "loading"
    READY = "ready"
    RUNNING = "running"
    UNLOADING = "unloading"
    RELOADING = "reloading"
    FAILED = "failed"


# Matrice des transitions autorisées : état_actuel → {événement: état_suivant}
_TRANSITIONS: dict[PluginState, dict[str, PluginState]] = {
    PluginState.UNLOADED: {"load": PluginState.LOADING},
    PluginState.LOADING: {"ok": PluginState.READY, "error": PluginState.FAILED},
    PluginState.READY: {
        "call": PluginState.RUNNING,
        "unload": PluginState.UNLOADING,
        "reload": PluginState.RELOADING,
        "error": PluginState.FAILED,
    },
    PluginState.RUNNING: {"ok": PluginState.READY, "error": PluginState.FAILED},
    PluginState.UNLOADING: {"ok": PluginState.UNLOADED, "error": PluginState.FAILED},
    PluginState.RELOADING: {"ok": PluginState.READY, "error": PluginState.FAILED},
    PluginState.FAILED: {"reset": PluginState.UNLOADED},
}


class InvalidTransition(Exception):
    """Transition non autorisée depuis l'état courant."""


class StateMachine:
    """
    Machine à états finie thread-safe pour un plugin.

    Usage:
        sm = StateMachine("my_plugin")
        sm.transition("load")    # UNLOADED → LOADING
        sm.transition("ok")      # LOADING  → READY
        sm.transition("call")    # READY    → RUNNING
        sm.transition("ok")      # RUNNING  → READY
    """

    def __init__(
        self,
        plugin_name: str,
        on_change: Callable[[PluginState, PluginState], None] | None = None,
    ):
        self._name = plugin_name
        self._state = PluginState.UNLOADED
        self._on_change = on_change

    @property
    def state(self) -> PluginState:
        return self._state

    @property
    def is_ready(self) -> bool:
        return self._state == PluginState.READY

    @property
    def is_failed(self) -> bool:
        return self._state == PluginState.FAILED

    @property
    def is_available(self) -> bool:
        return self._state in (PluginState.READY, PluginState.RUNNING)

    def transition(self, event: str) -> PluginState:
        """
        Effectue une transition.

        Args:
            event: "load" | "ok" | "error" | "call" | "unload" | "reload" | "reset"

        Returns:
            Le nouvel état.

        Raises:
            InvalidTransition: si la transition n'est pas autorisée depuis l'état actuel.
        """
        allowed = _TRANSITIONS.get(self._state, {})
        if event not in allowed:
            raise InvalidTransition(
                f"[{self._name}] Transition '{event}' invalide depuis '{self._state.value}'. "
                f"Transitions autorisées : {list(allowed.keys())}"
            )
        old = self._state
        self._state = allowed[event]
        if self._on_change:
            self._on_change(old, self._state)
        return self._state

    def force(self, state: PluginState) -> None:
        """Force un état (usage interne uniquement, ex: tests)."""
        self._state = state

    def __repr__(self) -> str:
        return f"<StateMachine plugin='{self._name}' state={self._state.value}>"
