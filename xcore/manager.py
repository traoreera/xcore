"""
manager.py — Orchestrateur principal du système de plugins.
"""

import asyncio
import os
import pkgutil
from logging import Logger

from xcore.sandbox.manager import PluginManager
from xcore.sandbox.sandbox.snapshot import Snapshot
from xcore.sandbox.sandbox.supervisor import SupervisorConfig

from xcore.loggers import Logs, LoggingConfig  # ← ton système logging


class Manager:
    """
    Orchestrateur principal du système de plugins.
    """

    def __init__(
        self,
        app,
        base_routes,
        plugins_dir: str = "plugins",
        secret_key: bytes = b"change-me-in-production",
        services: dict = None,
        interval: int = 2,
        strict_trusted: bool = True,
        timeout: float = 10.0,
        max_restarts: int = 3,
        restart_delay: float = 1.0,
        logging_config: LoggingConfig = LoggingConfig(),
    ):
        self.app = app
        self.plugins_dir = plugins_dir
        self.base_routes = list(base_routes)
        self.interval = interval
        self.running = False
        self._services = services or {}

        # 🔥 Logger centralisé
        self.__logger: Logger = Logs("xcore.manager", logging_config).get()

        self.plugin_manager = PluginManager(
            plugins_dir=plugins_dir,
            secret_key=secret_key,
            services=self._services,
            sandbox_config=SupervisorConfig(
                timeout=timeout,
                max_restarts=max_restarts,
                restart_delay=restart_delay,
            ),
            strict_trusted=strict_trusted,
            app=app,
            logger=self.__logger,  # ← injection propre
        )

        self.snapshot = Snapshot(logger=self.__logger)

        if not os.path.exists(self.plugins_dir):
            os.makedirs(self.plugins_dir, exist_ok=True)
            with open(os.path.join(self.plugins_dir, "__init__.py"), "w") as f:
                f.write("# created automatically\n")

    # ── Services ──────────────────────────────────────────────

    def update_services(self, services: dict) -> None:
        self._services.update(services)
        self.plugin_manager._services.update(services)
        self.__logger.info(
            f"Services injectés : {list(services.keys())}"
        )

    # ── Démarrage ─────────────────────────────────────────────

    async def start(self) -> dict:
        report = await self.plugin_manager.load_all()

        self.__logger.info(
            f"Plugins chargés={len(report['loaded'])} "
            f"| échecs={len(report['failed'])} "
            f"| ignorés={len(report['skipped'])}"
        )

        self._attach_router()
        self.app.state.plugin_manager = self.plugin_manager
        return report

    def _attach_router(self) -> None:
        from xcore.sandbox.router import router as plugin_router

        existing = [r.path for r in self.app.routes if hasattr(r, "path")]

        if "/plugin/{plugin_name}/{action}" not in existing:
            self.app.include_router(plugin_router)
            self.app.openapi_schema = None
            self.__logger.info("Route plugin attachée")

    # ── Appel direct ──────────────────────────────────────────

    async def call(self, plugin_name: str, action: str, payload: dict) -> dict:
        return await self.plugin_manager.call(plugin_name, action, payload)

    # ── Watcher ───────────────────────────────────────────────

    def start_watching(self):
        last_snapshot = self.snapshot.create(self.plugins_dir)

        try:
            current_snapshot = self.snapshot.create(self.plugins_dir)

            if current_snapshot != last_snapshot:
                self.__logger.info("Changement détecté → reload plugins")

                asyncio.run(self.plugin_manager.shutdown())
                asyncio.run(self.plugin_manager.load_all())

        except Exception as e:
            self.__logger.exception("Erreur watcher")
            raise e

    # ── Arrêt ─────────────────────────────────────────────────

    async def stop(self) -> None:
        self.running = False
        await self.plugin_manager.shutdown()
        self.__logger.info("Manager arrêté")

    # ── Utilitaires ───────────────────────────────────────────

    def status(self) -> dict:
        return self.plugin_manager.status()

    def return_name(self) -> list[str]:
        if not os.path.exists(self.plugins_dir):
            return []

        return [
            name
            for _, name, _ in pkgutil.iter_modules([self.plugins_dir])
        ]