"""
services/ — Couche d'intégration des services xcore v2.

Point d'entrée : ServiceContainer
  - Initialise, orchestre et expose tous les services
  - Injection dans les plugins via PluginContext.services

Usage:
    container = ServiceContainer(config.services)
    await container.init()

    db       = container.get("db")        # premier adaptateur BDD
    cache    = container.get("cache")     # CacheService
    scheduler= container.get("scheduler") # SchedulerService

    await container.shutdown()
"""

from .base import BaseService, ServiceStatus
from .container import ServiceContainer

__all__ = ["ServiceContainer", "BaseService", "ServiceStatus"]
