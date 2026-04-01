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
from .middleware import Middleware, MiddlewarePipeline
from .middlewares.retry import RetryMiddleware
from .middlewares.tracing import TracingMiddleware

logger = logging.getLogger("xcore.runtime.supervisor")


class RateLimitMiddleware(Middleware):
    def __init__(self, rate):
        self._rate = rate

    async def __call__(self, plugin_name, action, payload, next_call, *, handler=None, **kwargs):
        try:
            self._rate.check(plugin_name)
        except RateLimitExceeded as e:
            return {"status": "error", "msg": str(e), "code": "rate_limit_exceeded"}
        return await next_call(plugin_name, action, payload, **kwargs)


class PermissionMiddleware(Middleware):
    def __init__(self, permissions):
        self._permissions = permissions

    async def __call__(self, plugin_name, action, payload, next_call, *, handler=None, **kwargs):
        resource = kwargs.get("resource") or f"{action}"
        try:
            self._permissions.check(plugin_name, resource, "execute")
        except PermissionDenied as e:
            logger.warning(f"[{plugin_name}] Appel refusé : {e}")
            return {"status": "error", "msg": str(e), "code": "permission_denied"}
        return await next_call(plugin_name, action, payload, **kwargs)


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
        metrics = None,
        tracer = None,
        health = None,
    ) -> None:
        self._config = config
        self._services = services
        self._events = events
        self._hooks = hooks
        self._registry = registry
        self._rate = RateLimiterRegistry()
        self._permissions = PermissionEngine(events=events)

        self._loader: PluginLoader | None = None
        self._pipeline: MiddlewarePipeline | None = None

        self._metrics = metrics
        self._tracer = tracer
        self._health = health

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
            registry=self._registry,
            caller=lambda name, action, payload: self.call(name, action, payload),
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

        # Initialisation du pipeline de middlewares
        # L'ordre compte : Tracing → RateLimit → Permissions → Retry → Final
        self._pipeline = MiddlewarePipeline(
            middlewares=[
                TracingMiddleware(self._tracer, self._metrics),
                RateLimitMiddleware(self._rate),
                PermissionMiddleware(self._permissions),
                RetryMiddleware(),
            ],
            final_handler=self._dispatch,
        )

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

    async def call(self, plugin_name, action, payload, *, resource=None) -> dict:
        """
        Appelle une action sur un plugin via la pipeline de middlewares.
        """
        if self._loader is None or self._pipeline is None:
            return self._err("Supervisor non démarré", "not_ready")

        if not self._loader.has(plugin_name):
            return self._err(f"Plugin '{plugin_name}' introuvable", "not_found")

        handler = self._loader.get(plugin_name)

        # Exécution de la pipeline (inclut tracing, retry, rate limit et permissions)
        return await self._pipeline.execute(
            plugin_name,
            action,
            payload,
            handler=handler,
            resource=resource
        )

    async def _dispatch(
        self, plugin_name: str, action: str, payload: dict, *, handler=None, **kwargs
    ) -> dict:
        """Dernière étape du pipeline : exécution réelle."""
        if handler is None:
            handler = self._loader.get(plugin_name)
        return await handler.call(action, payload)

    # ── Gestion dynamique ─────────────────────────────────────

    def register_middleware(self, middleware: Middleware, first: bool = False) -> None:
        """
        Enregistre dynamiquement un middleware dans la pipeline.

        Si first=True, le middleware est placé en début de chaîne
        (exécuté avant les autres).
        """
        if self._pipeline is None:
            raise RuntimeError("Le pipeline n'est pas encore initialisé. Appelez boot() d'abord.")
        self._pipeline.add_middleware(middleware, first=first)
        logger.info(f"Middleware {middleware.__class__.__name__} enregistré dynamiquement.")

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
