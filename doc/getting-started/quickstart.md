# Quick Start Guide

Build your first XCore application and plugin in under 5 minutes.

---

## 1. Initialize the Application

Create a new file `app.py`. This will be the entry point for your FastAPI server.

```python
# app.py
from fastapi import FastAPI
from xcore import Xcore

app = FastAPI(title="My XCore App")
core = Xcore(config_path="xcore.yaml")

@app.on_event("startup")
async def startup():
    # This boots the kernel, services, and all plugins
    await core.boot(app)

@app.on_event("shutdown")
async def shutdown():
    await core.shutdown()
```

---

## 2. Create Your First Plugin

Plugins live in the `./plugins` directory by default.

### A. Directory Structure
```bash
mkdir -p plugins/hello_plugin/src
touch plugins/hello_plugin/plugin.yaml
touch plugins/hello_plugin/src/main.py
```

### B. The Manifest (`plugin.yaml`)
```yaml
name: hello_plugin
version: "1.0.0"
execution_mode: trusted
entry_point: src/main.py
```

### C. The Logic (`src/main.py`)
```python
from xcore.sdk import TrustedBase, AutoDispatchMixin, action, ok

class Plugin(AutoDispatchMixin, TrustedBase):
    async def on_load(self):
        self.logger.info("Hello plugin is ready!")

    @action("greet")
    async def greet_user(self, payload: dict):
        name = payload.get("name", "World")
        return ok(message=f"Hello, {name}!")
```

---

## 3. Run and Test

### Start the Server
```bash
uvicorn app:app --reload
```

### Call via CLI
In a new terminal, invoke your plugin's action:
```bash
xcore plugin call hello_plugin greet '{"name": "Developer"}'
```
**Response**: `{"status": "ok", "message": "Hello, Developer!"}`

### Call via HTTP
By default, XCore mounts plugin routes. Try visiting:
`http://localhost:8000/plugin/hello_plugin/` (if you added routes).

---

## Next Steps

-   [**Learn the SDK**](../reference/sdk.md): Discover decorators like `@route` and `@validate_payload`.
-   [**Shared Services**](../guides/services.md): Learn how to use the Database and Cache.
-   [**Sandboxing**](../guides/security.md): Secure your app by isolating plugins.
