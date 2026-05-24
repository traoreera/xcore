---
title: Custom Services
description: How to extend Xcore by developing and registering your own service providers.
icon: material/puzzle-plus
---

# Custom Services

While Xcore provides built-in services for Databases, Cache, and Scheduling, you can extend the framework by creating your own **Custom Services** (also known as Extensions). Custom services follow the same lifecycle as core services and are automatically injected into the service container.

---

### Key Concepts

#### The `BaseService` Contract
A custom service should inherit from `xcore.services.base.BaseService` and implement the standard lifecycle methods. This ensures that Xcore can manage the service's startup, shutdown, and health monitoring.

#### The `extensions` Configuration
Custom services are registered in the global `xcore.yaml` file under the `services.extensions` block. Xcore uses a dynamic loader to instantiate these classes at boot time.

---

### Practical Guide

#### 1. Implementation
Create a new Python class that implements the `BaseService` contract.

```python linenums="1" title="myapp/services/email.py"
from xcore.services.base import BaseService, ServiceStatus

class EmailService(BaseService):
    name = "email"

    def __init__(self, config: dict):
        super().__init__()
        self._host = config.get("smtp_host")
        self._port = config.get("smtp_port")
        self._client = None

    async def init(self):
        self._status = ServiceStatus.INITIALIZING
        # Initialize your client here
        self._client = await self._connect_smtp(self._host, self._port)
        self._status = ServiceStatus.READY

    async def shutdown(self):
        if self._client:
            await self._client.close()
        self._status = ServiceStatus.STOPPED

    async def health_check(self) -> tuple[bool, str]:
        if self._status == ServiceStatus.READY:
            return True, "SMTP connection active"
        return False, "SMTP disconnected"

    def status(self) -> dict:
        return {"host": self._host, "status": self._status.value}

    async def send(self, to, subject, body):
        # Your custom service logic
        pass
```

#### 2. Registration
Register your service in the `xcore.yaml` file.

```yaml linenums="1" title="xcore.yaml"
services:
  extensions:
    my_mailer:                  # (1)!
      module: "myapp.services.email:EmailService" # (2)!
      config:                   # (3)!
        smtp_host: "smtp.gmail.com"
        smtp_port: 587
```

1.  **Service Key**: The name used to retrieve the service from the container.
2.  **Module Path**: Format `package.module:ClassName`.
3.  **Config**: Passed as a dictionary to the class constructor.

#### 3. Usage in a Plugin
Once registered, you can retrieve your custom service just like a core service.

```python linenums="1"
class Plugin(TrustedBase):
    async def on_load(self):
        # Use get_service_as for full IDE support
        from myapp.services.email import EmailService
        self.mailer = self.get_service_as("my_mailer", EmailService)

    async def handle(self, action, payload):
        await self.mailer.send(...)
        return ok()
```

---

### API Reference

#### `BaseService` Methods to Implement
| Method | Return Type | Description |
|--------|-------------|-------------|
| `init()` | `None` | Asynchronous initialization (connections, cache warmup). |
| `shutdown()`| `None` | Asynchronous cleanup (closing connections). |
| `health_check()`| `tuple[bool, str]` | Used by the global health monitoring system. |
| `status()` | `dict` | Metadata exposed via the CLI `services status` command. |

---

### Common Errors & Pitfalls

!!! danger "ImportError during Registration"
    If the `module` path in `xcore.yaml` is incorrect or the package is not in the Python path, the framework will log an error and skip the extension.
    **Check**: Verify you can run `from myapp.services.email import EmailService` in a standard Python shell.

!!! warning "Synchronous Blocking"
    Like plugins, custom services must be asynchronous. Do not perform blocking I/O inside `init()` or your service methods.

!!! failure "Status not updated"
    If you forget to set `self._status = ServiceStatus.READY` at the end of `init()`, the `ExtensionLoader` will assume the service failed to start.

---

### Best Practices

!!! success "Use Environment Variables"
    Always use `${VAR}` substitution in your `extensions` config for sensitive data like API keys or hostnames.

!!! tip "Granular Health Checks"
    Your `health_check()` should be as fast as possible. Avoid heavy queries; prefer a simple "ping" or checking a local connection flag.
