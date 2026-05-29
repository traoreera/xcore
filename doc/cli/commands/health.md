---
title: Health & Services
description: Monitor service connectivity, plugin integrity, and environment health.
icon: material/heart-pulse
---

# Health & Services

Monitoring the status of your `xcore` ecosystem is vital for maintaining a healthy production environment.

## Global Health Check

The `health` command performs an exhaustive check of all configured services and components.

```bash title="Check Everything"
xcli health
```

This command validates:

- **Connectivity**: Database and Redis connections.
- **Plugins**: Integrity, signature validity, and loading status.
- **Worker**: Celery/XWorker availability.
- **Environment**: Python version and required dependencies.

### Example output

```text
XCore Health Check
──────────────────────────────────────────────────
 service      status     latency
──────────────────────────────────────────────────
 db (sqlite)  UP         1.2 ms
 cache (mem)  UP         0.1 ms
 scheduler    UP         —
 worker       DEGRADED   broker unreachable
──────────────────────────────────────────────────
 Plugins (3 loaded)
   hello_plugin    OK    v1.0.0
   auth_plugin     OK    v2.1.0
   billing_engine  WARN  signature missing
──────────────────────────────────────────────────
Exit code: 1  (1 degraded, 1 warning)
```

!!! danger "Service Failures"
    If any critical service is down, `xcli health` returns a non-zero exit code, making it suitable for CI/CD health gates.

```bash title="Use in CI/CD"
xcli health || exit 1
```

## Service Status

For a more focused view of system services, use the `services` command.

```bash title="Service Overview"
xcli services
```

### Example output

```text
 Service     Type         Status    Uptime
─────────────────────────────────────────
 db          postgresql   UP        2h 14m
 cache       redis        UP        2h 14m
 scheduler   apscheduler  UP        2h 14m
 email       custom       DOWN      —
─────────────────────────────────────────
```

**Status values:**

| Status | Meaning |
|--------|---------|
| `UP` | Service initialized and healthy |
| `DOWN` | Service failed to start or crashed |
| `DEGRADED` | Service started but reporting errors |

!!! tip "Service Management"
    Individual services can be managed via the `manager services` command group. See [Service Management](../manager/services.md) for details.

## Troubleshooting

If `health` reports errors:

```bash
# 1. Check the logs for the specific error
xcli manager logs --follow

# 2. Validate your configuration file
xcli config validate

# 3. Reload a specific failing service
xcli manager services reload db

# 4. Restart the entire server
xcli manager stop
xcli manager start --reload
```

## See Also

[Manager Monitoring](../manager/monitoring.md)
:   Real-time dashboard and resource profiling.

[Service Management](../manager/services.md)
:   Reload, unload, and inspect individual services.
