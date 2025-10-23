from typing import Any, List, Optional

from manager.plManager import logger
from manager.tools.error import Error

try:
    from fasthtml.common import Route
except ImportError:
    Route = None


class AppType:
    FASTAPI = "fastapi"
    FASTHTML = "fasthtml"


class Reloader:
    def __init__(
        self,
        app: Any,
        base_routes: Optional[List[Any]] = None,
        app_type: str = AppType.FASTHTML,
    ):
        self.app = app
        self.base_routes = base_routes or []
        self.app_type = app_type

    # ------------------------------------------------------------
    # Méthode principale : reload
    # ------------------------------------------------------------
    @Error.exception_handler
    def reload(self) -> Any:
        """Recharge les routes principales de l'application."""
        logger.info(f"Reloading core routes for {self.app_type.upper()}...")

        if self.app_type == AppType.FASTHTML:
            self.__reload_fasthtml()
            logger.info("Core routes reloaded successfully.")

        elif self.app_type == AppType.FASTAPI:
            self.__reload_fastapi()
            logger.info("Core routes reloaded successfully.")
            return self.app

        else:
            logger.warning(f"Unknown app type: {self.app_type}")
            return self.app

        return self.app

    # ------------------------------------------------------------
    # 🧩 FASTHTML
    # ------------------------------------------------------------
    def __reload_fasthtml(self):
        if not Route:
            raise ImportError("fasthtml.common.Route introuvable")

        # Supprime toutes les routes sauf les 2 premières
        original_count = len(self.app.routes)
        self.app.routes = self.app.routes[:2]

        # Réinjecte les routes de base
        for route in self.base_routes:
            route.to_app(app=self.app)

        logger.info(
            f"{len(self.base_routes)} routes rechargées ({original_count - len(self.app.routes)} supprimées)."
        )

    # ------------------------------------------------------------
    # 🧩 FASTAPI
    # ------------------------------------------------------------
    def __reload_fastapi(self):
        from fastapi import FastAPI

        app: FastAPI = self.app

        for route in app.routes:
            if route in self.base_routes:
                app.routes.append(route)
            else:
                app.routes.remove(route)

        # Réinjection des routes de base
        for route in self.base_routes:
            app.include_router(route)

        logger.info(f"{len(self.base_routes)} routes FastAPI réinjectées.")

    # ------------------------------------------------------------
    # 🚀 Execution dynamique des plugins
    # ------------------------------------------------------------
    @Error.exception_handler
    def exec_plugins(self, plugins: List[Any]):
        logger.info("🚀 Exécution dynamique des plugins...")
        for plugin in plugins:
            self._add_plugin(plugin)
        return self.app

    @Error.exception_handler
    def _add_plugin(self, plugin: Any):
        """Ajoute un plugin dynamiquement à l'application."""

        if self.app_type == AppType.FASTHTML and hasattr(plugin, "router"):
            plugin.router.to_app(self.app)
        elif self.app_type == AppType.FASTAPI and hasattr(plugin, "router"):
            self.app.include_router(plugin.router)

        else:
            logger.warning(f"Plugin {plugin} invalide ou sans router.")
            return

        name = plugin.PLUGIN_INFO.get("name", "unknown")
        logger.info(f"Plugin {name} ajouté avec succès.")
