# Kernel API Reference

This document covers the internal APIs of the XCore kernel, available to `Trusted` plugins via `self.ctx`.

## 1. `PluginSupervisor`

Manages the lifecycle and execution of plugins.

- **`async call(plugin_name: str, action: str, payload: dict, *, resource: str = None) -> dict`**: Executes a cross-plugin call with full middleware support (Security, RateLimit, Tracing).
- **`async load(plugin_name: str) -> None`**: Dynamically loads a plugin from disk.
- **`async reload(plugin_name: str) -> None`**: Performs a hot-reload of a plugin.
- **`async unload(plugin_name: str) -> None`**: Gracefully stops and removes a plugin.
- **`status() -> dict`**: Returns the health and state of all managed plugins.

---

## 2. `ServiceContainer`

Registry for shared resources and infrastructure.

- **`get(name: str) -> Any`**: Retrieves a registered service (e.g., `db`, `cache`).
- **`has(name: str) -> bool`**: Checks if a service is registered.
- **`register_service(name: str, service: Any) -> None`**: Manually registers a new service instance.
- **`async health() -> dict`**: Aggregates health status from all services.

---

## 3. `EventBus`

Asynchronous event distribution.

- **`async emit(event: str, data: dict = None, source: str = None)`**: Dispatches an event to all subscribers.
- **`on(event: str, priority: int = 50)`**: Decorator to subscribe to an event.
- **`once(event: str)`**: Subscribes for the next occurrence only.

---

## 4. `HookManager`

Synchronous filters and actions for fine-grained extensibility.

- **`apply_filters(hook_name: str, value: Any, **kwargs) -> Any`**: Passes a value through a chain of filter functions.
- **`do_action(hook_name: str, **kwargs)`**: Executes a chain of side-effect actions.

---

## 5. `PermissionEngine`

Evaluates security policies.

- **`check(plugin: str, resource: str, action: str) -> None`**: Validates access and raises `PermissionDenied` if unauthorized.
- **`allows(plugin: str, resource: str, action: str) -> bool`**: Returns boolean status.
