---
title: Advanced Sandbox: Transformation Engine
description: Building a secure, high-performance data processing engine in an isolated sandbox.
icon: material/inventory
---

# Advanced Sandbox: Transformation Engine

This example features a **Sandboxed** plugin designed to handle massive data transformations using untrusted logic. It demonstrates how to push the limits of Xcore's isolation while maintaining strict control over system resources.

---

### 1. The Manifest (`plugin.yaml`)

We use the manifest to create a "digital cage" for the plugin, preventing it from consuming too much memory or performing illegal operations.

```yaml linenums="1"
name: "high_perf_transformer"
version: "3.2.0"
execution_mode: "sandboxed"

resources:
  max_memory_mb: 256         # (1)!
  max_disk_mb: 100           # (2)!
  timeout_seconds: 5.0       # (3)!
  rate_limit:
    calls: 5000              # (4)!
    period_seconds: 60

retry:
  max_attempts: 5
  backoff_seconds: 0.1

filesystem:
  allowed_paths: ["data/logs/", "data/temp/"]
  denied_paths: ["src/", "plugin.yaml"]
```

1.  Hard RSS memory ceiling.
2.  The plugin can write up to 100MB of temporary data.
3.  Kills any call taking > 5 seconds.
4.  Standard rate limiting to prevent DoS attacks from compromised plugins.

---

### 2. The Implementation (`src/main.py`)

A stateless transformation logic that utilizes local disk for buffering large payloads.

```python linenums="1"
import json
import hashlib
import time

class Plugin:
    async def on_load(self):
        # Warmup: load a heavy dictionary from data/
        print("[sandbox] engine warmed up")

    async def handle(self, action: str, payload: dict) -> dict:
        if action == "bulk_transform":
            items = payload.get("items", [])
            results = []

            # (1) Performance tracing inside sandbox
            start = time.perf_counter()

            for item in items:
                # Apply complex transformation logic
                processed = self._transform_item(item)
                results.append(processed)

                # (2) Periodic heartbeat for health monitor
                # (handled automatically by IPC channel)

            duration = time.perf_counter() - start

            # (3) Return structured results
            return {
                "status": "ok",
                "count": len(results),
                "data": results,
                "metrics": {"duration": duration}
            }

        return {"status": "error", "msg": f"Action {action} unknown"}

    def _transform_item(self, item: str) -> str:
        # Simulate heavy CPU work
        return hashlib.sha256(item.encode()).hexdigest()
```

---

### 3. Advanced IPC Patterns

#### Calling from the Main App
When calling a sandboxed plugin from a FastAPI route, always handle potential resource violations gracefully.

```python linenums="1"
@app.post("/transform")
async def transform(data: list[str]):
    try:
        result = await xcore.plugins.call(
            "high_perf_transformer",
            "bulk_transform",
            {"items": data}
        )
        return result
    except IPCTimeoutError:
        # The sandbox took too long and was killed
        return {"error": "Processing timeout", "code": 504}
    except PermissionError:
        # The sandbox tried to do something illegal
        return {"error": "Security violation", "code": 403}
```

---

### 4. Performance Tuning

#### Batching Calls
IPC communication has overhead. Instead of calling the sandbox 1,000 times for 1,000 items, pass a list of 1,000 items in a single `call()`. This reduces context switching between the main process and the sandbox worker.

#### Filesystem Buffering
If your payload is too large for JSON serialization (e.g., > 10MB), write the data to a shared volume in the plugin's `data/` directory and pass the filename as the payload.

---

### 5. Troubleshooting Resource Limits

!!! danger "DiskQuotaExceeded"
    If the plugin writes more than `max_disk_mb` to `data/`, Xcore will block all further writes.
    **Fix**: Implement a cleanup routine in your `handle` method or increase the quota.

!!! warning "Memory Ceiling (OOM)"
    If you see `Exit Code 137` in the logs, the OS OOM killer terminated the sandbox.
    **Fix**: Check for memory leaks or increase `max_memory_mb`.

---

### See Also

[Security & Sandboxing](../security/security.md)
:   Deep dive into the C++ AST scanner and resource enforcement.

[Middleware Pipeline](../advanced/middleware.md)
:   Understand how the `RetryMiddleware` handles sandbox crashes.
