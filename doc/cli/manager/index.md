---
title: Administration Dashboard
description: High-level control center for monitoring, service management, and administration.
icon: material/view-dashboard
---

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

Manage your API server directly from the CLI.

### Start the Server

```bash title="Development mode (hot-reload)"
xcli manager start --reload
```

```bash title="Production mode (detached)"
xcli manager start --workers 4 --detach
```

### Stop the Server

```bash
xcli manager stop
```

### Server Start Flags

| Flag | Description |
|------|-------------|
| `--reload` | Enable hot-reload (development only) |
| `--workers N` | Number of Uvicorn worker processes |
| `--host HOST` | Bind host (default: `127.0.0.1`) |
| `--port PORT` | Bind port (default: `8000`) |
| `--detach` / `-d` | Run as a background process |

## Monitoring & Services

### The `top` Dashboard

Launch the full-screen real-time management interface:

```bash
xcli manager top
```

### Service Management

Fine-grained control over individual providers (DB, Cache, etc.):

```bash
xcli manager services list
xcli manager services reload db
xcli manager services unload cache
```

## In This Section

- [Real-time Monitoring](monitoring.md)
- [Service Management](services.md)
