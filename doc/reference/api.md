# API Reference

Complete API reference for XCore classes and interfaces.

## Xcore

Main orchestrator class.

```python
from xcore import Xcore

class Xcore:
    def __init__(self, config_path: str | None = None)
    async def boot(self, app=None) -> "Xcore"
    async def shutdown(self) -> None
```

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `services` | `ServiceContainer` | Service container |
| `plugins` | `PluginSupervisor` | Plugin supervisor |
| `events` | `EventBus` | Event bus |
| `hooks` | `HookManager` | Hook manager |
| `registry` | `PluginRegistry` | Plugin registry |

### Methods

#### `__init__`

```python
def __init__(self, config_path: str | None = None)
```

Initialize XCore instance.

**Parameters**:
- `config_path`: Path to YAML configuration file (default: `integration.yaml`)

**Example**:
```python
xcore = Xcore(config_path="production.yaml")
```

#### `boot`

```python
async def boot(self, app=None) -> "Xcore"
```

Start all subsystems.

**Parameters**:
- `app`: FastAPI application instance (optional)

**Returns**:
- Self for chaining

**Example**:
```python
@app.on_event("startup")
async def startup():
    await xcore.boot(app)
```

#### `shutdown`

```python
async def shutdown(self) -> None
```

Gracefully shutdown all subsystems.

**Example**:
```python
@app.on_event("shutdown")
async def shutdown():
    await xcore.shutdown()
```

---

## TrustedBase

Base class for trusted plugins.

```python
from xcore.sdk import TrustedBase

class Plugin(TrustedBase):
    ...
```

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `ctx` | `PluginContext` | Plugin context (injected) |

### Methods

#### `get_service`

```python
def get_service(self, name: str) -> Any
```

Get a service by name.

**Parameters**:
- `name`: Service name

**Returns**:
- Service instance

**Raises**:
- `KeyError`: If service not found
- `RuntimeError`: If context not injected

**Example**:
```python
db = self.get_service("db")
cache = self.get_service("cache")
```

#### `get_router`

```python
def get_router(self) -> APIRouter | None
```

Return custom FastAPI router.

Override to expose HTTP endpoints.

**Returns**:
- `APIRouter` instance or `None`

**Example**:
```python
def get_router(self):
    from fastapi import APIRouter
    router = APIRouter(prefix="/items")

    @router.get("/")
    async def list_items():
        return []

    return router
```

#### `handle`

```python
@abstractmethod
async def handle(self, action: str, payload: dict) -> dict
```

Handle IPC actions.

**Parameters**:
- `action`: Action name
- `payload`: Action parameters

**Returns**:
- Response dictionary

**Example**:
```python
async def handle(self, action: str, payload: dict) -> dict:
    if action == "ping":
        return {"status": "ok", "message": "pong"}
    return {"status": "error", "msg": "Unknown action"}
```

### Lifecycle Hooks

#### `on_load`

```python
async def on_load(self) -> None
```

Called when plugin is loaded.

**Example**:
```python
async def on_load(self) -> None:
    self.db = self.get_service("db")
    print("Plugin loaded")
```

#### `on_unload`

```python
async def on_unload(self) -> None
```

Called when plugin is unloaded.

**Example**:
```python
async def on_unload(self) -> None:
    print("Plugin unloaded")
```

#### `on_reload`

```python
async def on_reload(self) -> None
```

Called when plugin is reloaded.

**Example**:
```python
async def on_reload(self) -> None:
    print("Plugin reloading")
```

---

## PluginSupervisor

High-level plugin management interface.

```python
from xcore.kernel.runtime.supervisor import PluginSupervisor
```

### Methods

#### `call`

```python
async def call(
    self,
    plugin_name: str,
    action: str,
    payload: dict
) -> dict
```

Call a plugin action.

**Parameters**:
- `plugin_name`: Target plugin name
- `action`: Action name
- `payload`: Action parameters

**Returns**:
- Response dictionary

