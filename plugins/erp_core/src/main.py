"""
erp_core/src/main.py
─────────────────────
Point d'entrée du plugin erp_core.

⚠️  Règle d'or pour les plugins Trusted :
Ne jamais importer depuis xcore directement.
Le runner injecte TrustedBase via services — le plugin n'a pas besoin
de savoir qu'il tourne dans xcore.

Tous les imports sont absolus (pas de "from .models") car src/ est
ajouté au sys.path par le TrustedRunner avant l'import.
"""

from __future__ import annotations

import logging
from typing import Any

# ── Imports absolus depuis src/ ───────────────────────────────────
import core_models as models_module
import core_router as router_module
from core_services import CoreService

logger = logging.getLogger("erp_core")


# ══════════════════════════════════════════════════════════════════
# Helpers réponses — copiés localement pour éviter toute dépendance
# vers xcore (le plugin doit être autonome à l'import)
# ══════════════════════════════════════════════════════════════════


def _ok(data: dict | None = None, **kwargs) -> dict:
    return {"status": "ok", **(data or {}), **kwargs}


def _error(msg: str, code: str | None = None, **kwargs) -> dict:
    r = {"status": "error", "msg": msg}
    if code:
        r["code"] = code
    r.update(kwargs)
    return r


# ══════════════════════════════════════════════════════════════════
# Plugin
# ══════════════════════════════════════════════════════════════════


class Plugin:
    """
    Plugin erp_core — respecte le contrat BasePlugin par duck typing.
    Pas besoin d'hériter de TrustedBase : le PluginManager injecte
    les services via le constructeur si la classe en accepte.
    """

    def __init__(self, services: dict[str, Any] | None = None) -> None:
        self._services: dict[str, Any] = services or {}

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
        logger.info("🔧 erp_core — initialisation...")

        db_factory = self.get_service("db")
        shared_base = self.get_service("base")
        engine = self.get_service("engine")

        # Enregistre les modèles sur le Base partagé
        for table in models_module.Base.metadata.tables.values():
            if table.name not in shared_base.metadata.tables:
                table.to_metadata(shared_base.metadata)

        # Crée les tables (idempotent)
        shared_base.metadata.create_all(bind=engine, checkfirst=True)
        logger.info("✅ Tables core_* créées / vérifiées")

        # Injecte la DB dans le router FastAPI
        router_module._db_dependency = db_factory
        logger.info("✅ DB injectée dans erp_core router")

        # Expose CoreService aux autres plugins
        self._services["core"] = lambda: CoreService(next(db_factory()))
        logger.info("✅ CoreService exposé via service 'core'")

        logger.info("🚀 erp_core chargé avec succès")

    async def on_unload(self) -> None:
        logger.info("erp_core — déchargement")

    async def on_reload(self) -> None:
        logger.info("erp_core — rechargement")
        await self.on_load()

    # ──────────────────────────────────────────
    # Router — lu par PluginManager._attach_routes()
    # ──────────────────────────────────────────

    @property
    def router(self):
        return router_module.router

    # ──────────────────────────────────────────
    # handle() — API interne inter-plugins
    # ──────────────────────────────────────────

    async def handle(self, action: str, payload: dict) -> dict:
        db_factory = self.get_service("db")
        try:
            db = next(db_factory())
            svc = CoreService(db)
            result = await self._dispatch(action, payload, svc)
            db.close()
            return result
        except Exception as e:
            logger.error(f"erp_core.handle({action}) → {e}")
            return _error(str(e), code="internal_error")

    async def _dispatch(self, action: str, payload: dict, svc: CoreService) -> dict:

        if action == "ping":
            return _ok({"msg": "erp_core is alive"})

        # ── Company ──
        if action == "get_company":
            r = svc.get_company(payload["company_id"])
            return (
                _ok(r.model_dump())
                if r
                else _error("Société introuvable", code="not_found")
            )

        if action == "list_companies":
            return _ok({"companies": [c.model_dump() for c in svc.list_companies()]})

        if action == "create_company":
            from schemas import CompanyCreate

            r = svc.create_company(CompanyCreate(**payload))
            return _ok(r.model_dump())

        # ── User ──
        if action == "get_user":
            r = svc.get_user(payload["user_id"])
            return (
                _ok(r.model_dump())
                if r
                else _error("Utilisateur introuvable", code="not_found")
            )

        if action == "get_user_by_email":
            r = svc.get_user_by_email(payload["email"])
            return (
                _ok(r.model_dump())
                if r
                else _error("Utilisateur introuvable", code="not_found")
            )

        if action == "list_users":
            return _ok(
                {
                    "users": [
                        u.model_dump() for u in svc.list_users(payload["company_id"])
                    ]
                }
            )

        if action == "verify_password":
            r = svc.verify_password(payload["email"], payload["password"])
            return (
                _ok(r.model_dump())
                if r
                else _error("Credentials invalides", code="auth_failed")
            )

        if action == "create_user":
            from schemas import UserCreate

            r = svc.create_user(UserCreate(**payload))
            return _ok(r.model_dump())

        # ── Currency ──
        if action == "list_currencies":
            return _ok(
                {
                    "currencies": [
                        c.model_dump()
                        for c in svc.list_currencies(payload["company_id"])
                    ]
                }
            )

        if action == "get_exchange_rate":
            try:
                rate = svc.get_exchange_rate(
                    payload["company_id"], payload["from_code"], payload["to_code"]
                )
                return _ok({"rate": rate})
            except ValueError as e:
                return _error(str(e), code="invalid_currency")

        # ── Country ──
        if action == "list_countries":
            return _ok({"countries": svc.list_countries()})

        if action == "get_country":
            r = svc.get_country(payload["iso2"])
            return (
                _ok(r)
                if r
                else _error(f"Pays '{payload['iso2']}' introuvable", code="not_found")
            )

        return _error(f"Action inconnue : '{action}'", code="unknown_action")
