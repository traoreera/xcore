# Deep Guide: Security & Sandboxing

Security is the cornerstone of XCore. This guide explains the technical details of our isolation model and how to configure it for maximum protection.

## 1. The Security Philosophy
XCore operates on a **"Zero Trust"** model for plugins. Even `trusted` plugins are signed to prevent unauthorized code modification, while `sandboxed` plugins are treated as inherently unsafe and isolated at multiple levels.

---

## 2. Multi-Layer Sandboxing

### A. Static Code Analysis (AST)
When a sandboxed plugin is loaded, the kernel's `ASTScanner` analyzes the source tree. It uses an `ast.NodeVisitor` to inspect every import, name access, and function call.

- **Forbidden Modules**: Blocked modules include `os`, `sys`, `subprocess`, `socket`, `ctypes`, and `requests` (to prevent unauthorized network calls).
- **Attribute Access**: Accessing sensitive attributes like `__class__`, `__globals__`, or `__subclasses__` is blocked to prevent Python introspection escapes.
- **Built-in Restriction**: Dangerous functions like `eval()`, `exec()`, and `__import__()` are completely removed from the worker's environment.

**Configuration**:
You can extend the whitelist of imports in `plugin.yaml`:
```yaml
allowed_imports:
  - math
  - json
  - pydantic
  - PIL
```

### B. OS Process Isolation
Sandboxed plugins do not share memory with the kernel. They run in a separate process spawned using `multiprocessing` or `subprocess`.
- **IPC Channel**: The only way for the kernel to talk to the sandbox is through a specialized JSON-RPC channel over OS pipes.
- **Data Serialization**: All parameters and results are serialized to JSON, ensuring no complex Python objects (which could contain executable code) are passed between processes.

### C. Resource Enforcement
The kernel monitors the sandbox process in real-time.
- **CPU Time**: If a call exceeds the `timeout_seconds`, the worker process is immediately sent a `SIGKILL`.
- **Memory (RSS)**: Max memory is capped. If exceeded, the process is terminated to prevent OOM (Out of Memory) conditions on the host.
- **Rate Limiting**: The `RateLimitMiddleware` counts calls per plugin per sliding window (e.g., 100 calls / 60s) and rejects excesses before they even reach the sandbox.

---

## 3. Permission Engine & RBAC

XCore uses a **Policy-Based Access Control** system. Each plugin defines its own required permissions in the manifest.

### Policy Structure:
```yaml
permissions:
  - resource: "db.users.*"
    actions: ["read"]
    effect: allow
  - resource: "ext.email"
    actions: ["send"]
    effect: deny
```

### Evaluation Logic:
1.  **Explicit Deny**: If a policy matches with `effect: deny`, the action is blocked regardless of other policies.
2.  **Explicit Allow**: If no deny matches, but an allow policy does, the action is permitted.
3.  **Deny-by-Default**: If no policy matches at all, the action is denied.

---

## 4. Plugin Integrity (Signing)

To prevent code tampering in production, XCore supports HMAC-SHA256 signatures.

### Signing a Plugin:
```bash
# Generate a plugin.sig file
xcore plugin sign ./plugins/my_plugin --key your-secret-key
```

### Verification:
In production, enable `strict_trusted` mode in `xcore.yaml`:
```yaml
plugins:
  strict_trusted: true
```
The kernel will verify the signature of every file in the plugin against the `plugin.sig` manifest. If a single byte has changed, the plugin will refuse to load.

---

## 5. Network & Filesystem Security

### Logical Filesystem (Chroot-like)
The `SandboxedActivator` validates all filesystem paths. Plugins can only access paths relative to their own `data/` directory. Attempts to use `../` or absolute paths are rejected.

### Network Isolation
By default, network modules like `socket` and `http.client` are blocked in the AST scanner. If a plugin needs to make external calls, it must use a `Trusted` proxy plugin or a dedicated kernel service.

---

## 6. Security Audit Logs

XCore maintains a detailed audit trail of every security-relevant event.

- **Permission Logs**: Every `ALLOW` or `DENY` is logged with the calling plugin, target resource, and action.
- **Scan Violations**: Any AST scan failure is logged with the specific line number and reason.
- **CLI Audit**:
  ```bash
  xcore permissions audit --plugin task_manager --limit 50
  ```

## Best Practices for Plugin Developers
1.  **Use Sandboxing**: Always use `sandboxed` mode unless you need direct access to deep kernel services.
2.  **Minimize Permissions**: Only request the specific resources your plugin needs.
3.  **Validate Payloads**: Use `@validate_payload` to ensure your IPC handlers don't process malformed data.
4.  **No Secrets in Code**: Use environment variables for API keys and database credentials.