**Example**:
```python
result = await supervisor.call(
    "my_plugin",
    "process",
    {"data": "value"}
)
```

#### `load`

```python
async def load(self, plugin_name: str) -> None
```

Load a plugin.

**Parameters**:
- `plugin_name`: Plugin name

#### `unload`

```python
async def unload(self, plugin_name: str) -> None
```

Unload a plugin.

**Parameters**:
- `plugin_name`: Plugin name

#### `reload`

```python
async def reload(self, plugin_name: str) -> None
```

Reload a plugin.

**Parameters**:
- `plugin_name`: Plugin name

#### `status`

```python
def status(self) -> dict
```

Get plugin status.

**Returns**:
```python
{
    "plugins": [
        {
            "name": "plugin_name",
            "version": "1.0.0",
            "mode": "trusted",
            "state": "loaded"
        }
    ],
    "count": 1
}
```

#### `list_plugins`

```python
def list_plugins(self) -> list[str]
```

List loaded plugin names.

**Returns**:
- List of plugin names

---

## EventBus

Event subscription and emission.

```python
from xcore.kernel.events.bus import EventBus, Event
```

### Methods

#### `on`

```python
def on(
    self,
    event_name: str,
    priority: int = 50,
    name: str | None = None
) -> Callable
```

Subscribe to an event.

**Parameters**:
- `event_name`: Event name pattern
- `priority`: Handler priority (0-100, higher first)
- `name`: Handler identifier

**Returns**:
- Decorator function

**Example**:
```python
@events.on("user.created", priority=50)
async def on_user_created(event: Event):
    print(event.data)
```

#### `once`

```python
def once(
    self,
    event_name: str,
    priority: int = 50
) -> Callable
```

Subscribe once to an event.

**Parameters**:
- `event_name`: Event name
- `priority`: Handler priority

**Example**:
```python
@events.once("system.ready")
async def on_ready(event: Event):
    print("System ready!")
```

#### `subscribe`

```python
def subscribe(
    self,
    event_name: str,
    handler: Callable,
    priority: int = 50,
    once: bool = False,
    name: str | None = None
) -> None
```

Subscribe a handler to an event.

**Parameters**:
- `event_name`: Event name
- `handler`: Callback function
- `priority`: Handler priority
- `once`: Remove after first execution
- `name`: Handler name

#### `unsubscribe`

```python
def unsubscribe(self, event_name: str, handler: Callable) -> None
```

Unsubscribe a handler.

**Parameters**:
- `event_name`: Event name
- `handler`: Handler function

#### `emit`

```python
async def emit(
    self,
    event_name: str,
    data: dict[str, Any] | None = None,
    source: str | None = None,
    gather: bool = True
) -> list[Any]
```

Emit an event.

**Parameters**:
- `event_name`: Event name
- `data`: Event data
- `source`: Event source
- `gather`: Execute handlers in parallel

**Returns**:
- List of handler results

**Example**:
```python
await events.emit("user.created", {
    "user_id": "123",
    "email": "user@example.com"
})
```

#### `emit_sync`

```python
def emit_sync(
    self,
    event_name: str,
    data: dict[str, Any] | None = None
) -> None
```

Fire-and-forget event emission.

**Parameters**:
- `event_name`: Event name
- `data`: Event data

#### `clear`

```python
def clear(self, event_name: str | None = None) -> None
```

Clear event handlers.

**Parameters**:
- `event_name`: Specific event or all if None

### Event Object

```python
@dataclass
class Event:
    name: str
    data: dict[str, Any]
    source: str | None
    propagate: bool
    cancelled: bool

    def stop(self) -> None      # Stop propagation
    def cancel(self) -> None     # Cancel event
```

---

## ServiceContainer

Service management and access.

```python
from xcore.services.container import ServiceContainer
```

### Methods

#### `init`

```python
async def init(self) -> None
```

Initialize all services.

#### `shutdown`

```python
async def shutdown(self) -> None
```

