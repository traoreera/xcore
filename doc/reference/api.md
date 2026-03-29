# Kernel API Exhaustive Reference

This reference documents the internal kernel APIs of XCore. These APIs are used for framework orchestration and are available to `Trusted` plugins via `self.ctx`.

## 1. `Xcore` (Main Orchestrator)

The `Xcore` class is the central point of the framework.

- `__init__(config_path: str = "xcore.yaml")`: Initializes the core with the specified configuration file.
- `async boot(app: FastAPI = None) -> None`:
    - Boots all services in order.
    - Loads all plugins via `PluginSupervisor`.
    - If `app` is provided, it mounts all plugin-defined routers.
- `async shutdown() -> None`:
    - Gracefully stops all plugins.
    - Shuts down all services in reverse order.
- `plugins`: Access to the `PluginSupervisor` instance.
- `services`: Access to the `ServiceContainer` instance.
- `events`: Access to the `EventBus` instance.

## 2. `PluginSupervisor`

Responsible for high-level plugin management and cross-plugin communication.

- `async call(plugin_name: str, action: str, payload: dict, *, resource: str = None) -> dict`:
    - The primary way to call another plugin.
    - Executes the middleware pipeline (Tracing -> RateLimit -> Permission -> Retry).
    - `resource` can be explicitly set for permission checks; otherwise, it defaults to the action name.
- `async load(plugin_name: str) -> None`: Loads a specific plugin from disk.
- `async reload(plugin_name: str) -> None`: Hot-reloads a plugin.
- `async unload(plugin_name: str) -> None`: Unloads a plugin and releases its resources.
- `status() -> dict`: Returns a list of all plugins and their current states.
- `list_plugins() -> list[str]`: Returns a list of loaded plugin names.
- `permissions_audit(plugin_name: str = None, limit: int = 100) -> list[dict]`: Returns the most recent permission check results.

## 3. `ServiceContainer`

Manages the lifecycle and discovery of shared services.

- `get(name: str) -> Any`: Retrieves a service by its registered name. Raises `KeyError` if missing.
- `get_as(name: str, type_: type[T]) -> T`: Retrieves a service and asserts its type for better IDE support.
- `register_service(name: str, service: Any) -> None`: Manually registers a service instance.
- `register_provider(name: str, provider: Any) -> None`: Registers a lazy service provider.
- `async health() -> dict`: Aggregates the health check results from all registered services.
- `has(name: str) -> bool`: Returns True if the service exists.

## 4. `EventBus`

Asynchronous event distribution system.

- `async emit(event_name: str, data: dict = None, source: str = None, gather: bool = True) -> list[Any]`:
    - Dispatches an event to all subscribers.
    - If `gather=True`, handlers run in parallel.
    - Returns a list of results from all handlers.
- `emit_sync(event_name: str, data: dict = None) -> None`: Fire-and-forget emission.
- `on(event_name: str, priority: int = 50) -> Callable`: Decorator for subscribing to an event.
- `once(event_name: str, priority: int = 50) -> Callable`: Decorator for a one-time subscription.
- `subscribe(event_name: str, handler: Callable, priority: int = 50, once: bool = False)`: Programmatic subscription.
- `unsubscribe(event_name: str, handler: Callable) -> None`: Removes a subscription.

## 5. `PermissionEngine`

Handles security policy evaluation.

- `check(plugin_name: str, resource: str, action: str) -> None`:
    - Evaluates if the plugin is allowed to perform the action on the resource.
    - Raises `PermissionDenied` if the check fails.
- `allows(plugin_name: str, resource: str, action: str) -> bool`: Returns a boolean indicating permission status without raising an exception.
- `load_from_manifest(plugin_name: str, raw_permissions: list[dict]) -> None`: Replaces the current policy set for a plugin.

## 6. `PluginLoader` (Internal)

Handles low-level plugin discovery and dependency resolution.

- `async load_all() -> dict`: Discovers and loads plugins in topological waves.
- `_topo_sort(manifests: list) -> list`: Implements Kahn's algorithm for DAG sorting.
- `_flush_services(plugin_names: list[str]) -> None`: Propagates services exposed by plugins to the global container.
