---
title: Plugin Anatomy
description: Understanding the structure and manifest of an Xcore plugin.
icon: material/file-tree
---

# Plugin Anatomy

An Xcore plugin is a self-contained directory that includes logic, metadata, and optional resources. Every plugin must follow a specific structure and provide a manifest file (`plugin.yaml`) for the framework to load it correctly.

---

### Prerequisites

- [x] [Xcore Installation](../installation.md)
- [x] Basic knowledge of YAML syntax

---

### Directory Structure

The standard structure for an Xcore plugin is:

```text
my_plugin/
├── plugin.yaml          # (1)!
├── src/                 # (2)!
│   ├── __init__.py
│   └── main.py          # (3)!
├── data/                # (4)!
└── tests/               # (5)!
```

1.  **Manifest**: Metadata, dependencies, and permissions.
2.  **Source Code**: Isolated namespace for the plugin logic.
3.  **Entry Point**: Contains the `class Plugin`.
4.  **Persistent Data**: The only directory writable by default in Sandboxed mode.
5.  **Tests**: Unit tests for the plugin.

---

### The Manifest (`plugin.yaml`)

The manifest is the source of truth for the framework. It defines how the plugin should be executed and what resources it can access.

#### 1. Identification
```yaml linenums="1"
name: "billing_engine"  # (1)!
version: "1.2.0"       # (2)!
framework_version: ">=2.1.0"  # (3)!
execution_mode: "trusted"  # (4)!
entry_point: "src/main.py"
```

1.  **Unique ID**: Must be snake_case.
2.  **Semantic Versioning**: Used for dependency resolution.
3.  **Compatibility**: Xcore will refuse to load the plugin if the framework version is lower.
4.  **Mode**: `trusted` (native) or `sandboxed` (isolated).

#### 2. Dependencies
Declare other plugins your plugin depends on. Xcore uses this to determine the loading order (**Waves**).

```yaml linenums="6"
requires:
  - name: "database_utils"
    version: "^1.0.0"
  - name: "auth_provider"
    version: ">=2.0.0"
```

#### 3. Security & Permissions
Permissions are **fail-closed**. If not declared here, they are denied by default.

```yaml linenums="11"
permissions:
  - "service:db:read"
  - "service:cache:*"
  - "plugin:logger:log"
```

#### 4. Sandbox Restrictions
Relevant only for `execution_mode: sandboxed`.

```yaml linenums="16"
filesystem:
  allowed_paths: ["data/", "tmp/"]  # Relative to plugin root
  denied_paths: ["src/", "plugin.yaml"]

resources:
  max_memory_mb: 256
  max_disk_mb: 50
  timeout_seconds: 10.0
  rate_limit:
    calls: 1000
    period_seconds: 60
```

#### 5. Environment & Configuration
Xcore supports environment variable substitution using `${VAR}`.

```yaml linenums="28"
env:
  API_KEY: "${MY_APP_API_KEY}"  # (1)!
  DB_URL: "sqlite:///data/plugin.db"

extra:  # (2)!
  theme: "dark"
  retries: 5
```

1.  Resolved from the host system's environment variables.
2.  Available inside the plugin via `self.ctx.config`.

---

### Manifest Reference

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | **Required** | Unique identifier for the plugin. |
| `version` | `str` | **Required** | Plugin version (SemVer). |
| `framework_version`| `str` | `"*"` | Minimum Xcore version required. |
| `execution_mode` | `str` | `"legacy"` | `trusted` or `sandboxed`. |
| `entry_point` | `str` | `"src/main.py"` | Path to the file containing `class Plugin`. |
| `requires` | `list` | `[]` | List of dependency objects (name + version). |
| `permissions` | `list` | `[]` | Explicit permissions for services and IPC. |
| `extra` | `dict` | `{}` | Arbitrary configuration parameters. |

---

### Common Errors & Pitfalls

!!! danger "Invalid YAML Syntax"
    A simple indentation error in `plugin.yaml` will prevent the `PluginLoader` from even discovering the plugin. Use a YAML validator if the plugin doesn't appear in `xcore plugin list`.

!!! warning "Framework Version Mismatch"
    If you set `framework_version: ">=3.0.0"` but run Xcore `2.1.2`, the plugin will be skipped during boot with a compatibility warning in the logs.

!!! failure "Entry Point Path"
    The `entry_point` path is relative to the plugin root. Ensure it points to the actual `.py` file, not just the directory.

---

### Best Practices

!!! success "Use semantic versioning"
    Always follow [SemVer](https://semver.org/) for your plugin versions. This ensures that dependents can safely use `^` (compatible) or `~` (patch) constraints.

!!! tip "Keep Extra Configuration Lean"
    Use the `extra` block for settings that change per environment. Hardcoded business logic should stay in your Python code.

---

### See Also

[Trusted Plugins](./trusted-plugins.md)
:   Implementing the `TrustedBase` contract.

[Sandboxed Plugins](./sandboxed-plugins.md)
:   Best practices for isolated plugin development.

[Dependency Management](../kernel/kernel.md#plugin-waves-topological-loading)
:   How Xcore resolves the loading order.
