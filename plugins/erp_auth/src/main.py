"""
erp_auth/src/main.py
─────────────────────
Plugin d'authentification ERP.

Ce plugin expose deux choses aux autres plugins :
  - service "get_current_user" → dépendance FastAPI pour protéger les routes
  - service "require_roles"    → factory de dépendance pour contrôle par rôle

Usage dans erp_crm (ou n'importe quel autre plugin) :
    async def on_load(self):
        self._get_current_user = self.get_service("get_current_user")
        self._require_roles    = self.get_service("require_roles")

    # Dans son router.py :
    get_user_dep = None   # injecté par Plugin.on_load()

    @router.get("/contacts")
    def list_contacts(current = Depends(get_user_dep)):
        ...
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict

import auth_models as models_module
import auth_router as router_module
from auth_services import AuthService

logger = logging.getLogger("erp_auth")

# Clé secrète JWT par défaut — à TOUJOURS surcharger via env en production


class EnviroVarialble(TypedDict):
    AUTH_JWT_SECRET: str


_DEFAULT_SECRET = b"erp-auth-secret-change-me-in-production"


class Plugin:
    """Plugin erp_auth — authentification centralisée pour tout l'ERP."""

    def __init__(self, services: dict[str, Any] | None = None) -> None:
        self._services: dict[str, Any] = services or {}
        self.env: EnviroVarialble

    def get_service(self, name: str) -> Any:
        if name not in self._services:
            raise KeyError(
                f"Service '{name}' non disponible. "
                f"Disponibles : {list(self._services.keys())}"
            )
        return self._services[name]

    # ──────────────────────────────────────────
    # Cycle de vie
    # ──────────────────────────────────────────

    async def on_load(self) -> None:
        logger.info("🔐 erp_auth — initialisation...")

        db_factory = self.get_service("db")
        shared_base = self.get_service("base")
        engine = self.get_service("engine")

        # Clé secrète JWT — depuis l'env ou la config
        secret = self.env["AUTH_JWT_SECRET"]
        if secret == _DEFAULT_SECRET:
            logger.warning(
                "⚠️  JWT_SECRET par défaut utilisé — à changer en production !"
            )

        # ── 1. Tables ──
        for table in models_module.LocalBase.metadata.tables.values():
            if table.name not in shared_base.metadata.tables:
                table.to_metadata(shared_base.metadata)
        shared_base.metadata.create_all(bind=engine, checkfirst=True)
        logger.info("✅ Table auth_refresh_tokens créée / vérifiée")

        # ── 2. Injecte DB + secret + CoreService dans le router ──
        router_module._db_dependency = db_factory
        router_module._auth_secret = secret
        # router_module._core_service_fn = self.get_service("core")
        logger.info("✅ DB, secret et CoreService injectés dans erp_auth router")

        # ── 3. Expose les dépendances FastAPI aux autres plugins ──
        # Les autres plugins n'importent RIEN depuis erp_auth.
        # Ils récupèrent juste une référence à la fonction Depends().

        self._services["get_current_user"] = router_module.get_current_user
        self._services["require_roles"] = router_module.require_roles
        self._services["auth"] = lambda: AuthService(next(db_factory()), secret)

        logger.info("✅ Services 'get_current_user' et 'require_roles' exposés")
        logger.info("🚀 erp_auth chargé avec succès")

    async def on_unload(self) -> None:
        logger.info("erp_auth — déchargement")

    async def on_reload(self) -> None:
        await self.on_load()

    @property
    def router(self):
        return router_module.router

    async def env_variable(self, manifest: dict) -> None:
        self.env = manifest

    # ──────────────────────────────────────────
    # handle() — API interne
    # ──────────────────────────────────────────

    async def handle(self, action: str, payload: dict) -> dict:
        db_factory = self.get_service("db")
        secret = router_module._auth_secret or _DEFAULT_SECRET

        try:
            db = next(db_factory())
            svc = AuthService(db, secret)
            return await self._dispatch(action, payload, svc)
        except Exception as e:
            logger.error(f"erp_auth.handle({action}) → {e}")
            return {"status": "error", "msg": str(e), "code": "internal_error"}

    async def _dispatch(self, action: str, payload: dict, svc: AuthService) -> dict:

        if action == "ping":
            return {"status": "ok", "msg": "erp_auth is alive"}

        if action == "verify_token":
            identity = svc.verify_access_token(payload["token"])
            if identity is None:
                return {
                    "status": "error",
                    "msg": "Token invalide",
                    "code": "unauthorized",
                }
            return {"status": "ok", **identity.model_dump()}

        if action == "logout_all":
            count = svc.logout_all(payload["user_id"])
            return {"status": "ok", "revoked": count}

        return {
            "status": "error",
            "msg": f"Action inconnue : '{action}'",
            "code": "unknown_action",
        }
