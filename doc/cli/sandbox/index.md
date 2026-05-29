---
title: Plugin Sandboxing
description: Inspect and manage the security isolation layer for sandboxed plugins.
icon: material/box-shadow
---

# Plugin Sandboxing

The Sandbox provides a secure execution environment for third-party or untrusted plugins, ensuring they cannot compromise the host system.

## Security Layers

Xcore applies multiple isolation mechanisms to every sandboxed plugin:

1. **AST Scanning** — Static code analysis before execution to detect forbidden imports.
2. **Import Restrictions** — A `sys.meta_path` hook blocks access to non-whitelisted modules.
3. **Filesystem Guard** — Intercepts `open()`, `pathlib`, and `os` to restrict file access.
4. **Resource Limits** — Enforces CPU time, memory (RSS), and disk quotas.
5. **IPC Protocol** — Communication through JSON over stdin/stdout pipes, not shared memory.

## Resource Isolation

Sandboxed plugins are restricted in their resource consumption to prevent "noisy neighbor" issues or intentional Denial of Service.

### Default Limits (integration.yaml)

```yaml title="integration.yaml"
security:
  rate_limit_default:
    calls: 200           # Max IPC calls
    period_seconds: 60   # Per minute window
```

### Per-Plugin Limits (plugin.yaml)

```yaml title="plugin.yaml"
resources:
  max_memory_mb: 256
  max_disk_mb: 50
  timeout_seconds: 10.0
  rate_limit:
    calls: 500
    period_seconds: 60

filesystem:
  allowed_paths: ["data/", "tmp/"]
  denied_paths:  ["src/", "plugin.yaml"]
```

## AST-Based Whitelisting

The AST analyzer scans every `.py` file in the plugin's `src/` directory before the first load.

- **Allowed**: Only modules listed in `security.allowed_imports` can be imported.
- **Blocked**: Modules in `security.forbidden_imports` raise a `PermissionError` at import time.

```yaml title="integration.yaml"
security:
  allowed_imports:
    - json
    - math
    - datetime
    - pydantic
    - re
  forbidden_imports:
    - os
    - sys
    - subprocess
    - socket
    - ctypes
    - threading
```

!!! danger "Sandbox Bypass Attempt"
    Attempting to bypass the sandbox via reflection (`__subclasses__`, `__globals__`) or other advanced Python techniques is detected by the AST scanner and will result in the plugin being refused.

## Managing the Sandbox

Use the `sandbox` command group to inspect the isolation layer:

```bash title="Global sandbox statistics"
xcli sandbox stats

# Sandbox Statistics
# ─────────────────────────────────────────────────
#  Plugin             Calls   Avg CPU   Avg Mem   Violations
#  text_transformer   14230   12ms      48 MB     0
#  data_processor     8901    87ms      201 MB    2
```

```bash title="Inspect a specific plugin"
xcli sandbox inspect data_processor

# Sandbox: data_processor
# Mode:       sandboxed
# PID:        19823
# Memory:     201 MB / 256 MB limit
# Disk:       12 MB / 50 MB limit
# Violations: 2 (see logs for details)
# Uptime:     1h 42m
```

!!! info "Trusted vs. Sandboxed"
    Plugins run in **Sandboxed** mode unless `execution_mode: trusted` is declared in `plugin.yaml`. A trusted plugin must also be signed when `strict_trusted: true` is enabled.

## See Also

[Sandboxed Plugin Development](../../plugins/sandboxed-plugins.md)
:   How to write plugins designed for sandboxed execution.

[Security Architecture](../../security/security.md)
:   Deep dive into the FilesystemGuard and AST scanner.
