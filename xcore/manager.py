"""
manager.py — Orchestrateur principal du système de plugins.
"""

import asyncio
import os
import pkgutil
import time
from logging import Logger
from pathlib import Path

from xcore.sandbox.manager import PluginManager
from xcore.sandbox.sandbox.snapshot import Snapshot
from xcore.sandbox.sandbox.supervisor import SupervisorConfig

logger = Logger("xcore.manager")


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
    ):
        self.app = app
        self.plugins_dir = plugins_dir
        self.base_routes = list(base_routes)
        self.interval = interval
        self.running = False

        # Le dict services est stocké ici — update_services() le met à jour
        # ET le pousse dans plugin_manager avant load_all()
        self._services = services or {}

        self.plugin_manager = PluginManager(
            plugins_dir=plugins_dir,
            secret_key=secret_key,
            services=self._services,  # référence partagée
            sandbox_config=SupervisorConfig(
                timeout=10.0,
                max_restarts=3,
                restart_delay=1.0,
            ),
            strict_trusted=strict_trusted,
            app=app,
        )

        self.snapshot = Snapshot()

        if not os.path.exists(self.plugins_dir):
            os.makedirs(self.plugins_dir, exist_ok=True)
            with open(os.path.join(self.plugins_dir, "__init__.py"), "w") as f:
                f.write("# created automatically\n")

    # ── Services ──────────────────────────────────────────────

    def update_services(self, services: dict) -> None:
        """
        Injecte les services dans le PluginManager.
        À appeler dans le lifespan APRÈS integration.init()
        et AVANT manager.start().

        Met à jour à la fois self._services et plugin_manager._services
        pour que les plugins y aient accès dès leur chargement.
        """
        self._services.update(services)
        # Mise à jour directe du dict interne du PluginManager
        self.plugin_manager._services.update(services)
        logger.info(f"Services injectés dans PluginManager : {list(services.keys())}")

    # ── Démarrage ─────────────────────────────────────────────

    async def start(self) -> dict:
        """
        Charge tous les plugins et attache la route unique à FastAPI.
        Les services doivent être injectés via update_services() avant cet appel.
        """
        report = await self.plugin_manager.load_all()
        logger.info(
            f"Plugins chargés: {len(report['loaded'])} | "
            f"échecs: {len(report['failed'])} | "
            f"ignorés: {len(report['skipped'])}"
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
            logger.info("Route /plugin/{name}/{action} attachée")

    # ── Appel direct ──────────────────────────────────────────

    async def call(self, plugin_name: str, action: str, payload: dict) -> dict:
        return await self.plugin_manager.call(plugin_name, action, payload)

    # ── Watcher ───────────────────────────────────────────────

    def start_watching(self) -> None:
        last_snapshot = self.snapshot.create(self.plugins_dir)
        try:
            current_snapshot = self.snapshot.create(self.plugins_dir)
            if current_snapshot != last_snapshot:
                logger.info("Changement détecté → rechargement des plugins")
                asyncio.run(self.plugin_manager.shutdown())
                asyncio.run(self.plugin_manager.load_all())
                last_snapshot = current_snapshot
            time.sleep(self.interval)
        except Exception as e:
            logger.error(f"Erreur watcher : {e}")
            time.sleep(self.interval)

    # ── Arrêt ─────────────────────────────────────────────────

    async def stop(self) -> None:
        self.running = False
        await self.plugin_manager.shutdown()
        logger.info("Manager arrêté")

    # ── Utilitaires ───────────────────────────────────────────

    def status(self) -> dict:
        return self.plugin_manager.status()

    def return_name(self) -> list[str]:
        if not os.path.exists(self.plugins_dir):
            return []
        return [name for _, name, _ in pkgutil.iter_modules([self.plugins_dir])]
