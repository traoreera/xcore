# XCore SDK Reference

The XCore SDK is a high-level library designed to facilitate the development of secure, scalable, and maintainable plugins.

---

## 1. Core Plugin Classes

### `TrustedBase`
The primary base class for plugins that run within the main XCore process.
- **`async on_load(self) -> None`**: Entry point for initialization. Initialize services and state here.
- **`async on_unload(self) -> None`**: Entry point for cleanup. Close connections or stop timers here.
- **`async handle(self, action: str, payload: dict) -> dict`**: Low-level IPC handler. Use `AutoDispatchMixin` for a cleaner approach.
- **`get_service(self, name: str) -> Any`**: Helper to retrieve a public service from the kernel.

### `BasePlugin`
The low-level interface for all plugin types. Used for internal framework logic or building custom plugin runners.

---

## 2. Decorators

### `@action(name: str)`
Defines a method as an IPC action handler.
- **Usage**: Requires `AutoDispatchMixin`.
- **Logic**: Maps an IPC action string to the decorated method.

### `@route(path: str, method: str = "GET", ...)`
Defines a FastAPI route directly on the plugin class.
- **Usage**: Requires `RoutedPlugin` mixin.
- **Parameters**: `path`, `method`, `tags`, `summary`, `status_code`, `dependencies`, `permissions`.

### `@validate_payload(schema: Type[BaseModel], type_response="dict")`
Automatically validates the IPC `payload` against a Pydantic model.
- **`type_response="dict"`**: Passes a validated dictionary to the handler.
- **`type_response="pydantic"`**: Passes the model instance to the handler.

### `@trusted` / `@sandboxed`
Markers to ensure a method only executes in the specified mode.

---

## 3. Mixins

- **`AutoDispatchMixin`**: Provides an automatic implementation of `handle()` by routing to `@action` methods.
- **`RoutedPlugin`**: Enables automatic discovery and mounting of FastAPI routes.

---

## 4. Repositories & Data Access

### `BaseAsyncRepository`
Base class for asynchronous database interactions.
- **Usage**: Inherit and define your models to get standard CRUD operations.

### `RBACChecker`
FastAPI dependency used to enforce Role-Based Access Control on plugin routes.

---

## 5. Helper Functions

- **`ok(**kwargs) -> dict`**: Standard success response: `{"status": "ok", ...}`.
- **`error(msg: str, code: str, status_code: int = 400) -> dict`**: Standard error response: `{"status": "error", "msg": msg, "code": code}`.
