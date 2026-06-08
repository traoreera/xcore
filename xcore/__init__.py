"""
xcore v2 — Framework modulaire plugin-first avec intégration de services.

Quickstart:
    ```python
        from xcore import Xcore

    app = Xcore()
    await app.boot()

    # Accès au plugin manager
    result = await app.plugins.call("my_plugin", "my_action", {...})

    # Accès aux services intégrés
    db    = app.services.get("db")
    cache = app.services.get("cache")
    ```
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

from .__version__ import __version__
from .configurations.sections import MiddlewareConfig
from .kernel.api import (
    AuthBackend,
    AuthPayload,
    get_auth_backend,
    get_current_user,
    register_auth_backend,
    unregister_auth_backend,
)
from .kernel.api.contract import BasePlugin, TrustedBase
from .kernel.api.middleware import Middlewares
from .kernel.events.bus import EventBus
from .kernel.events.hooks import HookManager
from .kernel.observability import (
    HealthChecker,
    MetricsRegistry,
    Tracer,
    configure_logging,
    create_metrics_registry,
    get_logger,
)
from .kernel.runtime.lifecycle import LifecycleManager
from .kernel.runtime.loader import PluginLoader
from .kernel.runtime.supervisor import PluginSupervisor
from .kernel.security.signature import sign_plugin, verify_plugin
from .registry.index import PluginRegistry
from .services import ServiceContainer

__all__ = [
    "MiddlewareConfig",
    "MetricsRegistry",
    "__version__",
    "Xcore",
    "PluginLoader",
    "LifecycleManager",
    "PluginSupervisor",
    "EventBus",
    "HookManager",
    "BasePlugin",
    "TrustedBase",
    "sign_plugin",
    "verify_plugin",
    "ServiceContainer",
    "PluginRegistry",
    "get_logger",
    "AuthBackend",
    "AuthPayload",
    "get_auth_backend",
    "get_current_user",
    "register_auth_backend",
    "unregister_auth_backend",
]


class Xcore:
    """
    Point d'entrée unique du framework v2.

    Orchestre :
      - Le kernel (runtime, sandbox, permissions, events)
      - Les services intégrés (BDD, cache, scheduler)
      - Le registry de plugins
      - L'observabilité (logs, métriques, traces, health)

    Usage FastAPI:
        from contextlib import asynccontextmanager
        from fastapi import FastAPI
        from xcore import Xcore

        xcore = Xcore(config_path="xcore.yaml")

        @asynccontextmanager
        async def lifespan(app):
            await xcore.boot(app)
            yield
            await xcore.shutdown()

        app = FastAPI(lifespan=lifespan)

    Usage standalone:
        xcore = Xcore()
        await xcore.boot()
        result = await xcore.plugins.call("my_plugin", "ping", {})
        await xcore.shutdown()
    """

    def __init__(self, config_path: str | None = None):
        from .configurations.loader import ConfigLoader

        self._config = ConfigLoader.load(config_path)
        self._booted = False

        # Sous-systèmes — instanciés dans __init__ pour les décorateurs
        self.events = EventBus()
        self.hooks = HookManager()

        # Sous-systèmes instanciés lazily à boot()
        self.services: ServiceContainer | None = None
        self.plugins: PluginSupervisor | None = None
        self.registry: PluginRegistry | None = None

        self._logger = get_logger("xcore")

    def setup(self, app: "FastAPI") -> "Xcore":
        """
        Enregistre les middlewares sur l'app FastAPI.
        Doit être appelé AVANT le démarrage (avant uvicorn / lifespan).

        Usage :
            xcore = Xcore()
            app = FastAPI(lifespan=lifespan)
            xcore.setup(app)          # ← ici, avant que l'app démarre
        """

        def _lazy_service(name: str):
            """Résout le service au moment de la requête, pas à l'enregistrement."""
            if self.services is None:
                raise RuntimeError(f"Service '{name}' requested before boot()")
            return self.services.get(name)

        from .kernel.tenancy import TenantMiddleware

        # TenantMiddleware toujours présent — si disabled, injecte juste default_tenant
        app.add_middleware(TenantMiddleware, config=self._config.tenancy)

        Middlewares(
            config=self._config.middleware,
            prototypes=_lazy_service,
            event_bus=self.events,
        ).configure(app, self._logger)
        return self

    async def boot(self, app=None) -> "Xcore":
        """Démarre tous les sous-systèmes dans le bon ordre."""

        if self._booted:
            return self

        configure_logging(self._config.observability.logging)
        self._logger.info(f"━━━ xcore v{__version__} starting ━━━")

        # 0. Validation clés secrètes en production

        self._validate_secret_keys()

        # etape intermediare
        # configuration de l'observabilite
        self.metrics = create_metrics_registry(self._config.observability.metrics)
        self.tracer = Tracer(self._config.observability.tracing.service_name)
        self.health = HealthChecker()

        # 1. Services (BDD, cache, scheduler)
        from .services import ServiceContainer

        self.services = ServiceContainer(self._config.services)
        self.services.load_default_providers()
        await self.services.init()

        # Enregistrement auto des health checks pour chaque service
        for svc_name, svc in self.services.as_dict().items():
            if hasattr(svc, "health_check"):
                # Capture par valeur
                _svc = svc
                _name = svc_name

                @self.health.register(_name)
                async def _check(_s=_svc):
                    return await _s.health_check()

        # 2. Registry des plugins
        self.registry = PluginRegistry(self._config)

        # 4. Kernel Context & Plugin supervisor (runtime + sandbox)
        from .kernel.context import KernelContext

        ctx = KernelContext(
            config=self._config.plugins,
            services=self.services,
            events=self.events,
            hooks=self.hooks,
            registry=self.registry,
            metrics=self.metrics,
            tracer=self.tracer,
            health=self.health,
        )
        self.plugins = PluginSupervisor(ctx)

        await self.plugins.boot()
        self.plugins_lists = self.plugins.list_plugins()

        # 5. Attache le router FastAPI si une app est fournie
        if app is not None:
            self._attach_router(
                app,
                prefix=self._config.app.plugin_prefix,
                tags=self._config.app.plugin_tags,
            )

        self._booted = True
        self._logger.info("━━━ xcore ready ━━━")
        return self

    async def shutdown(self) -> None:
        if not self._booted:
            return
        self._logger.info("Shutting down xcore...")
        if self.plugins:
            await self.plugins.shutdown()
        if self.services:
            await self.services.shutdown()
        self._booted = False
        self._logger.info("xcore stopped.")

    def _attach_router(
        self,
        app,
        prefix: str | None = None,
        tags: list[str] | None = None,
    ) -> None:
        from .kernel.api.router import build_router

        # 1. Router système xcore (status, reload, load, unload)
        system_router = build_router(
            supervisor=self.plugins,
            secret_key=self._config.app.secret_key,
            server_key=self._config.app.server_key,
            prefix=self._config.app.plugin_prefix,
            health_checker=self.health,  # ← nouveau
            metrics_registry=self.metrics,  # ← nouveau
            tags=(self._config.app.plugin_tags or []) + (tags or []),
        )
        app.include_router(system_router)

        # 2. Routers custom des plugins Trusted (get_router())
        plugin_routers = self.plugins.collect_plugin_routers()
        for plugin_name, plugin_router in plugin_routers:
            # Monte sous /plugins/<plugin_name>/ + le prefix du router du plugin
            prefixed_router = plugin_router
            if not getattr(plugin_router, "prefix", "").startswith("/plugins/"):
                # Préfixe automatique si le plugin n'a pas déjà /plugins/...
                from fastapi import APIRouter

                wrapper = APIRouter(
                    prefix=f"{prefix}/{plugin_name}",
                    tags=(self._config.app.plugin_tags or []) + (tags or []),
                )
                wrapper.include_router(plugin_router)
                prefixed_router = wrapper
            app.include_router(prefixed_router)
            n_routes = len(getattr(plugin_router, "routes", []))
            self._logger.info(
                f"[{plugin_name}] 🌐 {n_routes} route(s) mounted sous {wrapper.prefix}"
            )

        for middleware in self.plugins.collect_app_state():
            if middleware:
                states = middleware.get("states")
                for key, value in states.items():
                    app.state.__setattr__(
                        key=f"{middleware['name']}_{key}", value=value
                    )
                    self._logger.info(
                        f"{middleware['name']}📦 state {middleware['name']}_{key} "
                        "updated"
                    )

        # Endpoint /metrics Prometheus (seulement si backend=prometheus)
        if (
            getattr(self._config.observability.metrics, "backend", "memory")
            == "prometheus"
        ):
            try:
                from fastapi import APIRouter as _AR
                from fastapi import Response
                from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

                _metrics_router = _AR()

                @_metrics_router.get("/metrics")
                async def prometheus_metrics():
                    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

                app.include_router(_metrics_router)
            except ImportError:
                pass

        app.openapi_schema = None  # force la regen du schéma OpenAPI

    def _validate_secret_keys(self) -> None:
        """
        Bloque le démarrage en production si les clés secrètes sont celles
        par défaut.
        """
        if self._config.app.env != "production":
            return
        default_key = b"change-me-in-production"
        if (
            self._config.app.secret_key == default_key
            or self._config.app.server_key == default_key
        ):
            raise RuntimeError(
                "SECRET_KEY default detected in production! "
                "Configure app.secret_key in your xcore.yaml"
            )
        if self._config.plugins.secret_key == default_key:
            raise RuntimeError(
                "PLUGIN_SECRET_KEY default detected in production! "
                "Configure plugins.secret_key in your xcore.yaml"
            )

    def __repr__(self) -> str:
        status = "booted" if self._booted else "idle"
        return f"<Xcore [{status}] v{__version__}>"
