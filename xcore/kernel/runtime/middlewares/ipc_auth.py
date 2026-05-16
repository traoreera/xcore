"""
ipc_auth.py — Middleware d'autorisation IPC plugin-à-plugin.

Règle : chaque plugin déclare `allowed_callers` dans plugin.yaml.
  - Liste non vide  → seuls les plugins listés peuvent appeler ce plugin.
  - Liste vide      → tout appel IPC est refusé (deny-by-default).
  - caller = None   → appel HTTP direct (non IPC), toujours autorisé.

Exemple plugin.yaml :
    allowed_callers:
      - billing
      - crm
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

from .middleware import Middleware

if TYPE_CHECKING:
    from ..loader import PluginLoader

logger = logging.getLogger("xcore.runtime.ipc_auth")


class IPCAuthMiddleware(Middleware):
    """
    Vérifie que le plugin appelant (caller) est autorisé à joindre
    le plugin cible via IPC.

    Désactivé si tenancy.enforce_ipc=false dans integration.yaml.
    """

    def __init__(self, loader: "PluginLoader", enforce: bool = True) -> None:
        self._loader = loader
        self._enforce = enforce

    async def __call__(
        self,
        plugin_name: str,
        action: str,
        payload: dict,
        next_call: Callable,
        handler,
        **kwargs,
    ) -> dict:
        caller: str | None = kwargs.get("caller")

        # Appel HTTP direct (pas IPC) → on laisse passer
        if caller is None:
            return await next_call(plugin_name, action, payload, handler, **kwargs)

        # enforce_ipc désactivé → tout IPC autorisé
        if not self._enforce:
            return await next_call(plugin_name, action, payload, handler, **kwargs)

        manifest = self._loader.get_manifest(plugin_name)

        # Plugin non trouvé → refus sécurisé
        if manifest is None:
            logger.warning(
                "IPC [%s → %s:%s] refusé — manifest introuvable",
                caller,
                plugin_name,
                action,
            )
            return _denied(caller, plugin_name)

        allowed: list[str] = getattr(manifest, "allowed_callers", [])

        # Liste vide → deny-by-default
        if not allowed:
            logger.warning(
                "IPC [%s → %s:%s] refusé — aucun caller autorisé (deny-by-default)",
                caller,
                plugin_name,
                action,
            )
            return _denied(caller, plugin_name)

        if caller not in allowed:
            logger.warning(
                "IPC [%s → %s:%s] refusé — '%s' absent de allowed_callers %s",
                caller,
                plugin_name,
                action,
                caller,
                allowed,
            )
            return _denied(caller, plugin_name)

        logger.debug("IPC [%s → %s:%s] autorisé", caller, plugin_name, action)
        return await next_call(plugin_name, action, payload, handler, **kwargs)


def _denied(caller: str, target: str) -> dict:
    return {
        "status": "error",
        "code": "ipc_denied",
        "msg": (
            f"Plugin '{caller}' n'est pas autorisé à appeler '{target}' via IPC. "
            f"Ajoutez '{caller}' dans allowed_callers de {target}/plugin.yaml."
        ),
    }
