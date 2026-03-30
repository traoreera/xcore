# Creating Plugins

This guide covers everything you need to know about creating XCore plugins, from simple IPC handlers to full REST API endpoints.

## 1. Plugin Structure

A standard XCore plugin requires a specific directory structure:

```text
plugins/my_plugin/
├── plugin.yaml      # Plugin manifest (metadata & configuration)
├── plugin.sig       # Security signature (for trusted mode in production)
└── src/
    └── main.py      # Core logic and entry point
```

## 2. Inter-Process Communication (IPC)

XCore uses a standardized IPC system for communication between the core and plugins:

-   **Core → Plugin**: Via HTTP API calls or internal process signals.
-   **Plugin → Core**: Via the `self.ctx.plugins.call()` method.
-   **Plugin → Plugin**: Also via `self.ctx.plugins.call()`, routed through the kernel for security checks.

### Managing Plugins via CLI

You can manage the plugin lifecycle directly from the command line:

```bash
# List all discovered plugins
xcore plugin list

# Load a specific plugin
xcore plugin load <name>

# Hot-reload a plugin (refreshes code and manifest)
xcore plugin reload <name>

# Unload a plugin
xcore plugin unload <name>
```

## 3. The Manifest (`plugin.yaml`)

The manifest is a YAML file that describes your plugin's metadata, requirements, and security policies.

```yaml
name: my_plugin                    # Unique identifier
version: 1.0.0                    # Semantic version
author: Your Name                  # Author name
description: Plugin description    # Short description

execution_mode: trusted            # trusted | sandboxed
framework_version: ">=2.0"        # Compatible XCore version
entry_point: src/main.py          # Main file path

# Dependencies on other plugins
requires:
  - name: other_plugin
    version: ">=1.5.0"

# Granular service permissions
permissions:
  - resource: "db.*"
    actions: ["read", "write"]
    effect: allow
  - resource: "cache.global"
    actions: ["read"]
    effect: allow

# Resource limits (especially important for sandboxed plugins)
resources:
  timeout_seconds: 30
  max_memory_mb: 256
  rate_limit:
    calls: 1000
    period_seconds: 60
```

## 4. Implementation Styles

### Basic Plugin (Action-Based)

The simplest way to implement a plugin is to inherit from `TrustedBase` and implement the `handle` method.

```python
from xcore.sdk import TrustedBase, ok, error

class Plugin(TrustedBase):
    """A simple calculator plugin."""

    async def handle(self, action: str, payload: dict) -> dict:
        if action == "add":
            result = payload.get("a", 0) + payload.get("b", 0)
            return ok(result=result)

        return error(f"Unknown action: {action}", code="unknown_action")
```

### Advanced Plugin with Auto-Dispatch

Use the `AutoDispatchMixin` and `@action` decorator to automatically route IPC calls to specific methods.

```python
from xcore.sdk import TrustedBase, AutoDispatchMixin, action, ok

class Plugin(AutoDispatchMixin, TrustedBase):

    @action("greet")
    async def say_hello(self, payload: dict):
        name = payload.get("name", "Guest")
        return ok(message=f"Hello, {name}!")
```

### Plugin with HTTP Routes

Expose REST API endpoints by using the `RoutedPlugin` mixin and `@route` decorator. These routes are automatically mounted by XCore.

```python
from xcore.sdk import TrustedBase, RoutedPlugin, route

class Plugin(RoutedPlugin, TrustedBase):

    @route("/hello/{name}", method="GET")
    async def hello_api(self, name: str):
        return {"message": f"Hello, {name}!"}
```
*Note: These routes will be available at `/plugins/my_plugin/hello/{name}`.*

## 5. Using Core Services

XCore provides built-in services for common tasks. Access them using `self.get_service()`.

### Database Access

```python
async def on_load(self):
    self.db = self.get_service("db")

async def get_users(self):
    async with self.db.session() as session:
        result = await session.execute("SELECT * FROM users")
        return result.fetchall()
```

### Cache & Events

```python
async def on_load(self):
    self.cache = self.get_service("cache")
    # Subscribe to an event
    self.ctx.events.on("user.created", self._on_user_created)

async def _on_user_created(self, event):
    # React to the event
    user_email = event.data.get("email")
    await self.cache.set(f"welcome_sent:{user_email}", True)
```

## 6. Plugin Lifecycle Hooks

Override these methods to manage your plugin's lifecycle:

-   **`on_load(self)`**: Called when the plugin is first loaded. Use it for initialization.
-   **`on_reload(self)`**: Called during a hot-reload. Use it to refresh state or connections.
-   **`on_unload(self)`**: Called before the plugin is removed. Use it for cleanup.

## 7. Best Practices

1.  **Strict Typing**: Use Python type hints for better maintainability.
2.  **Input Validation**: Use Pydantic models with the `@validate_payload` decorator for all IPC and HTTP inputs.
3.  **Error Handling**: Always return standardized responses using `ok()` and `error()` helpers.
4.  **Least Privilege**: Only request the permissions your plugin absolutely needs in `plugin.yaml`.
5.  **Documentation**: Include docstrings for your class and all exposed actions/routes.

## Next Steps

-   [Working with Services](services.md)
-   [Security Best Practices](security.md)
-   [Testing Plugins](../development/testing.md)
