from typing import Any, List

from ..plManager import logger
from ..tools.error import Error


class Reloader:
    def __init__(
        self,
        app: Any,
    ):
        self.app = app

    # ------------------------------------------------------------
    # Méthode principale : reload
    # ------------------------------------------------------------
    @Error.exception_handler
    def reload(self, base_routes) -> Any:
        logger.info("🔄 Rechargement des routes...")
        if not base_routes:
            logger.warning("Aucune route de base fournie, reload ignoré.")
            return self.app

        base_signatures = {
            self._get_route_signature(route)
            for route in base_routes
            if self._get_route_signature(route) is not None
        }

        filtered_routes = [
            route
            for route in self.app.routes
            if self._get_route_signature(route) in base_signatures
        ]

        logger.info(f"Routes conservées: {len(filtered_routes)}/{len(self.app.routes)}")
        self.app.routes[:] = filtered_routes
        self.app.router.routes[:] = filtered_routes
        self.app.openapi_schema = None
        if hasattr(self.app, "_original_openapi"):
            self.app.openapi = self.app._original_openapi
            self.app.openapi_schema = None

        return self.app

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

        self.app.include_router(plugin.router)

        return plugin

    @staticmethod
    def _get_route_signature(route):
        """
        Génère une signature unique pour une route en gérant tous les types.

        Returns:
            tuple: (path, methods_tuple) où methods_tuple peut être:
                - tuple des méthodes HTTP pour les APIRoute
                - ('MOUNT',) pour les Mount
                - ('WEBSOCKET',) pour les WebSocketRoute
        """
        if not hasattr(route, "path"):
            return None

        path = route.path

        # Gestion des différents types de routes
        if hasattr(route, "methods"):
            # APIRoute classique
            methods = tuple(sorted(route.methods))
        elif route.__class__.__name__ == "Mount":
            # Mount pour fichiers statiques
            methods = ("MOUNT",)
        elif route.__class__.__name__ == "WebSocketRoute":
            # WebSocket
            methods = ("WEBSOCKET",)
        else:
            # Type inconnu, signature générique
            methods = (route.__class__.__name__,)

        return (path, methods)
