# Administration Dashboard

The `manager` command group is your high-level control center for the entire `xcore` project. It provides a suite of tools for monitoring, service management, and system-wide administration.

## The Manager Concept

While other commands focus on specific components (like `plugin` or `worker`), the `manager` provides an aggregated view and orchestration capabilities for the whole system.

### Core Capabilities

- **Server Management**: Start and stop the FastAPI/Uvicorn server.
- **Real-time Monitoring**: Full-screen "top-like" dashboard.
- **Resource Analytics**: Detailed memory and CPU profiling per plugin.
- **Service Orchestration**: Hot-reloading and unloading of system services.
- **Log Aggregation**: Unified view of logs from multiple sources.

## Server Management

You can manage your API server directly from the CLI.

### Start the Server

```bash title="Development mode"
xcli manager start --reload
```

```bash title="Production mode"
xcli manager start --workers 4 --detach
```

### Stop the Server

If started with `--detach`, you can stop it using:

```bash
xcli manager stop
```

## Monitoring & Services

### The `top` Dashboard

To launch the main management interface:

```bash
xcli manager top
```

### Service Management

The `services` sub-app allows fine-grained control over individual providers (DB, Cache, etc.).

```bash
xcli manager services list
xcli manager services reload db
```

## In this section:

- [Real-time Monitoring](monitoring.md)
- [Service Management](services.md)
