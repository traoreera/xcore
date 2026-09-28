"""
Rich context injected into each plugin.

PluginContext replaces the simple services dictionary from v1.
It provides access to services, the event bus, hooks, environment
variables, and the plugin configuration.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Coroutine

if TYPE_CHECKING:
    from ...registry import PluginRegistry
    from ..observability import HealthChecker, MetricsRegistry, Tracer
    from .proto import EventBus, HookManager


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
    events: EventBus = None  # EventBus
    hooks: HookManager = None  # HookManager
    env: dict[str, str] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    caller: Callable[[str, str, dict], Awaitable[dict]] | None = None
    tenant_id: str = "default"

    metrics: MetricsRegistry = None  # MetricsRegistry
    tracer: Tracer = None  # Tracer
    health: HealthChecker = None  # HealthChecker
    registry: PluginRegistry = None  # PluginRegistry

    # Rempli par LifecycleManager : les tâches créées via spawn_task() y sont
    # ajoutées pour pouvoir être annulées de force au unload, sans dépendre
    # du plugin pour les traquer lui-même.
    _task_sink: list[asyncio.Task] | None = field(default=None, repr=False)

    def spawn_task(self, coro: Coroutine, name: str | None = None) -> asyncio.Task:
        """
        Crée une tâche de fond suivie par le kernel.

        À utiliser à la place d'un `asyncio.create_task()` brut pour tout ce
        qui ne doit pas survivre au unload du plugin : le kernel annule
        automatiquement les tâches encore en cours au moment du unload,
        qu'on_unload/on_stop l'ait fait ou non.
        """
        task = asyncio.create_task(coro, name=name)
        if self._task_sink is not None:
            self._task_sink.append(task)
        return task

    def get_service(self, name: str) -> Any:
        """
        Accès sécurisé à un service avec vérification de scoping via le registry
        si disponible, sinon via le container partagé.
        """
        # Priorité au registry pour le respect des scopes (public/private/protected)
        if self.registry:
            try:
                return self.registry.get_service(name, requester=self.name)
            except (KeyError, PermissionError) as e:
                # Si non trouvé ou refusé par le registry, on tente le container
                # (Certains services noyau ne sont pas forcément dans le registry)
                if isinstance(e, PermissionError):
                    raise

        # Fallback sur le container direct
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
