"""
action_permissions.py — Middleware qui applique les permissions déclarées par
@action(name, permissions=[...], permission_groups=[[...], ...]) contre le
principal résolu par AuthResolverMiddleware (kernel/middlewares/auth_resolver.py).
"""

from __future__ import annotations

from ..observability import get_logger
from .middleware import Middleware

logger = get_logger("xcore.runtime.middlewares.action_permissions")


class ActionPermissionMiddleware(Middleware):
    """
    Si l'action ciblée ne déclare ni permission ni groupe (cas par défaut, le
    plus courant), ne fait rien — totalement rétrocompatible.

    `permissions` (ET) : vérifie que le `principal` résolu par
    AuthResolverMiddleware possède au moins un rôle ou une permission couvrant
    CHAQUE permission requise (`principal["roles"] | principal["permissions"]`).

    `permission_groups` (OU de ET) : satisfait si le principal couvre
    ENTIÈREMENT au moins un des groupes déclarés — pour une hiérarchie de rôles
    où plusieurs permissions distinctes donnent chacune un accès suffisant
    (ex : le responsable d'un tenant OU l'administrateur de la plateforme).
    `permissions` seul ne peut pas exprimer cette alternative : il exigerait
    les deux permissions à la fois plutôt que l'une ou l'autre.

    Si les deux sont déclarés sur la même action, les deux conditions
    s'appliquent (ET global) : `permissions` doit être entièrement satisfait,
    ET au moins un groupe de `permission_groups` doit l'être aussi.

    Sans `principal` (pas de backend enregistré, pas de token) une exigence
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

        get_groups = getattr(handler, "get_action_permission_groups", None)
        groups: list[list[str]] = get_groups(action) if get_groups else []

        if required or groups:
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

            if groups and not any(set(group) <= granted for group in groups):
                logger.warning(
                    "action denied — aucun groupe de permissions satisfait",
                    plugin=plugin_name,
                    action=action,
                    groups=groups,
                )
                return {
                    "status": "error",
                    "code": "action_permission_denied",
                    "msg": (
                        f"Aucun groupe de permissions satisfait pour '{plugin_name}.{action}' "
                        f"(un seul suffit) : {groups}"
                    ),
                }

        return await next_call(plugin_name, action, payload, handler, **kwargs)
