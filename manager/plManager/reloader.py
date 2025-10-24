from typing import Any, List

from manager.plManager import logger
from manager.tools.error import Error


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
        base_paths = {(r.path, tuple(sorted(r.methods))) for r in base_routes}
        self.app.routes[:] = [
            r
            for r in self.app.routes
            if (r.path, tuple(sorted(r.methods))) in base_paths
        ]
        self.app.router.routes[:] = self.app.routes
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