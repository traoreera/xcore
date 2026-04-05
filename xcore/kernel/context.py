"""
KernelContext — Encapsulation des dépendances partagées du noyau.
Simplifie l'injection de dépendances et réduit le couplage entre les composants.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..configurations.sections import PluginConfig
    from ..events.bus import EventBus
    from ..events.hooks import HookManager
    from ..observability import HealthChecker, MetricsRegistry, Tracer
    from ..registry.index import PluginRegistry
    from ..services.container import ServiceContainer


@dataclass
class KernelContext:
    """
    Objet de contexte partagé par tous les composants du kernel (Supervisor, Loader, Lifecycle).
    """
    config: PluginConfig
    services: ServiceContainer
    registry: PluginRegistry
    events: EventBus | None = None
    hooks: HookManager | None = None
    metrics: MetricsRegistry | None = None
    tracer: Tracer | None = None
    health: HealthChecker | None = None

    def as_plugin_context_kwargs(self) -> dict[str, Any]:
        """Retourne les arguments pour instancier un PluginContext."""
        return {
            "services": self.services.as_dict() if hasattr(self.services, "as_dict") else {},
            "events": self.events,
            "hooks": self.hooks,
            "metrics": self.metrics,
            "tracer": self.tracer,
            "health": self.health,
            "registry": self.registry,
        }
