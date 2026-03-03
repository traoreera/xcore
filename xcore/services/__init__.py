"""
services/ — Integration layer for xcore v2 services.

Entry point: ServiceContainer
    - Initializes, orchestrates, and exposes all services
    - - Injects services into plugins via PluginContext.services

Use:
    ```python
    container = ServiceContainer(config.services)
    await container.init()

    db       = container.get("db")        # first database adapter
    cache    = container.get("cache")     # CacheService
    scheduler= container.get("scheduler") # SchedulerService

    await container.shutdown()
    ```
"""

from .base import BaseService, ServiceStatus
from .container import ServiceContainer

__all__ = ["ServiceContainer", "BaseService", "ServiceStatus"]
