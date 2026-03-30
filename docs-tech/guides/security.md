# Security Deep Dive

XCore follows a "Zero Trust" model for plugins. Even trusted plugins are restricted from modifying core kernel state, while sandboxed plugins are isolated at the OS and Runtime levels.

---

## 1. The Multi-Layer Sandbox

When a plugin's `execution_mode` is set to `sandboxed`, the kernel applies multiple defensive layers.

### Layer 1: Static Code Analysis (AST)
Before execution, the `ASTScanner` parses the plugin's source tree. It uses an `ast.NodeVisitor` to inspect every node.

-   **Forbidden Names**: Accessing names like `eval`, `exec`, `globals`, `locals`, or `__import__` is blocked.
-   **Forbidden Attributes**: Accessing sensitive attributes like `__class__`, `__globals__`, or `__subclasses__` (common in sandbox escapes) is prohibited.
-   **Import Whitelisting**: Only modules explicitly listed in `allowed_imports` (in `plugin.yaml`) or the global kernel whitelist are allowed.

### Layer 2: Process Isolation
Sandboxed plugins run in a dedicated OS process via the `multiprocessing` module.
-   **IPC Channel**: The only bridge between the kernel and the sandbox is a standard JSON-RPC 2.0 channel over OS pipes.
-   **Serialization**: Only standard JSON types are passed. No Python objects (no `pickle`) are exchanged, eliminating entire classes of injection attacks.

### Layer 3: OS Resource Limits
The kernel monitors the worker process RSS (Resident Set Size) and CPU time.
-   **Memory**: Workers are terminated if they exceed `max_memory_mb`.
-   **Timeout**: Every IPC call has a mandatory `timeout_seconds`. If the worker hangs, it is killed.

---

## 2. Permission Engine

Every inter-plugin call and service access is audited by the **PermissionEngine**.

### Policy Evaluation
XCore uses a "Fail-Closed" model. If no policy explicitly allows an action, it is denied.
1.  Check for an explicit `deny`.
2.  Check for an explicit `allow`.
3.  Default to `deny`.

### Granular Patterns
You can use `*` wildcards for resources:
```yaml
# Allows reading from any table in the 'users' database
- resource: "db.users.*"
  actions: ["read"]
  effect: allow
```

---

## 3. Trusted Plugin Signing

In production, enabling `strict_trusted` mode ensures that even plugins running in the main process haven't been tampered with.

-   **Signature**: A `plugin.sig` file contains HMAC-SHA256 hashes of every file in the plugin directory.
-   **Verification**: At boot, the kernel recalculates all hashes using a secret `SERVER_KEY`. If they don't match, the plugin refuses to load.

---

## 4. Best Practices for Developers

1.  **Use Sandboxing by Default**: Only use `trusted` mode if you need access to complex kernel objects or low-level FastAPI hooks.
2.  **Request Minimal Permissions**: Use the principle of least privilege.
3.  **Validate All Inputs**: Use the `@validate_payload` decorator to ensure your handlers don't process malformed JSON.
4.  **No Local State**: Treat plugins as ephemeral. Store all persistence in the shared `db` or `cache` services.
