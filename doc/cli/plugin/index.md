# Plugin System

The `xcore` framework is designed around a powerful, modular plugin system. Plugins allow you to extend the core functionality of your application without modifying the kernel.

## Architecture

Plugins in `xcore` are self-contained modules located in the directory specified in `integration.yaml` (usually `./plugins/`).

### Types of Plugins

1. **Trusted Plugins**:
   - Have full access to the system.
   - Typically developed internally.
   - Must be signed if `strict_trusted` is enabled.

2. **Sandboxed Plugins**:
   - Run in an isolated environment.
   - Restricted by an AST-based whitelist for imports.
   - Limited resource consumption (CPU, Memory, Disk).

## Directory Structure

A typical plugin looks like this:

```text
plugins/
└── my-plugin/
    ├── src/
    │   └── main.py      # Entry point
    ├── plugin.yaml      # Metadata & Resources
    ├── plugin.sig       # Security signature
    └── requirements.txt # Dependencies
```

## Lifecycle Management

`xcorecli` provides a comprehensive suite of commands to manage the entire plugin lifecycle:

- **Development**: [Local Linking & Scaffolding](local.md)
- **Deployment**: [Installation & Removal](install.md)
- **Runtime**: [Load/Unload/Reload](runtime.md)
- **Discovery**: [Marketplace](marketplace.md)
- **Security**: [Signing & Health Checks](security.md)
- **Maintenance**: [Updates](update.md)

### Top-level Commands

In addition to sub-apps, the `plugin` group provides several direct commands:

- **`xcli plugin info <name>`**: Show detailed manifest and permissions for an installed plugin.
- **`xcli plugin health`**: Perform a global health check (signatures, AST, manifests) on all installed plugins.
- **`xcli plugin remove <name>`**: Uninstall a plugin and delete its files.

!!! tip "IPC (Inter-Plugin Communication)"
    Plugins can communicate with each other using the built-in IPC mechanism, which is enforced by the core `ServiceContainer`.
