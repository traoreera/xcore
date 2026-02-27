"""
supervisor.py — Orchestrateur haut niveau du système de plugins.

Agrège : PluginLoader + rate limiter + retry + routing appels.
C'est lui qu'expose Xcore via xcore.plugins.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...configurations.sections import PluginConfig

from ..sandbox.limits import RateLimiterRegistry, RateLimitExceeded
from .loader import PluginLoader

logger = logging.getLogger("xcore.runtime.supervisor")


class PluginSupervisor:
    """
    Interface haut niveau pour interagir avec les plugins.

    Usage:
        supervisor = PluginSupervisor(config, services, events, hooks, registry)
        await supervisor.boot()

        result = await supervisor.call("my_plugin", "ping", {})
        await supervisor.reload("my_plugin")
        status = supervisor.status()
        await supervisor.shutdown()
    """

    def __init__(
        self,
        config: "PluginConfig",
        services,  # ServiceContainer
        events=None,
        hooks=None,
        registry=None,
    ) -> None:
        self._config = config
        self._services = services
        self._events = events
        self._hooks = hooks
        self._registry = registry
        self._rate = RateLimiterRegistry()

        self._loader: PluginLoader | None = None

    async def boot(self) -> None:
        """Instancie le loader et charge tous les plugins."""
        # Le container de services est un dict partagé par référence
        svc_dict = (
            self._services.as_dict() if hasattr(self._services, "as_dict") else {}
        )

        self._loader = PluginLoader(
            config=self._config,
            services=svc_dict,
            events=self._events,
            hooks=self._hooks,
        )
        report = await self._loader.load_all()
        logger.info(
            f"Boot plugins — chargés: {len(report['loaded'])}, "
            f"échecs: {len(report['failed'])}, ignorés: {len(report['skipped'])}"
        )

        # Enregistrement dans le registry si disponible
        if self._registry:
            for name in report["loaded"]:
                self._registry.register(name, self._loader.get(name))

        # Émettre l'événement de démarrage
        if self._events:
            await self._events.emit("xcore.plugins.booted", {"report": report})

    # ── Appel ─────────────────────────────────────────────────

    async def call(self, plugin_name: str, action: str, payload: dict) -> dict:
        """
        Route un appel vers le plugin approprié.

        Applique :
          - Rate limiting
          - Retry (selon manifest)
          - Gestion d'erreur standardisée
        """
        if self._loader is None:
            return self._err("Supervisor non démarré", "not_ready")

        try:
            await self._rate.check(plugin_name)
        except RateLimitExceeded as e:
            return self._err(str(e), "rate_limit_exceeded")

        if not self._loader.has(plugin_name):
            return self._err(f"Plugin '{plugin_name}' introuvable", "not_found")

        handler = self._loader.get(plugin_name)
        return await self._call_with_retry(plugin_name, handler, action, payload)

    async def _call_with_retry(
        self, name: str, handler, action: str, payload: dict
    ) -> dict:
        manifest = getattr(handler, "manifest", None)
        retry_cfg = getattr(manifest, "runtime", None)
        max_attempts = (
            getattr(getattr(retry_cfg, "retry", None), "max_attempts", 1)
            if retry_cfg
            else 1
        )
        backoff = (
            getattr(getattr(retry_cfg, "retry", None), "backoff_seconds", 0.0)
            if retry_cfg
            else 0.0
        )

        last_err = None
        for attempt in range(1, max_attempts + 1):
            try:
                return await handler.call(action, payload)
            except Exception as e:
                last_err = e
                if attempt < max_attempts:
                    logger.warning(
                        f"[{name}] Tentative {attempt} échouée, retry dans {backoff}s"
                    )
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 60.0)

        logger.error(f"[{name}] Toutes les tentatives échouées : {last_err}")
        return self._err(str(last_err), "all_retries_failed")

    # ── Gestion dynamique ─────────────────────────────────────

    async def load(self, plugin_name: str) -> None:
        if self._loader:
            await self._loader.load(plugin_name)

    async def reload(self, plugin_name: str) -> None:
        if self._loader:
            await self._loader.reload(plugin_name)
            if self._events:
                await self._events.emit(f"plugin.{plugin_name}.reloaded", {})

    async def unload(self, plugin_name: str) -> None:
        if self._loader:
            await self._loader.unload(plugin_name)
            if self._events:
                await self._events.emit(f"plugin.{plugin_name}.unloaded", {})

    # ── Observabilité ─────────────────────────────────────────

    def status(self) -> dict:
        if self._loader is None:
            return {"plugins": [], "count": 0}
        items = self._loader.status()
        return {"plugins": items, "count": len(items)}

    def list_plugins(self) -> list[str]:
        return self._loader.all_names() if self._loader else []

    def collect_plugin_routers(self) -> list[tuple[str, Any]]:
        """
        Délègue au loader la collecte des APIRouter exposés par les plugins.
        Appelé par Xcore._attach_router() après le boot.
        """
        return self._loader.collect_plugin_routers() if self._loader else []

    # ── Arrêt ─────────────────────────────────────────────────

    async def shutdown(self) -> None:
        if self._loader:
            await self._loader.shutdown()

    # ── Helpers ───────────────────────────────────────────────

    @staticmethod
    def _err(msg: str, code: str) -> dict:
        return {"status": "error", "msg": msg, "code": code}
