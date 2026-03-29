# Creating Services & Extensions

This guide explains how to create your own services and extensions within the XCore framework. This allows you to share complex logic, connections, or state between multiple plugins.

## 1. Services vs. Extensions

-   **Services**: Core-level components managed by the `ServiceContainer`. They are typically initialized before any plugins are loaded and are often used for shared infrastructure (e.g., a specific database connection or an external API client).
-   **Extensions**: A specialized type of service that is loaded from a specific directory and can be dynamically discovered. Use extensions for high-level business logic that needs to be shared across multiple plugins.

## 2. Creating a Custom Service Provider

Custom services are typically implemented as `BaseService` classes and registered in the `ServiceContainer`.

### Step 1: Implement the Service

```python
from xcore.services.base import BaseService, ServiceStatus

class MyCustomService(BaseService):
    name = "my_custom_service"

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.client = None

    async def init(self) -> None:
        self._status = ServiceStatus.INITIALIZING
        # Initialize client, connection, etc.
        self.client = MyExternalClient(self.config.get("api_key"))
        self._status = ServiceStatus.READY
        print(f"Service {self.name} initialized")

    async def shutdown(self) -> None:
        if self.client:
            await self.client.close()
        self._status = ServiceStatus.STOPPED

    async def health_check(self) -> tuple[bool, str]:
        if self.client and await self.client.ping():
            return True, "ok"
        return False, "client unreachable"

    async def do_something(self, data):
        """Custom method for the service."""
        return await self.client.process(data)
```

### Step 2: Register the Service

In your `app.py`, you can manually register your service before calling `xcore.boot()`:

```python
xcore = Xcore(config_path="xcore.yaml")
custom_service = MyCustomService(my_config)

# Register before boot
xcore.services.register_service("my_service", custom_service)

# Alternatively, use a ServiceProvider for lazy-loading
class MyServiceProvider:
    def provide(self, name: str):
        if name == "my_service":
            return custom_service
        return None

xcore.services.register_provider("my_provider", MyServiceProvider())
```

## 3. Creating an Extension

Extensions are automatically loaded from the `extensions/` directory if configured in `xcore.yaml`.

### Step 1: Create the Extension Structure

```bash
extensions/
  my_extension/
    __init__.py
    extension.py
```

### Step 2: Implement the Extension

```python
# extensions/my_extension/extension.py

class MyExtension:
    """A custom extension shared between plugins."""

    def __init__(self, config):
        self.config = config

    async def init(self):
        # Initialization logic
        print("Extension initialized!")

    def get_info(self):
        return {"version": "1.0", "status": "active"}
```

### Step 3: Configure in `xcore.yaml`

```yaml
services:
  extensions:
    directory: "extensions/"
    enabled: true
    configs:
      my_extension:
        api_key: "secret_123"
```

### Step 4: Use the Extension in a Plugin

```python
class MyPlugin(TrustedBase):
    async def on_load(self):
        # Extensions are prefixed with 'ext.'
        self.my_ext = self.get_service("ext.my_extension")
        print(self.my_ext.get_info())
```

## 4. Best Practices

1.  **Lazy Loading**: For services that are not used by every plugin, consider using a `ServiceProvider` to initialize them only when first requested.
2.  **Health Checks**: Always implement `health_check()` to allow the kernel to monitor the status of your service.
3.  **Graceful Shutdown**: Ensure your `shutdown()` method properly releases all resources (database connections, file handles, etc.).
4.  **Logging**: Use the standard XCore logging (available via `self.logger` or `logging.getLogger("xcore.services.custom")`).
5.  **Type Safety**: Provide type hints for your service methods to improve the developer experience for plugin authors.
