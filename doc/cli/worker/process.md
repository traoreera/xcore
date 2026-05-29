---
title: Worker Process Management
description: Fine-grained control over multiple Celery worker instances, status, and logs.
icon: material/cog-play
---

# Worker Process Management

The `worker process` sub-app provides fine-grained control over multiple background worker instances.

## Process Lifecycle

### Start Multiple Instances

Start several worker instances at once, each with its own hostname:

```bash title="Start 4 worker instances"
xcli worker process start --count 4
```

```bash title="With specific queues and concurrency"
xcli worker process start \
  --queues priority,emails \
  --concurrency 8 \
  --detach
```

### Start Flags

| Flag | Description |
|------|-------------|
| `--count N` | Number of worker instances to start (default: 1) |
| `--queues` / `-Q` | Comma-separated list of queues |
| `--concurrency N` | Child processes per worker instance |
| `--detach` / `-d` | Run workers as background processes |

### Stop All Workers

Gracefully shut down all running worker processes:

```bash
xcli worker process stop
# Sending shutdown signal to 4 workers...
# worker@server-01  stopped (grace: 2.1s)
# worker@server-02  stopped (grace: 1.8s)
# worker@server-03  stopped (grace: 2.4s)
# worker@server-04  stopped (grace: 1.9s)
```

### Restart All Workers

Stop and then restart all worker processes — applies code changes without server downtime:

```bash
xcli worker process restart
# Stopping 4 workers... done
# Starting 4 workers... done
```

## Monitoring & Logs

### Status Table

See a detailed table of running worker processes including their PIDs, uptime, and resource usage:

```bash title="Process Status"
xcli worker process status

# Worker Process Status
# ────────────────────────────────────────────────────
#  Hostname       PID     Queues          CPU %   RSS MB   Uptime
#  ──────────────────────────────────────────────────────────────
#  worker@srv-01  18432   default,email   2.1%    142.3    2h 14m
#  worker@srv-02  18433   heavy           8.7%    312.1    2h 14m
#  worker@srv-03  18434   default         1.4%    138.9    2h 14m
#  worker@srv-04  18435   default         1.2%    141.2    2h 14m
```

### Worker Logs

Tail the logs for worker processes:

```bash title="Follow worker logs"
xcli worker process logs --follow

# Filter to a specific worker
xcli worker process logs --lines 100 --worker worker@srv-02
```

!!! note "Background Processes"
    The `status` and `logs` commands are most useful when workers are started with `--detach`, since stdout is not visible directly.
