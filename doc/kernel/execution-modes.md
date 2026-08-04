---
title: Execution Modes
description: Comparison between Trusted, Sandboxed, and Ephemeral execution modes in Xcore.
icon: material/shield-sync
---

# Execution Modes

Xcore supports three execution modes for plugins: **Trusted**, **Sandboxed**, and **Ephemeral**. The choice depends on the source of the plugin and the required level of performance, security, and isolation.

---

### Comparison Table

| Feature | Trusted Mode | Sandboxed Mode | Ephemeral Mode |
|---------|--------------|----------------|----------------|
| **Process** | Main Process | Isolated Subprocess | Main Process |
| **Lifetime** | Persistent | Persistent | Per-call |
| **Performance** | Native (Fast) | IPC Overhead (Medium) | Native (Fast) |
| **Security** | None (Full Access) | High (Restricted) | None (Full Access) |
| **State** | Persistent | Persistent | Stateless (zero) |
| **Filesystem** | Full Access | Restricted (FilesystemGuard) | Full Access |
| **Imports** | All Python modules | Whitelisted modules only | All Python modules |
| **Resource Limits** | Shared with App | CPU, Memory & Disk Quotas | Bounded by WarmPool |
| **Use Case** | Core business logic | 3rd-party, Untrusted, or Experimental | Serverless-style, hot reloads |

---

### Trusted Mode

Trusted plugins run directly in the main FastAPI process. They have full access to the system, including environment variables, sensitive files, and the entire Python standard library.

#### Signature Verification
To prevent malicious code from being injected into the `plugins/` directory, Xcore supports mandatory signature verification for Trusted plugins.

```yaml title="xcore.yaml"
plugins:
  strict_trusted: true
```

When enabled, Xcore will refuse to load any Trusted plugin that does not have a valid `plugin.sig` file generated using the `xcore plugin sign` command.

---

### Sandboxed Mode

Sandboxed plugins run in an isolated subprocess. Xcore applies multiple layers of security to ensure that the sandboxed code cannot compromise the host system.

#### 1. Filesystem Guard
The `FilesystemGuard` intercepts all file operations (via `open`, `os`, and `pathlib`).
- **Fail-closed**: By default, the plugin can only access its own `data/` directory.
- **Traversal Protection**: Relative paths are resolved and checked against the plugin root.

#### 2. Import Restrictions
The sandbox blocks access to sensitive Python modules such as `subprocess`, `os`, `ctypes`, `socket`, and `shutil`. Any attempt to import these will raise a `PermissionError`.

#### 3. Resource Limits
Resource limits are enforced via `RLIMIT_AS` (Memory) and `RLIMIT_CPU` (CPU) on Linux systems.

```yaml title="plugin.yaml"
resources:
  max_memory_mb: 128
  max_disk_mb: 50
  timeout_seconds: 5.0
```

#### 4. Inter-Process Communication (IPC)
Since the plugin runs in a separate process, communication happens via a JSON newline-delimited protocol over standard I/O pipes.

```mermaid
sequenceDiagram
    participant K as Kernel (Main)
    participant S as Supervisor
    participant W as Worker (Subprocess)
    participant P as Plugin Instance

    K->>S: call("my_plugin", "sum", {a:1, b:2})
    S->>W: {"action": "sum", "payload": {a:1, b:2}}\n
    W->>P: handle("sum", {a:1, b:2})
    P-->>W: {status: "ok", result: 3}
    W-->>S: {"status": "ok", "result": 3}\n
    S-->>K: {status: "ok", result: 3}
```

---

### Ephemeral Mode

Ephemeral plugins run in the main process but are **created per call and destroyed right after**. No instance survives between two calls, giving zero implicit state, bounded memory, and per-call isolation — at near-native speed.

This is the recommended mode for serverless-style actions and for plugins that are hot-reloaded frequently, since repeated reloads no longer leak memory.

```yaml title="plugin.yaml"
name: "image_processor"
version: "1.0.0"
execution_mode: "ephemeral"
entry_point: "src/main.py"

ephemeral:              # optional — falls back to plugins.ephemeral
  pool_size: 2
  max_idle_seconds: 60
  max_concurrent: 10
  boot_timeout: 5.0
```

See the [Ephemeral Plugins](../plugins/ephemeral-plugins.md) guide for the full lifecycle, configuration reference, and tuning advice.

---

### Configuration

#### Declaring Mode in `plugin.yaml`
```yaml linenums="1"
name: "security_scanner"
mode: "sandboxed"  # (1)!
entry_point: "src/main.py"

filesystem:
  allowed_paths: ["data/", "tmp/"]
  denied_paths: ["src/"]

resources:
  max_memory_mb: 256
```

1.  Accepted values: `trusted` | `sandboxed` | `ephemeral`. (`legacy` is deprecated.)

---

### Common Errors & Pitfalls

!!! danger "Sandboxed: PermissionDenied"
    If a sandboxed plugin tries to access a file outside `allowed_paths`, or imports a forbidden module, it will receive a `PermissionError`.
    **Fix**: Explicitly add the path to `allowed_paths` or use a Trusted plugin if full access is required.

!!! warning "IPC Overhead"
    Every call to a sandboxed plugin involves JSON serialization/deserialization and process context switching. Avoid using sandboxed plugins for high-frequency operations (e.g., millions of calls per second).

!!! failure "DiskQuotaExceeded"
    If the `data/` directory exceeds `max_disk_mb`, the `SandboxProcessManager` will block further `call()` attempts.
    **Fix**: Clean up temporary files or increase the quota in `plugin.yaml`.

!!! danger "Ephemeral: Boot Timeout"
    If an ephemeral plugin's `on_load()` takes longer than `boot_timeout`, the instance boot fails.
    **Fix**: Move heavy initialization out of `on_load()` or raise `boot_timeout` in the `ephemeral:` block.

---

### Best Practices

!!! success "Use Sandboxing for Extension Points"
    If your framework allows users to upload their own logic (e.g., a "Transformation Plugin"), **always** use Sandboxed mode.

!!! tip "Health Checks"
    Enable health checks for sandboxed plugins to ensure the supervisor can automatically restart them if they crash or hang.

```yaml title="plugin.yaml"
runtime:
  health_check:
    enabled: true
    interval_seconds: 30
    timeout_seconds: 5
```
