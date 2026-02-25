"""
Integration — point d'entrée du framework de services.

Usage minimal :
    from integrations import Integration

    integration = Integration()
    await integration.init()

    email = integration.get("email")
    await email.send(to="alice@example.com", subject="Bonjour", body="...")

Usage synchrone (wrapper) :
    integration = Integration()
    integration.init_sync()

Usage FastAPI :
    from contextlib import asynccontextmanager
    from fastapi import FastAPI
    from integrations import Integration

    integration = Integration()

    @asynccontextmanager
    async def lifespan(app):
        await integration.init()
        yield
        await integration.shutdown()

    app = FastAPI(lifespan=lifespan)
"""

from __future__ import annotations

import asyncio
from logging import Logger
from pathlib import Path
from typing import Optional

from xcore.integration.config.schemas import HandlerLogging, LoggingConsole, LoggingFile
from xcore.loggers import Logs, LoggingConfig

from ..config.loader import IntegrationConfig, get_config
from ..core.registry import ServiceRegistry, get_registry
from ..plugins.base import BaseService
from ..plugins.extension_loader import ExtensionLoader
from ..services.cache import CacheService
from ..services.database import DatabaseManager
from ..services.scheduler import SchedulerService


class Integration:
    """
    Orchestrateur central du framework d'intégration de services.

    Charge la configuration YAML, instancie tous les services déclarés
    dans la section `extensions', et les rend accessibles globalement.
    """

    def __init__(self, config_path: Optional[str | Path] = None):
        self._config_path = config_path
        self._config: Optional[IntegrationConfig] = None
        self._registry: Optional[ServiceRegistry] = None
        self._extensions: Optional[ExtensionLoader] = None
        self._db: Optional[DatabaseManager] = None
        self._cache: Optional[CacheService] = None
        self._scheduler: Optional[SchedulerService] = None
        self._initialized = False

    # ── Init ──────────────────────────────────────────────────

    async def init(self) -> "Integration":
        """Initialise tous les services de façon asynchrone."""
        if self._initialized:
            return self
        # 1. Config
        self._config = get_config(self._config_path)
        self.__logger = Logs(name="xcore", config=LoggingConfig(
            level=self._config.logging.level,
            format=self._config.logging.format,
            handlers= HandlerLogging(
                console=LoggingConsole(enabled=self._config.logging.handlers['console']['enabled']),
                file=LoggingFile(
                    enabled=self._config.logging.handlers['file']['enabled'],
                    path=self._config.logging.handlers['file']['path'],
                    max_bytes=self._config.logging.handlers['file']['max_bytes'],
                    backup_count=self._config.logging.handlers['file']['backup_count'],
                )
            )
        )).get()
        self.__logger.info("━━━ Démarrage Integration Framework ━━━")
        # 2.global register
        self._registry = get_registry()

        # 3. Infrastructure (BDD, cache, scheduler)
        self._db = DatabaseManager(self._config)
        await self._db.init_all()
        self._registry.register_instance("db", self._db)

        self._cache = CacheService(self._config)
        self._cache.init()
        self._registry.register_instance("cache", self._cache)

        self._scheduler = SchedulerService(self._config)
        self._scheduler.init()
        self._registry.register_instance("scheduler", self._scheduler)

        # 4. Extensions de services (déclarées dans le YAML)
        self._extensions = ExtensionLoader(self._config, registry=self._registry)
        await self._extensions.init_all()

        self._initialized = True
        self.__logger.info(
            f"━━━ Framework prêt — "
            f"{len(self._extensions.all())} service(s) actif(s) ━━━"
        )
        return self

    def init_sync(self) -> "Integration":
        """Wrapper synchrone pour les contextes non-async."""
        asyncio.run(self.init())
        return self

    # ── Accès aux services ────────────────────────────────────

    def get(self, name: str) -> BaseService:
        """
        Retourne un service par son nom (tel que déclaré dans integration.yaml).

        Exemple :
            email = integration.get("email")
            email.send(to="alice@example.com", subject="Bonjour")
        """
        self._assert_ready()
        return self._extensions.get(name)

    def get_optional(self, name: str) -> Optional[BaseService]:
        """Retourne un service ou None s'il n'est pas activé."""
        self._assert_ready()
        return self._extensions.get_optional(name)

    def has(self, name: str) -> bool:
        """Vérifie si un service est disponible."""
        self._assert_ready()
        return self._extensions.has(name)

    def __getitem__(self, name: str) -> BaseService:
        """Sucre syntaxique : integration["email"]"""
        return self.get(name)

    # ── Infrastructure ────────────────────────────────────────

    @property
    def db(self) -> DatabaseManager:
        self._assert_ready()
        return self._db

    @property
    def cache(self) -> CacheService:
        self._assert_ready()
        return self._cache

    @property
    def scheduler(self) -> SchedulerService:
        self._assert_ready()
        return self._scheduler

    @property
    def registry(self) -> ServiceRegistry:
        self._assert_ready()
        return self._registry

    @property
    def config(self) -> IntegrationConfig:
        self._assert_ready()
        return self._config
    @property
    def extensions(self) -> ExtensionLoader:
        self._assert_ready()
        return self._extensions
    @property
    def logger(self) -> Logger:
        self._assert_ready()
        return self.__logger
    
    # ── Monitoring ────────────────────────────────────────────

    def status(self) -> dict:
        """Retourne l'état complet du framework et de tous les services."""
        self._assert_ready()
        return {
            "app": self._config.app.name,
            "env": self._config.app.env,
            "services": self._extensions.status(),
            "db": list(self._db.adapters.keys()) if self._db else [],
            "scheduler_running": (
                self._scheduler.is_running if self._scheduler else False
            ),
        }

    # ── Arrêt ─────────────────────────────────────────────────

    async def shutdown(self):
        """Arrêt propre de tous les services."""
        self.__logger.info("Arrêt demande  du framework...")
        if self._extensions:
            await self._extensions.shutdown_all()
        if self._scheduler:
            self._scheduler.shutdown()
        if self._db:
            await self._db.close_all()
        self._initialized = False
        self.__logger.info("Framework arrêté.")

    # ── Helpers ───────────────────────────────────────────────

    def _assert_ready(self):
        if not self._initialized:
            self.__logger.warning("Integration non initialisée. Appelez await integration.init() d'abord.")
            raise RuntimeError(
                "Integration non initialisée. Appelez await integration.init() d'abord."
            )

    def __repr__(self):
        status = "ready" if self._initialized else "not initialized"
        name = self._config.app.name if self._config else "?"
        return f"<Integration [{status}] app='{name}'>"


# ─────────────────────────────────────────────────────────────
# Singleton global + accès rapide
# ─────────────────────────────────────────────────────────────

_integration: Optional[Integration] = None


def setup(config_path: Optional[str | Path] = None) -> Integration:
    """Crée le singleton global (à appeler une fois au démarrage)."""
    global _integration
    _integration = Integration(config_path)
    return _integration


def get_service(name: str) -> BaseService:
    """
    Accès rapide à un service depuis n'importe où dans le code.

    Exemple :
        from integrations import get_service
        email = get_service("email")
    """
    if _integration is None:
        raise RuntimeError(
            "Framework non initialisé. "
            "Appelez integrations.setup() puis await integration.init()."
        )
    return _integration.get(name)
