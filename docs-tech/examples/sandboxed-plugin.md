# Example: Secure File Processor

A sandboxed plugin designed for processing untrusted data with strict resource limits.

## 1. Manifest (`plugin.yaml`)

```yaml
name: secure_processor
version: 1.0.0
execution_mode: sandboxed
entry_point: src/main.py

# Only allow safe modules
allowed_imports:
  - json
  - hashlib
  - base64

resources:
  timeout_seconds: 5
  max_memory_mb: 128
  rate_limit:
    calls: 10
    period_seconds: 60
```

## 2. Implementation (`src/main.py`)

```python
from xcore.sdk import TrustedBase, ok
import hashlib

class Plugin(TrustedBase):
    async def handle(self, action: str, payload: dict) -> dict:
        if action == "hash":
            data = payload.get("data", "").encode()
            return ok(hash=hashlib.sha256(data).hexdigest())

        return {"status": "error", "msg": "Unknown action"}
```
