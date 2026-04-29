from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Protocol

from xcore.kernel.events.section import HookResult
from xcore.kernel.observability import MetricsRegistry, Tracer


class EventBus(Protocol):
    def on(
        self, event_name: str, priority: int = 50, name: str | None = None
    ) -> Callable: ...

    async def emit(
        self, event_name: str, data: dict[str, Any] | None = None
    ) -> list[Any]: ...

    # Note : on ne met PAS 'clear' ici.
    def once(self, event_name: str, priority: int = 50) -> Callable: ...

    def emit_sync(
        self, event_name: str, data: dict[str, Any] | None = None
    ) -> None: ...


class HookManager(Protocol):

    def register(
        self,
        event_name: str,
        func: Callable,
        priority: int = 50,
        once: bool = False,
        timeout: Optional[float] = None,
    ) -> Callable: ...

    def on(
        self,
        event_name: str,
        priority: int = 50,
        once: bool = False,
        timeout: Optional[float] = None,
    ) -> Callable: ...

    def once(
        self, event_name: str, priority: int = 50, timeout: Optional[float] = None
    ) -> Callable: ...

    async def emit(
        self, event_name: str, data: Optional[Dict[str, Any]] = None, **kwargs
    ) -> List[HookResult]: ...

    def unregister(self, event_name: str, func: Callable) -> bool: ...


class HealthChecker(Protocol):

    def register(self, name: str) -> Callable:
        """
        Decorator to register a function to be called when an event is emitted.
        Args:
            name (str): The name of the event to register the function for.
        """
        ...


class PluginRegistry(Protocol): ...


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
    caller: Callable[[str, str, dict], Awaitable[dict]] | None = None

    metrics: MetricsRegistry = None  # MetricsRegistry
    tracer: Tracer = None  # Tracer
    health: HealthChecker = None  # HealthChecker
    registry: PluginRegistry = None  # PluginRegistry
