# Sandboxed Service Example

This example demonstrates a "Sandboxed" plugin with resource limits and specific permissions.

## Manifest (`plugin.yaml`)
```yaml
name: sandboxed_service
version: "1.0.0"
execution_mode: sandboxed
entry_point: src/main.py

permissions:
  - resource: "cache.*"
    actions: ["read", "write"]
    effect: allow

resources:
  max_memory_mb: 128
  timeout_seconds: 10
```

## Logic (`src/main.py`)
```python
from xcore.sdk import SandboxedBase, AutoDispatchMixin, action, ok

class Plugin(AutoDispatchMixin, SandboxedBase):
    @action("compute")
    async def compute(self, payload: dict):
        # This runs in an isolated process
        return ok(result="computed in sandbox")
```
