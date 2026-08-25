# Worker Orchestration

`xcore` integrates with **Celery** to handle background tasks, scheduled jobs, and asynchronous processing.

## Overview

The `worker` command group allows you to manage the lifecycle of your background processing fleet.

### Key Commands

- **`start`**: Launch a Celery worker.
- **`beat`**: Start the periodic task scheduler.
- **`inspect`**: Check worker health and registered tasks.
- **`purge`**: Clear all messages from a queue.
- **`process`**: Fine-grained process management sub-app.

## Managing Workers

### Start a Worker

By default, `worker start` launches a Celery worker. API server management has moved to `manager start`.

```bash title="Start Celery"
xcli worker start
```

### Inspect Workers

Check which worker nodes are online and what tasks they are capable of running.

```bash title="Inspect"
xcli worker inspect
```

### Purging Queues

If you have a buildup of unwanted tasks, you can clear a queue:

```bash
xcli worker purge default
```

## Periodic Tasks (Beat)

To start the scheduler that triggers periodic tasks:

```bash
xcli worker beat
```

!!! tip "Configuration"
    Worker settings like `broker_url`, `concurrency`, and `queues` are managed in the `services.xworker` section of `integration.yaml`.

## Next Steps

For detailed control over multiple worker processes, including logs and status tables, see [Process Management](process.md).
