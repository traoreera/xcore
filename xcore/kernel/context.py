"""
KernelContext - Unified context for kernel-level components.
Resolves "prop drilling" by encapsulating all core dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..configurations.sections import PluginConfig
    from ..registry.index import PluginRegistry
    from .events.bus import EventBus
    from .events.hooks import HookManager
    from .observability.metrics import MetricsRegistry
    from .observability.tracing import Tracer
    from .observability.health import HealthChecker
    from ..services.container import ServiceContainer


@dataclass
class KernelContext:
    """
    Unified context for kernel-level components.
    """
    config: PluginConfig
    services: ServiceContainer
    registry: PluginRegistry | None = None
    events: EventBus | None = None
    hooks: HookManager | None = None
    metrics: MetricsRegistry | None = None
    tracer: Tracer | None = None
    health: HealthChecker | None = None

    def as_plugin_context_params(self, plugin_name: str, caller: Any = None) -> dict[str, Any]:
        """
        Extracts parameters needed to build a PluginContext.
        """
        return {
            "name": plugin_name,
            "services": self.services.as_dict() if self.services else {},
            "events": self.events,
            "hooks": self.hooks,
            "metrics": self.metrics,
            "tracer": self.tracer,
            "health": self.health,
            "registry": self.registry,
            "caller": caller,
        }
