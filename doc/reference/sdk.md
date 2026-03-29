# XCore SDK Exhaustive Reference

The XCore SDK is a high-level library designed to facilitate the development of secure, scalable, and maintainable plugins. This reference covers every class, decorator, and utility available to developers.

## 1. Core Plugin Classes

### `TrustedBase`
The primary base class for plugins that run within the main XCore process.

- **Inheritance**: `BasePlugin` -> `TrustedBase`
- **Context Access**: `self.ctx` (of type `PluginContext`) provides access to the global EventBus, PluginSupervisor, and ServiceContainer.
- **Methods**:
    - `async on_load(self) -> None`: Initialization entry point. Initialize your services and state here.
    - `async on_unload(self) -> None`: Cleanup entry point. Close database connections or stop timers here.
    - `async on_reload(self) -> None`: Called when the plugin is hot-reloaded. Defaults to calling `on_unload` then `on_load`.
    - `async handle(self, action: str, payload: dict) -> dict`: The central dispatcher for IPC calls.
    - `get_service(self, name: str) -> Any`: Helper to retrieve a service from the container.

### `BasePlugin`
The low-level interface for all plugin types. Primarily used for internal framework logic or building custom plugin runners.

---

## 2. SDK Decorators

### `@action(name: str)`
Defines a method as an IPC action handler.
- **Usage**: Requires `AutoDispatchMixin`.
- **Logic**: Maps an IPC action string to the decorated method.
- **Example**:
  ```python
  @action("ping")
  async def ping_handler(self, payload: dict):
      return ok(message="pong")
  ```

### `@route(path: str, method: str = "GET", ...)`
Defines a FastAPI route directly on the plugin class.
- **Usage**: Requires `RoutedPlugin` mixin.
- **Parameters**:
    - `path`: URL path (relative to plugin root).
    - `method`: HTTP verb (`GET`, `POST`, `PUT`, `DELETE`, `PATCH`).
    - `tags`: List of strings for OpenAPI categorization.
    - `summary`: Short description for OpenAPI docs.
    - `status_code`: Default response status code.
    - `dependencies`: List of `FastAPI.Depends()`.
    - `permissions`: List of strings for RBAC (e.g., `["admin"]`).
- **Example**:
  ```python
  @route("/items/{id}", method="GET", tags=["inventory"])
  async def get_item(self, id: int):
      return {"id": id, "name": "Tool"}
  ```

### `@require_service(*service_names: str)`
Enforces the availability of specific services before method execution.
- **Logic**: Calls `get_service(name)` for each name provided.
- **Exceptions**: Raises `KeyError` if any service is missing from the container.

### `@validate_payload(schema: Type[BaseModel], type_response="BaseModel", unset=True)`
Automatically validates the IPC `payload` dictionary against a Pydantic model.
- **Parameters**:
    - `schema`: A Pydantic `BaseModel` class.
    - `type_response`: If `"pydantic"`, the handler receives the model instance. If `"dict"`, it receives a dictionary.
    - `unset`: If True, excludes unset fields from the dictionary output.
- **Logic**: Returns an XCore error response with status code 400 if validation fails.

### `@trusted`
Marks a method to ensure it only executes when the plugin is in `trusted` mode.

### `@sandboxed`
Marks a method as compatible with `sandboxed` execution.

---

## 3. Mixins

### `AutoDispatchMixin`
Provides an automatic implementation of the `handle(action, payload)` method.
- **Mechanism**: It scans the class for methods decorated with `@action` and routes incoming calls based on the action name.
- **Fallback**: Returns a standard "unknown_action" error if no match is found.

### `RoutedPlugin`
Enables automatic discovery and mounting of FastAPI routes.
- **Method**: `RouterIn(self) -> APIRouter | None`. This internal method is called by the kernel to collect all `@route` decorated methods and package them into a single `APIRouter`.

---

## 4. Repositories (Data Access)

The SDK implements the Repository Pattern to abstract database operations.

### `BaseAsyncRepository`
Base class for asynchronous database interactions.
- **Backend**: Uses `AsyncSQLAdapter`.
- **Usage**: Typically used with SQLAlchemy or direct async SQL.

### `BaseSyncRepository`
Base class for synchronous database interactions.
- **Backend**: Uses standard `SQLAdapter`.

---

## 5. Security & Authorization

### `RBACChecker(permissions: list[str])`
A FastAPI dependency class used to enforce Role-Based Access Control on plugin routes.

### `@require_role(role: str)`
Decorator to restrict access to a method or route based on a specific user role.

### `@require_permission(permission: str)`
Decorator to restrict access based on a specific granular permission.

---

## 6. Helper Functions

### `ok(**kwargs) -> dict`
Standardized success response.
- **Format**: `{"status": "ok", ...kwargs}`

### `error(msg: str, code: str, status_code: int = 400, **kwargs) -> dict`
Standardized error response.
- **Format**: `{"status": "error", "msg": msg, "code": code, ...kwargs}`

---

## 7. Configuration Objects

### `PluginManifest`
The typed representation of `plugin.yaml`.
- **Attributes**: `name`, `version`, `author`, `execution_mode`, `requires`, `permissions`, `resources`, `runtime`, `filesystem`, `env`.

### `ResourceConfig`
- **Attributes**: `timeout_seconds`, `max_memory_mb`, `max_disk_mb`, `rate_limit`.

### `RuntimeConfig`
- **Attributes**: `health_check` (enabled, interval, timeout), `retry` (max_attempts, backoff).
