# Real-time Monitoring

`xcorecli` provides powerful monitoring tools to help you keep an eye on your system's performance and health.

## The `top` Dashboard

The flagship monitoring tool is `xcli manager top`. It provides a comprehensive, real-time dashboard inside your terminal.

```bash title="Launch Dashboard"
xcli manager top
```

### Dashboard Tabs:
1. **System**: CPU, Memory, Disk, and Network usage.
2. **Services**: Status and uptime of databases, cache, and API.
3. **Workers**: Active Celery tasks and worker health.
4. **Plugins**: Resource usage per plugin.

## Resource Profiling

For a more data-focused view of resource consumption:

```bash title="Resource Summary"
xcli manager resources
```

This command generates a detailed report of which components are consuming the most memory and CPU cycles. Use the `--watch` flag for a live-updating table.

## Metrics & Logs

### Metrics

If metrics are enabled in `integration.yaml`, you can view a snapshot of counters and gauges:

```bash
xcli manager metrics
```

### Unified Logs

Instead of tailing multiple files, use the manager's log viewer to see a merged stream of application, worker, and plugin logs.

```bash title="Follow Logs"
xcli manager logs --follow
```

!!! tip "Filtering Logs"
    You can filter logs by a specific plugin name to reduce noise:
    ```bash
    xcli manager logs my-plugin --follow
    ```

!!! info "Configuration"
    Observability settings are defined in the `observability` section of your `integration.yaml`.
    ```yaml
    observability:
      logging:
        file: "log/xcore.log"
    ```
