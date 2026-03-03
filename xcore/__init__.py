"""
xcore v2 — Framework modulaire plugin-first avec intégration de services.

Quickstart:
    from xcore import Xcore

    app = Xcore()
    await app.boot()

    # Accès au plugin manager
    result = await app.plugins.call("my_plugin", "my_action", {...})

    # Accès aux services intégrés
    db    = app.services.get("db")
    cache = app.services.get("cache")
"""

from .__version__ import __version__
from .kernel.api.contract import BasePlugin, TrustedBase
from .kernel.events.bus import EventBus
from .kernel.events.hooks import HookManager
from .kernel.observability.logging import get_logger
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

        self._logger.info(f"━━━ xcore v{__version__} démarrage ━━━")

        # 1. Services (BDD, cache, scheduler)
        from .services import ServiceContainer

        self.services = ServiceContainer(self._config.services)
        await self.services.init()

        # 2. Event bus + hooks
        self.events = EventBus()
        self.hooks = HookManager()

        # 3. Registry des plugins
        self.registry = PluginRegistry(self._config)

        # 4. Plugin supervisor (runtime + sandbox)
        self.plugins = PluginSupervisor(
            config=self._config.plugins,
            services=self.services,
            events=self.events,
            hooks=self.hooks,
            registry=self.registry,
        )
        await self.plugins.boot()

        # 5. Attache le router FastAPI si une app est fournie
        if app is not None:
            self._attach_router(
                app,
                prefix=self._config.app.plugin_prefix,
                tags=self._config.app.plugin_tags,
            )

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
        from .kernel.api.router import build_router

        # 1. Router système xcore (status, reload, load, unload)
        system_router = build_router(
            supervisor=self.plugins,
            secret_key=self._config.app.secret_key,
            prefix=self._config.app.plugin_prefix,
            tags=self._config.app.plugin_tags,
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

                wrapper = APIRouter(prefix=f"{prefix}/{plugin_name}", tags=self._config.app.plugin_tags.extend(tags))
                wrapper.include_router(plugin_router)
                prefixed_router = wrapper
            app.include_router(prefixed_router)
            n_routes = len(getattr(plugin_router, "routes", []))
            self._logger.info(
                f"[{plugin_name}] 🌐 {n_routes} route(s) montée(s) "
                f"sous /plugins/{plugin_name}"
            )

        app.openapi_schema = None  # force la regen du schéma OpenAPI

    def __repr__(self) -> str:
        status = "booted" if self._booted else "idle"
        return f"<Xcore [{status}] v{__version__}>"
