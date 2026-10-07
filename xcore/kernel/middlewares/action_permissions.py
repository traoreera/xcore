"""
action_permissions.py — Middleware qui applique les permissions déclarées par
@action(name, permissions=[...]) contre le principal résolu par
AuthResolverMiddleware (kernel/middlewares/auth_resolver.py).
"""

from __future__ import annotations

from ..observability import get_logger
from .middleware import Middleware

logger = get_logger("xcore.runtime.middlewares.action_permissions")


class ActionPermissionMiddleware(Middleware):
    """
    Si l'action ciblée ne déclare aucune permission (cas par défaut, le plus
    courant), ne fait rien — totalement rétrocompatible.

    Sinon, vérifie que le `principal` résolu par AuthResolverMiddleware
    possède au moins un rôle ou une permission couvrant chaque permission
    requise (`principal["roles"] | principal["permissions"]`). Sans
    `principal` (pas de backend enregistré, pas de token) une permission
    déclarée est refusée par défaut — fail-closed : une exigence explicite
    sans identité pour la prouver ne peut pas être silencieusement autorisée.

    Système séparé de PermissionEngine/PolicySet (ACL plugin-à-plugin sur des
    ressources) : celui-ci répond à « cet utilisateur a-t-il le rôle requis »,
    pas « ce plugin a-t-il le droit d'accéder à cette ressource ».
    """

    async def __call__(
        self, plugin_name, action, payload, next_call, handler, **kwargs
    ):
        get_required = getattr(handler, "get_action_permissions", None)
        required: list[str] = get_required(action) if get_required else []

        if required:
            principal = kwargs.get("principal") or {}
            granted = set(principal.get("roles", [])) | set(
                principal.get("permissions", [])
            )
            missing = set(required) - granted
            if missing:
                logger.warning(
                    "action denied — permissions manquantes",
                    plugin=plugin_name,
                    action=action,
                    missing=sorted(missing),
                )
                return {
                    "status": "error",
                    "code": "action_permission_denied",
                    "msg": (
                        f"Permissions manquantes pour '{plugin_name}.{action}' : "
                        f"{sorted(missing)}"
                    ),
                }

        return await next_call(plugin_name, action, payload, handler, **kwargs)
