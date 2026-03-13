"""
supervisor.py — Orchestrateur haut niveau du système de plugins.

Agrège : PluginLoader + PermissionEngine + rate limiter + retry + routing appels.
C'est lui qu'expose Xcore via xcore.plugins.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...configurations.sections import PluginConfig

from ..permissions.engine import PermissionDenied, PermissionEngine
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
        self._permissions = PermissionEngine(events=events)

        self._loader: PluginLoader | None = None

    async def boot(self) -> None:
        """Instancie le loader et charge tous les plugins."""
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

        # Chargement des permissions pour chaque plugin chargé
        self._load_permissions(report["loaded"])

        # Enregistrement des rate limits
        self._register_rate_limits(report["loaded"])

        # Enregistrement dans le registry si disponible
        if self._registry:
            for name in report["loaded"]:
                self._registry.register(name, self._loader.get(name))

        if self._events:
            await self._events.emit("xcore.plugins.booted", {"report": report})

    def _register_rate_limits(self, plugin_names: list[str]) -> None:
        """Enregistre les rate limits de chaque plugin dans le RateLimiterRegistry."""
        from ..sandbox.limits import RateLimitConfig as LimitsRateLimitConfig

        for name in plugin_names:
            try:
                handler = self._loader.get(name)
                manifest = getattr(handler, "manifest", None)
                if manifest and hasattr(manifest, "resources"):
                    rl = manifest.resources.rate_limit
                    config = LimitsRateLimitConfig(
                        calls=rl.calls,
                        period_seconds=rl.period_seconds,
                    )
                    self._rate.register(name, config)
                    logger.debug(
                        f"[{name}] Rate limit : {rl.calls}/{rl.period_seconds}s"
                    )
            except Exception as e:
                logger.error(f"[{name}] Erreur enregistrement rate limit : {e}")

    def _load_permissions(self, plugin_names: list[str]) -> None:
        """Charge les policies de chaque plugin dans le PermissionEngine."""
        for name in plugin_names:
            try:
                handler = self._loader.get(name)
                manifest = getattr(handler, "manifest", None)
                raw_permissions = getattr(manifest, "permissions", None)
                self._permissions.load_from_manifest(name, raw_permissions)
                logger.debug(f"[{name}] Permissions chargées")
            except Exception as e:
                logger.error(f"[{name}] Erreur chargement permissions : {e}")
                # Fail-closed : si on ne peut pas charger, deny all
                self._permissions.load_from_manifest(name, None)

    # ── Appel ─────────────────────────────────────────────────

    async def call(
        self,
        plugin_name: str,
        action: str,
        payload: dict,
        *,
        resource: str | None = None,
    ) -> dict:
        """
        Route un appel vers le plugin approprié.

        Applique dans l'ordre :
          1. Rate limiting
          2. Vérification permissions (resource = action par défaut)
          3. Retry + gestion d'erreur standardisée

        Args:
            plugin_name: nom du plugin cible
            action: action à exécuter
            payload: données de l'appel
            resource: ressource ciblée pour la vérification de permission.
                      Si absent, utilise "action.<action>" comme ressource.
        """
        if self._loader is None:
            return self._err("Supervisor non démarré", "not_ready")

        # 1. Rate limiting
        try:
            await self._rate.check(plugin_name)
        except RateLimitExceeded as e:
            return self._err(str(e), "rate_limit_exceeded")

        # 2. Plugin existe ?
        if not self._loader.has(plugin_name):
            return self._err(f"Plugin '{plugin_name}' introuvable", "not_found")

        # 3. Vérification des permissions
        # La ressource par défaut est "action.<action>" ce qui permet aux plugins
        # de déclarer : resource: "action.*" effect: allow
        effective_resource = resource or f"action.{action}"
        try:
            self._permissions.check(plugin_name, effective_resource, "execute")
        except PermissionDenied as e:
            logger.warning(f"[{plugin_name}] Appel refusé : {e}")
            return self._err(str(e), "permission_denied")

        # 4. Appel avec retry
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
            self._load_permissions([plugin_name])
            self._register_rate_limits([plugin_name])

    async def reload(self, plugin_name: str) -> None:
        if self._loader:
            await self._loader.reload(plugin_name)
            # Rechargement des permissions après reload (le manifeste peut avoir changé)
            self._load_permissions([plugin_name])
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
        return self._loader.collect_plugin_routers() if self._loader else []

    def permissions_status(self) -> dict:
        """Expose l'état du moteur de permissions (audit log + policies)."""
        return self._permissions.status()

    def permissions_audit(
        self, plugin_name: str | None = None, limit: int = 100
    ) -> list[dict]:
        """Retourne le journal d'audit des permissions."""
        return self._permissions.audit_log(plugin_name, limit)

    # ── Arrêt ─────────────────────────────────────────────────

    async def shutdown(self) -> None:
        if self._loader:
            await self._loader.shutdown()

    # ── Helpers ───────────────────────────────────────────────

    @staticmethod
    def _err(msg: str, code: str) -> dict:
        return {"status": "error", "msg": msg, "code": code}
