# Worker Process Management

The `worker process` sub-app provides fine-grained control over multiple background worker instances.

## Process Lifecycle

### Start Multiple Instances

Start several worker instances at once, each with its own hostname.

```bash
xcli worker process start --count 4
```

### Advanced Start Flags

- `--queues` / `-Q`: Comma-separated list of queues to listen to.
- `--concurrency`: Number of child processes per worker instance.
- `--detach` / `-d`: Run workers in the background.

```bash
xcli worker process start --queues priority,emails --concurrency 8 --detach
```

### Stop

Gracefully shut down all running worker processes.

```bash
xcli worker process stop
```

### Restart

Stop then restart all worker processes to apply code changes.

```bash
xcli worker process restart
```

## Monitoring & Logs

### Status

See a detailed table of running worker processes, including their PIDs, uptime, and resource usage.

```bash title="Process Status"
xcli worker process status
```

### Logs

Tail the logs specifically for the worker processes.

```bash title="Worker Logs"
xcli worker process logs --lines 50 --follow
```

!!! note "Background Processes"
    Status and log commands are particularly useful when workers are started with the `--detach` flag.
