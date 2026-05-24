---
title: CLI Reference
description: Command-line interface reference for the xcore control tool.
icon: material/console
---

# CLI Reference

The `xcore` CLI is the control center for your framework. It allows you to manage the plugin lifecycle, inspect system health, and perform security operations directly from the terminal.

---

### Prerequisites

- [x] [Xcore Installation](../installation.md) completed
- [x] Poetry environment activated (`poetry shell`) or using `poetry run xcore`

---

### Command Overview

| Command | Category | Description |
|:--- | :--- | :--- |
| `xcore plugin list` | Plugins | List all loaded plugins and their status. |
| `xcore plugin info <name>` | Plugins | Show manifest, dependencies, and permissions. |
| `xcore plugin reload <name>`| Plugins | Hot-reload a plugin without stopping the server. |
| `xcore plugin sign <path>` | Security | Generate a `plugin.sig` for Trusted plugins. |
| `xcore services status` | Services | Check health of DB, Cache, and Scheduler. |
| `xcore health` | System | Perform a global system health check. |
| `xcore worker start` | System | Start the background task worker subprocess. |

---

### Plugin Management

#### Listing Plugins
Shows all plugins discovered in the `plugins/` directory, their current state, and execution mode.

```bash
xcore plugin list
```

#### Inspecting a Plugin
Displays the full details of a plugin, including its declared permissions and current resource usage.

```bash
xcore plugin info my_plugin
```

#### Hot-Reloading
Forces a plugin to reload its source code and manifest. This is useful during development to apply changes without restarting the FastAPI server.

```bash
xcore plugin reload my_plugin
```

---

### Security Operations

#### Signing a Plugin
Mandatory for **Trusted** plugins when `strict_trusted` is enabled. You must provide the secret key (matching the one in `xcore.yaml`).

```bash
xcore plugin sign ./plugins/my_plugin --key YOUR_SECRET_KEY
```

!!! tip "Key Management"
    Instead of passing the key as an argument, you can set the `XCORE_SECRET_KEY` environment variable.

---

### Service & System Health

#### Service Status
Provides a detailed breakdown of all registered services, including database connection strings (masked) and cache stats.

```bash
xcore services status
```

#### Global Health Check
Aggregates health checks from all services and plugins. Returns a non-zero exit code if any critical component is failing.

```bash
xcore health
```

---

### Background Workers

#### Starting the Worker
Starts the internal task worker responsible for executing background jobs and deferred events.

```bash
xcore worker start --queues default,high
```

---

### Common Errors & Pitfalls

!!! danger "Command Not Found"
    If `xcore` is not recognized, ensure you are inside the Poetry virtual environment or that the package was installed correctly.
    **Fix**: Run `poetry install` followed by `poetry shell`.

!!! warning "Configuration Not Found"
    Most CLI commands require an `xcore.yaml` or `integration.yaml` in the current directory to locate plugins and services.
    **Fix**: Run the command from the project root or use the `--config` flag.

---

### Best Practices

!!! success "Automate Health Checks"
    Integrate `xcore health` into your CI/CD pipeline or monitoring probes to ensure your application is fully functional after a deployment.

!!! tip "Use --help"
    Every command and sub-command supports the `--help` flag for detailed parameter descriptions:
    ```bash
    xcore plugin sign --help
    ```
