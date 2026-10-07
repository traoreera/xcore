"""
auth_resolver.py — Middleware qui résout le principal (utilisateur) de l'appel
IPC en cours via l'AuthBackend enregistré par le plugin auth (kernel/api/auth.py).
"""

from __future__ import annotations

from ..api.auth import get_auth_backend
from ..observability import get_logger
from .middleware import Middleware

logger = get_logger("xcore.runtime.middlewares.auth_resolver")


class AuthResolverMiddleware(Middleware):
    """
    Résout `principal` (AuthPayload) pour l'appel courant :
      - déjà fourni (propagé par TrustedBase.call_plugin() sur un appel IPC
        imbriqué, depuis le principal de l'appel parent) → transmis tel quel,
        pas de nouvelle résolution.
      - sinon, si `token=` est fourni (extrait de la requête HTTP entrante par
        le router via AuthBackend.extract_token()) → résolu ici en contactant
        l'AuthBackend enregistré (decode_token).
      - sinon, ou si aucun backend n'est enregistré → principal=None.

    Best-effort : ne lève jamais et ne bloque aucun appel. L'enforcement
    (401/403) reste la responsabilité de RBACChecker (routes HTTP) ou d'un
    futur middleware de permissions par action qui consommerait `principal`.
    """

    async def __call__(
        self, plugin_name, action, payload, next_call, handler, **kwargs
    ):
        token = kwargs.pop("token", None)
        principal = kwargs.get("principal")

        if principal is None and token is not None:
            backend = get_auth_backend()
            if backend is not None:
                try:
                    principal = await backend.decode_token(token)
                except Exception as e:
                    logger.warning(
                        "échec résolution du principal",
                        plugin=plugin_name,
                        error=str(e),
                    )
                    principal = None

        kwargs["principal"] = principal
        return await next_call(plugin_name, action, payload, handler, **kwargs)
