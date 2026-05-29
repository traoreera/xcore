---
title: Service Management
description: Control the lifecycle of individual system services without restarting the application.
icon: material/server-network
---

# Service Management

Control the lifecycle of individual system services (Databases, Cache, Extensions) without affecting the rest of the application.

## Service Operations

The `manager services` command group allows you to manage services defined in the `services` section of `integration.yaml`.

### List Services

See all configured services, their initialization status, and current health:

```bash
xcli manager services list

# Output:
#  Name        Type         Status    Version    Uptime
#  ────────────────────────────────────────────────────
#  db          postgresql   UP        14.1       3h 22m
#  cache       redis        UP        7.0.5      3h 22m
#  scheduler   apscheduler  UP        3.10.4     3h 22m
#  email       custom       DOWN      —          —
```

!!! tip "Live View"
    Use the `--watch` (or `-w`) flag to keep the table updated in real-time:
    ```bash
    xcli manager services list --watch
    ```

### Reload a Service

Force a service to re-read its configuration and reconnect. Useful for rotating database credentials or updating API keys.

```bash
xcli manager services reload db
# Reloading service 'db'... done (1.2s)
```

### Unload a Service

Temporarily disable a service and shut down its connections.

```bash
xcli manager services unload cache
# WARNING: 2 plugins depend on 'cache'. Proceed? [y/N]: y
# Service 'cache' unloaded.
```

!!! warning "Dependency Impact"
    Be careful when unloading core services like `db` or `cache`. Xcore will warn you if active plugins depend on them. Plugin calls that require the service will fail until it is reloaded.

## Custom Extensions

Services defined under `services.extensions` support hot-swapping and on-the-fly reload:

```yaml title="integration.yaml"
services:
  extensions:
    email:
      module: "myapp.services.email:EmailService"
      config:
        smtp_host: "smtp.gmail.com"
        smtp_port: 587
```

Reload after changing SMTP credentials:

```bash
xcli manager services reload email
# EmailService reconnected to smtp.gmail.com:587
```

## Service Status Lifecycle

```text
STOPPED → INITIALIZING → READY ↔ DEGRADED
                ↓
            FAILED
```

| Status | Meaning |
|--------|---------|
| `READY` | Service initialized and passing health checks |
| `DEGRADED` | Service started but health check failing |
| `FAILED` | Service failed to initialize or crashed |
| `STOPPED` | Service intentionally unloaded |

!!! tip "Service Container"
    All services are managed by a central `ServiceContainer`. The `manager services` commands interact with this container to ensure thread-safe operations.

## See Also

[Real-time Monitoring](monitoring.md)
:   Full dashboard and resource profiling.

[Custom Services](../../services/custom-services.md)
:   Build and register your own service providers.
