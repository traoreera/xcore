"""
xcore v2 — Framework modulaire plugin-first avec intégration de services.
"""

from typing import Any
from .__version__ import __version__
from .kernel.api.contract import BasePlugin, TrustedBase
from .kernel.events.bus import EventBus
from .kernel.events.hooks import HookManager
from .kernel.observability import (
    HealthChecker,
    MetricsRegistry,
    Tracer,
    configure_logging,
    get_logger,
)
from .kernel.runtime.lifecycle import LifecycleManager
from .kernel.runtime.loader import PluginLoader
from .kernel.runtime.supervisor import PluginSupervisor
from .kernel.security.signature import sign_plugin, verify_plugin
from .registry.index import PluginRegistry
from .services import ServiceContainer

__all__ = [
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
]


class Xcore:
    """
    Point d'entrée unique du framework v2.
    """

    def __init__(self, config_path: str | None = None):
        from .configurations.loader import ConfigLoader

        self._config = ConfigLoader.load(config_path)
        self._booted = False

        # Sous-systèmes — instanciés lazily à boot()
        self.services: ServiceContainer | None = None
        self.plugins: PluginSupervisor | None = None
        self.events: EventBus | None = None
        self.hooks: HookManager | None = None
        self.registry: PluginRegistry | None = None

        self._logger = get_logger("xcore")

    async def boot(self, app=None) -> "Xcore":
        """Démarre tous les sous-systèmes dans le bon ordre."""

        if self._booted:
            return self

        configure_logging(self._config.observability.logging)
        self._logger.info(f"━━━ xcore v{__version__} démarrage ━━━")

        # 0. Validation clés secrètes en production
        if self._config.app.env == "production":
            self._validate_secret_keys()

        # etape intermediare
        # configuration de l'observabilite
        self.metrics = MetricsRegistry()
        self.tracer = Tracer(self._config.observability.tracing.service_name)
        self.health = HealthChecker()

        # 1. Services (BDD, cache, scheduler)
        from .services import ServiceContainer

        self.services = ServiceContainer(self._config.services)
        self.services.load_default_providers()
        await self.services.init()

        # 2. Event bus + hooks
        self.events = EventBus()
        self.hooks = HookManager()

        # 3. Registry des plugins
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

        # 5. Attache le router/middleware si une app est fournie
        if app is not None:
            framework = self._detect_framework(app)
            self._attach_router(
                app,
                prefix=self._config.app.plugin_prefix,
                tags=self._config.app.plugin_tags,
            )
            self._attach_middlewares(app, framework)

        self._booted = True
        self._logger.info("━━━ xcore prêt ━━━")
        return self

    async def shutdown(self) -> None:
        if not self._booted:
            return
        self._logger.info("Arrêt xcore...")
        if self.plugins:
            await self.plugins.shutdown()
        if self.services:
            await self.services.shutdown()
        self._booted = False
        self._logger.info("xcore arrêté.")

    def _attach_router(
        self,
        app,
        prefix: str | None = None,
        tags: list[str] | None = None,
    ) -> None:
        framework = self._detect_framework(app)
        self._logger.info(f"Framework détecté : {framework}")

        if framework == "fastapi":
            self._attach_fastapi(app, prefix, tags)
        elif framework == "flask":
            self._attach_flask(app, prefix)
        elif framework == "django":
            self._attach_django(app, prefix)
        else:
            self._logger.warning(
                f"Framework '{framework}' non supporté pour l'attachement automatique des routes."
            )

    def _detect_framework(self, app: Any) -> str:
        """Détecte le framework de l'application fournie."""
        cls_name = app.__class__.__name__
        if cls_name == "FastAPI":
            return "fastapi"
        if cls_name == "Flask":
            return "flask"
        # Django app is often just a module or a specific handler,
        # but often people pass the settings or a core object.
        # Here we check for common django patterns.
        if hasattr(app, "ROOT_URLCONF") or cls_name == "WSGIHandler" or cls_name == "ASGIHandler":
            return "django"

        # Fallback detection via modules if class name is not enough
        if "fastapi" in app.__class__.__module__:
            return "fastapi"
        if "flask" in app.__class__.__module__:
            return "flask"
        if "django" in app.__class__.__module__:
            return "django"

        return "unknown"

    def _attach_fastapi(self, app, prefix, tags):
        from .kernel.api.router import build_router
        from fastapi import APIRouter

        # 1. Router système xcore (status, reload, load, unload)
        system_router = build_router(
            supervisor=self.plugins,
            secret_key=self._config.app.secret_key,
            server_key=self._config.app.server_key,
            prefix=self._config.app.plugin_prefix,
            health_checker=self.health,
            metrics_registry=self.metrics,
            tags=(self._config.app.plugin_tags or []) + (tags or []),
        )
        app.include_router(system_router)

        # 2. Routers custom des plugins Trusted (get_router())
        plugin_routers = self.plugins.collect_plugin_routers()
        for plugin_name, plugin_router in plugin_routers:
            # On vérifie si c'est bien un router FastAPI
            if not hasattr(plugin_router, "include_router"):
                continue

            prefixed_router = plugin_router
            if not getattr(plugin_router, "prefix", "").startswith("/plugins/"):
                wrapper = APIRouter(
                    prefix=f"{prefix}/{plugin_name}",
                    tags=(self._config.app.plugin_tags or []) + (tags or []),
                )
                wrapper.include_router(plugin_router)
                prefixed_router = wrapper

            app.include_router(prefixed_router)
            n_routes = len(getattr(plugin_router, "routes", []))
            self._logger.info(
                f"[{plugin_name}] 🌐 {n_routes} route(s) montée(s) "
                f"sous {getattr(prefixed_router, 'prefix', prefix)}"
            )

    def _attach_flask(self, app, prefix):
        from .kernel.api.flask_adapter import build_flask_blueprint

        # 1. Router système
        system_bp = build_flask_blueprint(
            supervisor=self.plugins,
            secret_key=self._config.app.secret_key,
            server_key=self._config.app.server_key,
            prefix=self._config.app.plugin_prefix,
            health_checker=self.health,
            metrics_registry=self.metrics,
        )
        app.register_blueprint(system_bp)

        # 2. Plugins routers (si compatibles Flask)
        plugin_routers = self.plugins.collect_plugin_routers()
        for plugin_name, plugin_router in plugin_routers:
            # Si le plugin renvoie un Blueprint Flask
            if hasattr(plugin_router, "register"):
                # On assume que c'est un Blueprint ou compatible
                if not plugin_router.url_prefix:
                    plugin_router.url_prefix = f"{prefix}/{plugin_name}"
                app.register_blueprint(plugin_router)
                self._logger.info(f"[{plugin_name}] 🌐 Blueprint Flask monté")

    def _attach_django(self, app, prefix):
        from .kernel.api.django_adapter import build_django_urls
        from django.urls import include, path as django_path

        # Pour Django, c'est un peu plus complexe car on ne peut pas toujours
        # "injecter" des routes dans une app déjà démarrée facilement sans toucher aux urlconf.
        # On fournit ici une aide, mais l'utilisateur devra probablement inclure les URLs.
        # Cependant, si 'app' est le module d'URLConf, on pourrait essayer.

        self._logger.info("Configuration Django : les routes IPC sont disponibles via build_django_urls")

        # Note: Si app est un objet de configuration ou un handler,
        # on ne peut pas injecter dynamiquement les routes dans Django de la même manière.
        # On log l'intention.

    def _attach_middlewares(self, app, framework):
        if framework != "fastapi":
            # Pour l'instant on ne supporte l'injection d'état que pour FastAPI
            return

        for middleware in self.plugins.collect_app_state():
            if middleware:
                states = middleware.get("state")
                for key, value in states.items():
                    app.state.__setattr__(
                        key=f"{middleware['name']}_{key}", value=value
                    )
                    self._logger.info(
                        f"{middleware['name']}📦 état {middleware['name']}_{key} mis à jour"
                    )

        app.openapi_schema = None  # force la regen du schéma OpenAPI

    def _validate_secret_keys(self) -> None:
        """Bloque le démarrage en production si les clés secrètes sont celles par défaut."""
        if self._config.app.env != "production":
            return
        default_key = b"change-me-in-production"
        if self._config.app.secret_key == default_key:
            raise RuntimeError(
                "SECRET_KEY par défaut détecté en production ! "
                "Configurez app.secret_key dans votre xcore.yaml"
            )
        if self._config.plugins.secret_key == default_key:
            raise RuntimeError(
                "PLUGIN_SECRET_KEY par défaut détecté en production ! "
                "Configurez plugins.secret_key dans votre xcore.yaml"
            )

    def __repr__(self) -> str:
        status = "booted" if self._booted else "idle"
        return f"<Xcore [{status}] v{__version__}>"
