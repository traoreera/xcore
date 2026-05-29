---
title: Real-time Monitoring
description: Terminal dashboard, resource profiling, metrics, and unified log streaming.
icon: material/monitor-eye
---

# Real-time Monitoring

`xcorecli` provides powerful monitoring tools to help you keep an eye on your system's performance and health.

## The `top` Dashboard

The flagship monitoring tool is `xcli manager top`. It provides a comprehensive, real-time dashboard inside your terminal.

```bash title="Launch Dashboard"
xcli manager top
```

### Dashboard Tabs

| Tab | Contents |
|-----|----------|
| **System** | CPU, Memory, Disk, and Network usage for the whole process |
| **Services** | Status and uptime of databases, cache, and API |
| **Workers** | Active Celery tasks and worker health |
| **Plugins** | Per-plugin RSS memory, CPU %, and call counts |

Press ++tab++ to switch between tabs, ++q++ to quit.

## Resource Profiling

For a data-focused view of resource consumption per component:

```bash title="Resource Summary"
xcli manager resources

# Output:
#  Component          CPU %    RSS MB   Calls/s
#  ──────────────────────────────────────────
#  kernel             0.4 %    48.2     —
#  auth_plugin        0.1 %    12.1     142
#  billing_engine     1.2 %    38.7     89
#  analytics_plugin   0.3 %    21.4     314
```

Use `--watch` for a continuously refreshed table:

```bash
xcli manager resources --watch
```

## Metrics & Logs

### Metrics Snapshot

If metrics are enabled in `integration.yaml`, view a snapshot of all counters and gauges:

```bash
xcli manager metrics

# Output:
#  Metric                         Value    Labels
#  ─────────────────────────────────────────────────────
#  plugin_calls_total             14 203   plugin=auth
#  plugin_calls_total              8 991   plugin=billing
#  action_duration_seconds_p99    0.042s   plugin=auth
#  cache_hit_ratio                0.87     —
```

Enable metrics in `integration.yaml`:

```yaml
observability:
  metrics:
    enabled: true
    export_interval: 60
```

### Unified Log Stream

Instead of tailing multiple files, use the manager's log viewer to see a merged stream of application, worker, and plugin logs.

```bash title="Follow all logs"
xcli manager logs --follow
```

```bash title="Filter by plugin"
xcli manager logs auth_plugin --follow
```

```bash title="Filter by log level"
xcli manager logs --level ERROR --follow
```

### Log Configuration

```yaml title="integration.yaml"
observability:
  logging:
    level: INFO
    format: "json"          # "text" | "json"
    file: "log/xcore.log"   # enables file rotation
```

## See Also

[Service Management](services.md)
:   Reload and control individual services.

[Observability Guide](../../observability/observability.md)
:   Configure tracing, metrics, and health checks.
