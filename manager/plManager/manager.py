import os
import pkgutil
import time

from . import logger
from .loader import Loader
from .reloader import Reloader
from .snapshot import Snapshot


class Manager:
    """Orchestrateur principal du système de plugins."""

    def __init__(
        self,
        app,
        base_routes,
        plugins_dir="plugins",
        entry_point="run",
        interval=2,
    ):
        self.app = app
        self.plugins_dir = plugins_dir
        self.entry_point = entry_point
        self.loader = Loader(
            directory=plugins_dir,
            entry_point=entry_point,
            app=app,
            logger=logger,
        )
        self.loader.bind_to_fastapi()
        self.snapshot = Snapshot()
        self.interval = interval
        self.running = False
        self.base_routes = base_routes
        self.reloader = Reloader(app=app)

        if not os.path.exists(self.plugins_dir):
            os.makedirs(self.plugins_dir, exist_ok=True)
            with open(f"{self.plugins_dir}/__init__.py", "w") as f:
                f.write("#create automatically")

    # ------------------------------------------------------

    def run_plugins(self, reload_app=False):
        """Exécute ou recharge dynamiquement tous les plugins."""
        plugins = self.loader.load_plugins()
        if reload_app:
            logger.info("Rechargement complet demandé")
            self.reloader.reload(base_routes=self.base_routes)
        self.reloader.exec_plugins(plugins=plugins)

    # ------------------------------------------------------

    def _watch_loop(self):
        """Surveille le dossier des plugins et recharge en cas de changement."""

    def start_watching(self, service):
        last_snapshot = self.snapshot.create(self.plugins_dir)

        while service.running:
            try:
                current_snapshot = self.snapshot.create(self.plugins_dir)
                if current_snapshot != last_snapshot:
                    logger.info("Changement détecté → reload des plugins")
                    self.run_plugins(reload_app=True)
                    last_snapshot = current_snapshot
                time.sleep(self.interval)

            except Exception as e:
                logger.error(f"Erreur watcher")
                logger.exception(e)
                time.sleep(self.interval)

    def stop_watching(self):
        """Arrête le watcher."""
        self.running = False
        logger.info("Watcher arrêté")
        self.close_db()

    def return_name(self):
        """Retourne la liste des plugins détectés."""
        if not os.path.exists(self.plugins_dir):
            return []
        return [name for _, name, _ in pkgutil.iter_modules([self.plugins_dir])]

    # ------------------------------------------------------
    # DB
    # ------------------------------------------------------
    def close_db(self):
        self.loader.close_db()
