"""
supervisor.py — Orchestrateur haut niveau du système de plugins.

Agrège : PluginLoader + PermissionEngine + rate limiter + retry + routing appels.
C'est lui qu'expose Xcore via xcore.plugins.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..context import KernelContext

from ..observability import get_logger
from ..permissions.engine import PermissionEngine
from ..sandbox.limits import RateLimiterRegistry
from .loader import PluginLoader
from .middlewares import (
    Middleware,
    MiddlewarePipeline,
    MiddlewareRegistry,
    PermissionMiddleware,
    RateLimitMiddleware,
    RetryMiddleware,
    TracingMiddleware,
)

logger = get_logger("xcore.runtime.supervisor")


class PluginSupervisor:
    """
    Interface haut niveau pour interagir avec les plugins.

    Usage:
        ctx = KernelContext(config, services, events, hooks, registry)
        supervisor = PluginSupervisor(ctx)
        await supervisor.boot()

        result = await supervisor.call("my_plugin", "ping", {})
        await supervisor.reload("my_plugin")
        status = supervisor.status()
        await supervisor.shutdown()
    """

    def __init__(self, ctx: "KernelContext") -> None:
        self._ctx = ctx
        self._config = ctx.config
        self._services = ctx.services
        self._events = ctx.events
        self._hooks = ctx.hooks
        self._registry = ctx.registry
        self._metrics = ctx.metrics
        self._tracer = ctx.tracer
        self._health = ctx.health

        self._rate = RateLimiterRegistry()
        self._permissions = PermissionEngine(events=self._events)

        self._loader: PluginLoader | None = None
        self._pipeline: MiddlewarePipeline | None = None

        self._middleware_registry = MiddlewareRegistry()
        self._setup_default_middlewares()

    def _setup_default_middlewares(self) -> None:
        """Registers default middleware factories."""
        self._middleware_registry.register(
            "tracing",
            lambda ctx: TracingMiddleware(
                ctx.get("tracer"), ctx.get("metrics"), ctx.get("events")
            ),
        )
        self._middleware_registry.register(
            "rate_limit", lambda ctx: RateLimitMiddleware(ctx.get("rate"))
        )
        self._middleware_registry.register(
            "permissions", lambda ctx: PermissionMiddleware(ctx.get("permissions"))
        )
        self._middleware_registry.register("retry", lambda _: RetryMiddleware())

    # supervisor.py — boot()

    async def boot(self) -> None:
        if self._events:
            self._events.subscribe(
                "plugin.*.services_registered", self._on_plugin_services_registered
            )

        self._loader = PluginLoader(
            ctx=self._ctx,
            caller=lambda name, action, payload, **kw: self.call(
                name, action, payload, **kw
            ),
            # tenant_id injecté à chaque appel via kwargs — voir _dispatch
        )

        # ── 1. Pipeline initialisée AVANT load_all ─────────────
        from .middlewares.ipc_auth import IPCAuthMiddleware

        tenancy_cfg = getattr(self._ctx.config, "tenancy", None)
        enforce_ipc = getattr(tenancy_cfg, "enforce_ipc", False)

        mw_context = {
            "tracer": self._tracer,
            "metrics": self._metrics,
            "events": self._events,
            "rate": self._rate,
            "permissions": self._permissions,
        }
        self._pipeline = self._middleware_registry.create_pipeline(
            names=["tracing", "rate_limit", "permissions", "retry"],
            context=mw_context,
            final_handler=self._dispatch,
        )
        # IPC auth en premier : bloque avant tout le reste
        self._pipeline.add_middleware(
            IPCAuthMiddleware(self._loader, enforce=enforce_ipc), first=True
        )

        # ── 2. KernelHandler enregistré AVANT load_all ─────────
        from ..sandbox.limits import RateLimitConfig
        from .kernel_handler import KernelHandler

        self._loader._handlers["xcore"] = KernelHandler(self._ctx, self)
        self._permissions.grant_all("xcore")
        self._rate.register("xcore", RateLimitConfig(calls=10_000, period_seconds=60))

        # ── 3. Chargement des plugins (peuvent appeler xcore.*) ─
        report = await self._loader.load_all()

        # ── 4. Enregistrement services noyau (inchangé) ─────────
        if self._registry:
            for name, svc in self._services.as_dict().items():
                try:
                    self._registry.register_core_service(name, svc)
                except Exception as e:
                    logger.warning(
                        "core service registration failed", service=name, error=str(e)
                    )

        logger.info(
            "plugins boot complete",
            loaded=len(report["loaded"]),
            failed=len(report["failed"]),
            skipped=len(report["skipped"]),
        )

        if self._events:
            await self._events.emit("xcore.plugins.booted", {"report": report})

        return self

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
                        "rate limit registered",
                        plugin=name,
                        calls=rl.calls,
                        period_s=rl.period_seconds,
                    )
            except Exception as e:
                logger.error(
                    "erreur enregistrement rate limit", plugin=name, erreur=str(e)
                )

    async def _on_plugin_services_registered(self, event) -> None:
        """Handler réactif appelé quand un plugin a enregistré ses services."""
        plugin_name = event.data.get("plugin")
        if not plugin_name:
            return

        logger.debug("reactive configuration triggered", plugin=plugin_name)

        # 1. Chargement des permissions
        self._load_permissions([plugin_name])

        # 2. Enregistrement des rate limits
        self._register_rate_limits([plugin_name])

        # 3. Enregistrement dans le registry si disponible
        if self._registry and self._loader:
            with contextlib.suppress(KeyError):
                self._registry.register(plugin_name, self._loader.get(plugin_name))

    def _load_permissions(self, plugin_names: list[str]) -> None:
        """Charge les policies de chaque plugin dans le PermissionEngine."""
        for name in plugin_names:
            try:
                handler = self._loader.get(name)
                manifest = getattr(handler, "manifest", None)
                raw_permissions = getattr(manifest, "permissions", None)
                self._permissions.load_from_manifest(name, raw_permissions)
                logger.debug("permissions loaded", plugin=name)
            except Exception as e:
                logger.error("permissions load error", plugin=name, error=str(e))
                # Fail-closed : si on ne peut pas charger, deny all
                self._permissions.load_from_manifest(name, None)

    # ── Appel ─────────────────────────────────────────────────

    async def call(
        self,
        plugin_name,
        action,
        payload,
        *,
        resource=None,
        caller=None,
        tenant_id: str = "default",
    ) -> dict:
        """
        Appelle une action sur un plugin via la pipeline de middlewares.
        caller=None     → appel HTTP direct (non IPC)
        caller="crm"    → appel IPC depuis le plugin "crm"
        tenant_id       → identifiant du tenant courant
        """
        if self._loader is None or self._pipeline is None:
            return self._err("Supervisor non démarré", "not_ready")

        if not self._loader.has(plugin_name):
            return self._err(f"Plugin '{plugin_name}' introuvable", "not_found")

        handler = self._loader.get(plugin_name)

        return await self._pipeline.execute(
            plugin_name,
            action,
            payload,
            handler=handler,
            resource=resource,
            caller=caller,
            tenant_id=tenant_id,
        )

    async def _dispatch(
        self, plugin_name: str, action: str, payload: dict, handler, **kwargs
    ) -> dict:
        """Dernière étape du pipeline : exécution réelle."""
        from ..tenancy.services import _current_tenant_id

        if handler is None:
            handler = self._loader.get(plugin_name)

        tenancy = (
            self._ctx.config.tenancy if hasattr(self._ctx.config, "tenancy") else None
        )
        tenant_id: str = kwargs.get(
            "tenant_id", getattr(tenancy, "default_tenant", "default")
        )

        # Les services du plugin sont déjà wrappés (TenantAwareDB/Cache) au chargement.
        # On positionne uniquement le ContextVar pour que les wrappers lisent le bon tenant.
        # Chaque tâche asyncio a sa propre valeur — pas de mutation d'état partagé.
        if tenancy is not None and tenancy.enabled:
            token = _current_tenant_id.set(tenant_id)
            try:
                return await handler.call(action, payload)
            finally:
                _current_tenant_id.reset(token)

        return await handler.call(action, payload)

    # ── Gestion dynamique ─────────────────────────────────────

    def register_middleware(self, middleware: Middleware, first: bool = False) -> None:
        """
        Enregistre dynamiquement un middleware dans la pipeline.

        Si first=True, le middleware est placé en début de chaîne
        (exécuté avant les autres).
        """
        if self._pipeline is None:
            raise RuntimeError(
                "Le pipeline n'est pas encore initialisé. Appelez boot() d'abord."
            )
        self._pipeline.add_middleware(middleware, first=first)
        logger.info(
            "middleware registered dynamically",
            middleware=middleware.__class__.__name__,
        )

    def get_active_middlewares(self) -> list[Middleware]:
        """Retourne la liste des middlewares actifs dans la pipeline."""
        return [] if self._pipeline is None else self._pipeline.get_middlewares()

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

    def collect_app_state(self) -> list[Any]:
        return self._loader.collect_app_state() if self._loader else []

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
