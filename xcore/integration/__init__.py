"""
integrations — Framework d'intégration de services modulaire.

Quickstart :
    from integrations import Integration

    integration = Integration(app=my_fastapi_app)
    integration.init()

    # Accès aux services
    db = integration.db.get("default")
    cache = integration.cache
    scheduler = integration.scheduler
"""

from .config.loader import IntegrationConfig, get_config, reload_config
from .core.events import Event, EventBus, get_event_bus
from .core.integration import Integration
from .core.registry import ServiceRegistry, ServiceScope, get_registry

__all__ = [
    "Integration",
    "EventBus",
    "Event",
    "get_event_bus",
    "ServiceRegistry",
    "ServiceScope",
    "get_registry",
    "get_config",
    "reload_config",
    "IntegrationConfig",
]

__version__ = "2.0.0"