Shutdown all services.

#### `get`

```python
def get(self, name: str) -> Any
```

Get a service by name.

**Parameters**:
- `name`: Service name

**Returns**:
- Service instance

**Raises**:
- `KeyError`: If service not found

**Example**:
```python
db = container.get("db")
cache = container.get("cache")
```

#### `get_or_none`

```python
def get_or_none(self, name: str) -> Any | None
```

Get a service or None.

**Parameters**:
- `name`: Service name

**Returns**:
- Service instance or None

#### `has`

```python
def has(self, name: str) -> bool
```

Check if service exists.

**Parameters**:
- `name`: Service name

**Returns**:
- True if service exists

#### `health`

```python
async def health(self) -> dict[str, Any]
```

Health check all services.

**Returns**:
```python
{
    "ok": True,
    "services": {
        "database": {"ok": True, "msg": "Connected"},
        "cache": {"ok": True, "msg": "Connected"}
    }
}
```

#### `status`

```python
def status(self) -> dict[str, Any]
```

Get service status.

**Returns**:
```python
{
    "services": {
        "database": {...},
        "cache": {...}
    },
    "registered_keys": ["db", "cache", "scheduler"]
}
```

---

## CacheService

Cache operations.

```python
from xcore.services.cache.service import CacheService
```

### Methods

#### `get`

```python
async def get(self, key: str) -> Any | None
```

Get value from cache.

**Parameters**:
- `key`: Cache key

**Returns**:
- Cached value or None

#### `set`

```python
async def set(
    self,
    key: str,
    value: Any,
    ttl: int | None = None
) -> None
```

Set cache value.

**Parameters**:
- `key`: Cache key
- `value`: Value to cache
- `ttl`: Time-to-live in seconds

#### `delete`

```python
async def delete(self, key: str) -> None
```

Delete cache key.

**Parameters**:
- `key`: Cache key

#### `exists`

```python
async def exists(self, key: str) -> bool
```

Check if key exists.

**Parameters**:
- `key`: Cache key

**Returns**:
- True if key exists

#### `get_or_set`

```python
async def get_or_set(
    self,
    key: str,
    factory: Callable[[], Any],
    ttl: int | None = None
) -> Any
```

Get or compute and cache value.

**Parameters**:
- `key`: Cache key
- `factory`: Function to compute value if not cached
- `ttl`: Time-to-live

**Example**:
```python
data = await cache.get_or_set(
    "expensive_data",
    factory=lambda: fetch_from_database(),
    ttl=300
)
```

---

## Utility Functions

### ok

```python
from xcore.kernel.api.contract import ok

def ok(data: dict | None = None, **kwargs) -> dict
```

Create success response.

**Example**:
```python
return ok(message="Success", id="123")
# Returns: {"status": "ok", "message": "Success", "id": "123"}
```

### error

```python
from xcore.kernel.api.contract import error

def error(
    msg: str,
    code: str | None = None,
    **kwargs
) -> dict
```

Create error response.

**Example**:
```python
return error("Not found", code="not_found", status_code=404)
# Returns: {"status": "error", "msg": "Not found", "code": "not_found"}
```

---

## Exceptions

### RateLimitExceeded

```python
from xcore.kernel.sandbox.limits import RateLimitExceeded

class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""
    pass
```

### PluginError

```python
from xcore.kernel.runtime.loader import PluginError

class PluginError(Exception):
    """Base plugin error."""
    pass
```

### ValidationError

```python
from xcore.kernel.security.validation import ValidationError

class ValidationError(Exception):
    """Plugin validation error."""
    pass
```

## Type Definitions

```python
from typing import Any, Protocol

class BasePlugin(Protocol):
    """Plugin protocol."""
    async def handle(self, action: str, payload: dict) -> dict: ...

class ExecutionMode(str, Enum):
    TRUSTED = "trusted"
    SANDBOXED = "sandboxed"
    LEGACY = "legacy"
```
