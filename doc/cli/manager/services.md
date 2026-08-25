# Service Management

Control the lifecycle of individual system services (Databases, Cache, Extensions) without affecting the rest of the application.

## Service Operations

The `manager services` command group allows you to manage services defined in the `services` section of `integration.yaml`.

### List Services

See all configured services, their initialization status, and current health.

```bash
xcli manager services list
```

!!! tip "Live View"
    Use the `--watch` (or `-w`) flag to keep the table updated in real-time.
    ```bash
    xcli manager services list --watch
    ```

### Reload a Service

Force a service to re-read its configuration and reconnect. Useful for rotating database credentials or updating API keys.

```bash
xcli manager services reload db
```

### Unload/Disable a Service

Temporarily disable a service and shut down its connections.

```bash
xcli manager services unload cache
```

!!! warning "Dependencies"
    Be careful when unloading core services like `db` or `redis_db`, as most plugins and internal components depend on them.

## Dynamic Extensions

Services defined under `services.extensions` can often be hot-swapped or reloaded on the fly.

```yaml
services:
  extensions:
    email:
      module: extensions.email.service:EmailService
```

You can reload this extension using:
```bash
xcli manager services reload email
```

!!! tip "Service Container"
    All services are managed by a central `ServiceContainer`. The `manager` commands interact with this container to ensure thread-safe operations.
