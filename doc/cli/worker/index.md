---
title: Worker Orchestration
description: Manage Celery workers for distributed background task processing.
icon: material/worker
---

# Worker Orchestration

`xcore` integrates with **Celery** to handle background tasks, scheduled jobs, and asynchronous processing.

## Overview

The `worker` command group manages the lifecycle of your background processing fleet.

| Command | Description |
|---------|-------------|
| `start` | Launch a Celery worker |
| `beat` | Start the periodic task scheduler (APScheduler) |
| `inspect` | Check worker health and registered tasks |
| `purge` | Clear all messages from a queue |
| `process` | Fine-grained process management (see below) |

## Managing Workers

### Start a Worker

```bash title="Default start"
xcli worker start
```

```bash title="With queues and concurrency"
xcli worker start --queues default,email,heavy --concurrency 4
```

### Inspect Workers

Check which worker nodes are online and what tasks they can run:

```bash title="Inspect active workers"
xcli worker inspect

# Active workers:
#   worker@server-01   — queues: default, email   tasks: 3 active
#   worker@server-02   — queues: heavy             tasks: 1 active
#
# Registered tasks:
#   image_processing.resize
#   report.generate_pdf
#   email.send_batch
```

### Purging Queues

Clear a queue if it has accumulated stale or unwanted tasks:

```bash
xcli worker purge default
# WARNING: This will delete all tasks in queue 'default'. Continue? [y/N]: y
# Purged 142 tasks from queue 'default'.
```

## Periodic Tasks (Beat)

Start the Celery Beat scheduler that triggers recurring tasks:

```bash
xcli worker beat
# Starting Celery Beat scheduler...
# Next jobs:
#   global_sync   every 1h   — next run in 42m
#   daily_report  0 9 * * *  — next run in 14h
```

Configure static jobs in `integration.yaml`:

```yaml title="integration.yaml — scheduler jobs"
services:
  scheduler:
    jobs:
      - id: "global_sync"
        func: "myapp.tasks:sync_external_data"
        trigger: "interval"
        hours: 1
      - id: "daily_report"
        func: "myapp.tasks:generate_report"
        trigger: "cron"
        hour: 9
        minute: 0
```

## Worker Configuration

```yaml title="integration.yaml — xworker section"
services:
  xworker:
    enabled: true
    broker_url: "redis://localhost:6379/0"
    result_backend: "redis://localhost:6379/0"
    queues: ["default", "email", "heavy"]
    concurrency: 4
    modules:
      - "plugins.billing_engine.tasks"
      - "plugins.email_plugin.tasks"
```

!!! tip "Queue Separation"
    Use dedicated queues for different task types to scale workers independently:
    - `default` — general tasks
    - `email` — transactional email sending
    - `heavy` — CPU-intensive processing (reports, image resizing)

## See Also

[Process Management](process.md)
:   Start, stop, and monitor multiple worker instances.

[XWorker Service](../../services/xworker.md)
:   Define `@task` decorators and dispatch tasks from plugins.
