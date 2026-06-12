"""
ipc_auth.py — Middleware d'autorisation IPC plugin-à-plugin.

Règles d'autorisation (par ordre de priorité) :
  1. caller=None          → appel HTTP direct, toujours autorisé.
  2. enforce_ipc=false    → toute vérification IPC désactivée.
  3. plugin virtuel       → accessible par tous les callers sans manifest.
  4. manifest introuvable → refus sécurisé.
  5. allowed_callers invalide (YAML malformé) → refus sécurisé.
  6. allowed_callers = ["*"] → wildcard, tout caller autorisé.
  7. allowed_callers = []  → deny-by-default, tout caller refusé.
  8. caller absent de allowed_callers → refusé.
  9. caller présent → autorisé.

Exemple plugin.yaml :
    allowed_callers:
      - billing
      - crm
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Awaitable, Callable

from ...observability import get_logger
from .middleware import Middleware

if TYPE_CHECKING:
    from ..loader import PluginLoader

logger = get_logger("xcore.runtime.ipc_auth")

# Plugins virtuels par défaut — pas de manifest, accessibles par tous.
_DEFAULT_VIRTUAL_PLUGINS: frozenset[str] = frozenset({"xcore"})


class IPCAuthMiddleware(Middleware):
    """
    Vérifie que le plugin appelant (caller) est autorisé à joindre
    le plugin cible via IPC.

    Args:
        loader:          Référence au PluginLoader pour résoudre les manifests.
        enforce:         Active/désactive la vérification IPC globale.
                         Correspond à tenancy.enforce_ipc dans integration.yaml.
        virtual_plugins: Plugins sans manifest, accessibles par tous les callers.
                         Défaut : {"xcore"}.
    """

    def __init__(
        self,
        loader: "PluginLoader",
        enforce: bool = False,
        virtual_plugins: set[str] | None = None,
    ) -> None:
        self._loader = loader
        self._enforce = enforce
        self._virtual_plugins: frozenset[str] = (
            frozenset(virtual_plugins)
            if virtual_plugins is not None
            else _DEFAULT_VIRTUAL_PLUGINS
        )

    async def __call__(
        self,
        plugin_name: str,
        action: str,
        payload: dict,
        next_call: Callable[..., Awaitable[dict]],
        handler,
        **kwargs,
    ) -> dict:
        # `caller` retiré de kwargs pour ne pas polluer les handlers en aval.
        caller: str | None = kwargs.pop("caller", None)
        req_id: str = kwargs.get("request_id", "-")

        # ── 1. Appel HTTP direct (pas IPC) ───────────────────────────────────
        if caller is None:
            return await next_call(plugin_name, action, payload, handler, **kwargs)

        # ── 2. Enforcement désactivé ──────────────────────────────────────────
        if not self._enforce:
            logger.debug(
                "IPC [%s → %s:%s] req=%s autorisé (enforce_ipc=false)",
                caller,
                plugin_name,
                action,
                req_id,
            )
            return await next_call(plugin_name, action, payload, handler, **kwargs)

        # ── 3. Plugin virtuel (ex: xcore) ─────────────────────────────────────
        if plugin_name in self._virtual_plugins:
            logger.debug(
                "IPC [%s → %s:%s] req=%s autorisé (plugin virtuel)",
                caller,
                plugin_name,
                action,
                req_id,
            )
            return await next_call(plugin_name, action, payload, handler, **kwargs)

        # ── 4. Manifest introuvable ───────────────────────────────────────────
        manifest = self._loader.get_manifest(plugin_name)
        if manifest is None:
            logger.warning(
                "IPC [%s → %s:%s] req=%s refusé — manifest introuvable",
                caller,
                plugin_name,
                action,
                req_id,
            )
            return _denied(caller, plugin_name)

        # ── 5. Validation de allowed_callers ──────────────────────────────────
        raw = getattr(manifest, "allowed_callers", None)
        if not isinstance(raw, list) or not all(isinstance(c, str) for c in raw):
            logger.error(
                "IPC [%s → %s:%s] req=%s refusé — allowed_callers invalide "
                "dans le manifest (attendu: list[str], reçu: %r)",
                caller,
                plugin_name,
                action,
                req_id,
                raw,
            )
            return _denied(caller, plugin_name)

        allowed: list[str] = raw

        # ── 6. Wildcard ───────────────────────────────────────────────────────
        if "*" in allowed:
            logger.debug(
                "IPC [%s → %s:%s] req=%s autorisé (wildcard)",
                caller,
                plugin_name,
                action,
                req_id,
            )
            return await next_call(plugin_name, action, payload, handler, **kwargs)

        # ── 7. Deny-by-default (liste vide) ──────────────────────────────────
        if not allowed:
            logger.warning(
                "IPC [%s → %s:%s] req=%s refusé — allowed_callers vide (deny-by-default)",
                caller,
                plugin_name,
                action,
                req_id,
            )
            return _denied(caller, plugin_name)

        # ── 8. Vérification du caller (insensible à la casse) ─────────────────
        if caller.lower() not in {c.lower() for c in allowed}:
            logger.warning(
                "IPC [%s → %s:%s] req=%s refusé — '%s' absent de allowed_callers %s",
                caller,
                plugin_name,
                action,
                req_id,
                caller,
                allowed,
            )
            return _denied(caller, plugin_name)

        # ── 9. Autorisé ───────────────────────────────────────────────────────
        logger.debug(
            "IPC [%s → %s:%s] req=%s autorisé",
            caller,
            plugin_name,
            action,
            req_id,
        )
        return await next_call(plugin_name, action, payload, handler, **kwargs)


def _denied(caller: str | None, target: str) -> dict:
    return {
        "status": "error",
        "code": "ipc_denied",
        "msg": (
            f"Plugin '{caller}' n'est pas autorisé à appeler '{target}' via IPC. "
            f"Ajoutez '{caller}' dans allowed_callers de {target}/plugin.yaml, "
            f"ou utilisez le wildcard '*' pour autoriser tous les callers."
        ),
    }
