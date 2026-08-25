# Plugin Sandboxing

The Sandbox provides a secure execution environment for third-party or untrusted plugins, ensuring they cannot compromise the host system.

## Resource Isolation

Sandboxed plugins are restricted in their resource consumption to prevent "noisy neighbor" issues or intentional Denial of Service.

### Limits Configuration

You can define default limits in `integration.yaml`:

```yaml
security:
  rate_limit_default:
    calls: 200        # Max IPC calls
    period_seconds: 60 # Per minute
```

## AST-Based Whitelisting

The core of the sandbox is an AST (Abstract Syntax Tree) analyzer that scans the plugin's code before execution.

- **Whitelisted**: Only modules listed in `security.allowed_imports` can be imported.
- **Blacklisted**: Modules in `security.forbidden_imports` (like `os` or `subprocess`) are explicitly blocked.

!!! danger "Sandbox Bypass"
    Attempting to bypass the sandbox via reflection or other advanced Python techniques is monitored and will result in the plugin being immediately unloaded.

## Managing the Sandbox

Use the `sandbox` command group to run a plugin in isolation and inspect the
policy declared in its manifest — none of these require the plugin to
already be loaded by a running `xcore` instance, unlike `xcli plugin
runtime`.

### Run

Launch a plugin in an isolated sandbox process and keep it running until
you interrupt it (Ctrl+C):

```bash
xcli sandbox run my-sandboxed-plugin
```

### Call

Start the sandbox, invoke a single action, print the result, then stop —
useful for testing one IPC action without keeping the process alive:

```bash
xcli sandbox call my-sandboxed-plugin send_email --payload '{"to": "user@example.com"}'
```

!!! warning "Sandboxed plugins only"
    `sandbox call` refuses a plugin whose `execution_mode` isn't
    `sandboxed` — use `xcli plugin runtime call` for a `trusted` plugin
    instead.

### Limits

Show the resource limits declared in the plugin's manifest (timeout, max
memory/disk, rate limit) — read-only, no process started:

```bash
xcli sandbox limits my-sandboxed-plugin
```

### Network

Show the plugin's declared network policy (`network:` in `plugin.yaml`):

```bash
xcli sandbox network my-sandboxed-plugin
```

### Filesystem

Show the plugin's declared filesystem policy (`filesystem:` in `plugin.yaml`):

```bash
xcli sandbox fs my-sandboxed-plugin
```

!!! info "Trusted vs. Sandboxed"
    By default, plugins are treated as **Sandboxed**. You must explicitly mark a plugin as **Trusted** in its `plugin.yaml` (and usually sign it) to run it with full permissions.
