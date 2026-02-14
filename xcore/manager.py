"""
manager.py
───────────
Orchestrateur principal — point d'entrée unique du système de plugins.
Connecte le PluginManager (Trusted + Sandbox) au cycle de vie FastAPI.
"""

import asyncio
import os
import pkgutil
import time
from pathlib import Path

from logging import Logger
from venv import logger
from xcore.sandbox.manager import PluginManager
from xcore.sandbox.sandbox.supervisor import SupervisorConfig
from xcore.sandbox.sandbox.snapshot import Snapshot

logger =Logger("xcore.manager")

class Manager:
    """
    Orchestrateur principal du système de plugins.

    Remplace l'ancien Loader/Reloader par le nouveau PluginManager
    qui gère nativement les modes Trusted et Sandboxed.
    """

    def __init__(
        self,
        app,
        base_routes,
        plugins_dir:    str   = "plugins",
        secret_key:     bytes = b"change-me-in-production",
        services:       dict  = None,
        interval:       int   = 2,
        strict_trusted: bool  = True,
    ):
        self.app         = app
        self.plugins_dir = plugins_dir
        self.base_routes = list(base_routes)
        self.interval    = interval
        self.running     = False

        # ── Nouveau PluginManager ──────────────────
        self.plugin_manager = PluginManager(
            plugins_dir    = plugins_dir,
            secret_key     = secret_key,
            services       = services or {},
            sandbox_config = SupervisorConfig(
                timeout       = 10.0,
                max_restarts  = 3,
                restart_delay = 1.0,
            ),
            strict_trusted = strict_trusted,
        )

        self.snapshot = Snapshot()

        # Crée le dossier plugins s'il n'existe pas
        if not os.path.exists(self.plugins_dir):
            os.makedirs(self.plugins_dir, exist_ok=True)
            with open(os.path.join(self.plugins_dir, "__init__.py"), "w") as f:
                f.write("# created automatically\n")

    # ──────────────────────────────────────────────
    # Démarrage
    # ──────────────────────────────────────────────

    async def start(self) -> dict:
        """
        Charge tous les plugins et attache la route unique à FastAPI.
        À appeler dans le lifespan/startup de FastAPI.
        """
        # 1. Charge tous les plugins (Trusted + Sandboxed)
        report = await self.plugin_manager.load_all()
        logger.info(
            f"Plugins chargés: {len(report['loaded'])} | "
            f"échecs: {len(report['failed'])} | "
            f"ignorés: {len(report['skipped'])}"
        )

        # 2. Attache la route unique /plugin/{name}/{action}
        self._attach_router()

        # 3. Expose le plugin_manager dans app.state
        #    (nécessaire pour la dépendance FastAPI dans router.py)
        self.app.state.plugin_manager = self.plugin_manager

        return report

    def _attach_router(self) -> None:
        """Attache le router /plugin/* à l'application FastAPI."""
        from xcore.sandbox.router import router as plugin_router

        # Vérifie qu'il n'est pas déjà attaché
        existing_prefixes = [
            r.path for r in self.app.routes if hasattr(r, "path")
        ]
        if "/plugin/{plugin_name}/{action}" not in existing_prefixes:
            self.app.include_router(plugin_router)
            self.app.openapi_schema = None
            logger.info("Route /plugin/{name}/{action} attachée")

    # ──────────────────────────────────────────────
    # Appel direct (sans passer par HTTP)
    # ──────────────────────────────────────────────

    async def call(self, plugin_name: str, action: str, payload: dict) -> dict:
        """
        Appelle un plugin directement depuis le code Python du Core.
        Même interface que la route HTTP, sans overhead réseau.
        """
        return await self.plugin_manager.call(plugin_name, action, payload)

    # ──────────────────────────────────────────────
    # Watcher (surveillance des changements)
    # ──────────────────────────────────────────────

    def start_watching(self, service) -> None:
        """Surveille le dossier et recharge en cas de changement."""
        last_snapshot = self.snapshot.create(self.plugins_dir)
        while service.running:
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

    # ──────────────────────────────────────────────
    # Arrêt
    # ──────────────────────────────────────────────

    async def stop(self) -> None:
        """Arrête proprement tous les plugins."""
        self.running = False
        await self.plugin_manager.shutdown()
        logger.info("Manager arrêté")

    # ──────────────────────────────────────────────
    # Utilitaires
    # ──────────────────────────────────────────────

    def status(self) -> dict:
        """Retourne le status de tous les plugins."""
        return self.plugin_manager.status()

    def return_name(self) -> list[str]:
        """Retourne la liste des plugins détectés sur le disque."""
        if not os.path.exists(self.plugins_dir):
            return []
        return [name for _, name, _ in pkgutil.iter_modules([self.plugins_dir])]