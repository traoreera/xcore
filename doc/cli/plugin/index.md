---
title: Plugin System
description: Manage the full plugin lifecycle — scaffold, install, deploy, and control plugins.
icon: material/puzzle
---

# Plugin System

The `xcore` framework is designed around a powerful, modular plugin system. Plugins allow you to extend the core functionality of your application without modifying the kernel.

## Architecture

Plugins in `xcore` are self-contained modules located in the directory specified in `integration.yaml` (usually `./plugins/`).

### Types of Plugins

**Trusted Plugins**

- Have full access to the system and service container.
- Typically developed internally or by vetted contributors.
- Must be signed if `strict_trusted: true` is enabled.

**Sandboxed Plugins**

- Run in an isolated subprocess environment.
- Restricted by an AST-based whitelist for imports.
- Limited resource consumption (CPU, Memory, Disk quotas).

## Directory Structure

A typical plugin looks like this:

```text
plugins/
└── my-plugin/
    ├── src/
    │   ├── __init__.py
    │   └── main.py          # Entry point — class Plugin
    ├── plugin.yaml          # Metadata, permissions & resources
    ├── plugin.sig           # HMAC signature file (production)
    ├── tests/               # Plugin unit tests
    └── data/                # Writable data directory (sandboxed)
```

## Quick Start

```bash
# Scaffold a new trusted plugin
xcli plugin local scaffold my_plugin --mode trusted --db --cache

# Link your development directory
xcli plugin local link --path ./my_plugin --name my_plugin

# Check the plugin loaded correctly
xcli plugin runtime status

# Run a health check on all plugins
xcli plugin health
```

## Lifecycle Management

`xcorecli` provides a comprehensive suite of commands to manage the entire plugin lifecycle:

| Stage | Command Group | Purpose |
|-------|---------------|---------|
| Development | [Local](local.md) | Scaffold, symlink, and iterate locally |
| Deployment | [Install](install.md) | Install from marketplace, Git, or zip |
| Runtime | [Runtime](runtime.md) | Load, unload, reload, and call actions |
| Discovery | [Marketplace](marketplace.md) | Browse and search the plugin registry |
| Security | [Security](security.md) | Sign, verify, and audit plugins |
| Maintenance | [Updates](update.md) | Check and apply upstream updates |

## Top-level Commands

| Command | Description |
|---------|-------------|
| `xcli plugin info <name>` | Show manifest, permissions, and resource limits |
| `xcli plugin health` | Check signatures, AST, and manifests for all plugins |
| `xcli plugin remove <name>` | Uninstall a plugin and delete its directory |
| `xcli plugin versions <name>` | List all available versions on the marketplace |

!!! tip "Inter-Plugin Communication (IPC)"
    Plugins communicate using the built-in IPC mechanism. Declare `allowed_callers` in `plugin.yaml` to control which plugins can call yours:
    ```yaml
    allowed_callers:
      - "auth_plugin"
      - "admin_panel"
    ```
