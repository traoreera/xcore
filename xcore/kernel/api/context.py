"""
Rich context injected into each plugin.

PluginContext replaces the simple services dictionary from v1.
It provides access to services, the event bus, hooks, environment
variables, and the plugin configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


@dataclass
class PluginContext:
    """
    Context injected into each Trusted plugin at load time.

    Attributes:

        name: plugin name
        services: shared dictionary of services (database, cache, other plugins, etc.)
        events: EventBus — emit/subscribe to events
        hooks: HookManager — priority hooks with wildcards
        env: environment variables resolved from plugin.yaml
        config: `extra` block of the manifest (arbitrary plugin configuration)
    """

    name: str
    services: dict[str, Any] = field(default_factory=dict)
    events: Any = None  # EventBus
    hooks: Any = None  # HookManager
    env: dict[str, str] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    caller: Callable[[str, str, dict], Awaitable[dict]] | None = None

    metrics: Any = None   # MetricsRegistry
    tracer: Any = None    # Tracer
    health: Any = None    # HealthChecker

    def get_service(self, name: str) -> Any:
        """Accès sécurisé à un service avec message d'erreur clair."""
        svc = self.services.get(name)
        if svc is None:
            raise KeyError(
                f"[{self.name}] Service '{name}' unavailable. "
                f"available : {sorted(self.services.keys())}"
            )
        return svc

    def has_service(self, name: str) -> bool:
        return name in self.services

    def __repr__(self) -> str:
        return (
            f"<PluginContext plugin='{self.name}' "
            f"services={sorted(self.services.keys())}>"
        )
