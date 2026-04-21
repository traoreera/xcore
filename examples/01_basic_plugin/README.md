# Basic Plugin Example

This example shows a minimal "Trusted" plugin that implements a simple greeting action.

## Structure
```
01_basic_plugin/
├── plugin.yaml
└── src/
    └── main.py
```

## Manifest (`plugin.yaml`)
```yaml
name: basic_plugin
version: "1.0.0"
execution_mode: trusted
entry_point: src/main.py
```

## Logic (`src/main.py`)
```python
from xcore.sdk import TrustedBase, AutoDispatchMixin, action, ok

class Plugin(AutoDispatchMixin, TrustedBase):
    @action("greet")
    async def greet(self, payload: dict):
        name = payload.get("name", "World")
        return ok(message=f"Hello, {name}!")
```
