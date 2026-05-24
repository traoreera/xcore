---
title: Quickstart
description: Get Xcore up and running with FastAPI in less than 5 minutes.
icon: material/lightning-bolt
---

# Quickstart

This guide will show you how to integrate Xcore into a FastAPI application, load a simple plugin, and call its methods.

### 1. Project Structure

Create a new project directory with the following structure:

```text
my_app/
├── main.py
├── xcore.yaml
└── plugins/
    └── hello_plugin/
        ├── plugin.yaml
        └── src/
            └── main.py
```

---

### 2. Configuration

Create an `xcore.yaml` file to configure the framework:

```yaml linenums="1"
app:
  name: "demo-app"
  env: "development"
  secret_key: "debug-key"

plugins:
  directory: "./plugins"
```

---

### 3. Create a Plugin

#### Manifest (`plugin.yaml`)
Define your plugin's metadata and entry point.

```yaml linenums="1"
name: "hello_plugin"
version: "1.0.0"
mode: "trusted"  # (1)!
entry_point: "src/main.py"
permissions: []  # (2)!
```

1.  **Trusted Mode**: Runs in the main process with full access.
2.  **Fail-closed**: An empty list means no special permissions are granted.

#### Logic (`src/main.py`)
Implement the `TrustedBase` contract.

```python linenums="1"
from xcore import TrustedBase, ok

class Plugin(TrustedBase):
    async def handle(self, action: str, payload: dict) -> dict:
        if action == "greet":
            name = payload.get("name", "World")
            return ok(message=f"Hello, {name}!")

        return {"status": "error", "msg": "Unknown action"}
```

---

### 4. Integrate with FastAPI

In your `main.py`, initialize and boot the Xcore kernel.

```python linenums="1" hl_lines="8 12 14"
from fastapi import FastAPI
from xcore import Xcore
from contextlib import asynccontextmanager

# 1. Initialize the Kernel
xcore = Xcore(config_path="xcore.yaml")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 2. Boot Xcore (loads services and plugins)
    await xcore.boot(app)
    yield
    # 3. Graceful shutdown
    await xcore.shutdown()

app = FastAPI(lifespan=lifespan)

@app.get("/hello/{name}")
async def hello(name: str):
    # 4. Call the plugin
    result = await xcore.plugins.call("hello_plugin", "greet", {"name": name})
    return result
```

---

### 5. Run the Application

Start the server using Uvicorn:

```bash
uvicorn main:app --reload
```

Now, visit `http://127.0.0.1:8000/hello/Xcore` in your browser. You should see:

```json
{
  "status": "ok",
  "message": "Hello, Xcore!"
}
```

---

### Common Pitfalls

!!! danger "Production Boot Failure"
    If you set `app.env: "production"`, Xcore will raise a `RuntimeError` if your `secret_key` is set to the default value (`b"change-me-in-production"`). Always use a secure, unique key in production.

!!! warning "Permissions are fail-closed"
    If your plugin needs to access certain services or perform restricted actions, you must explicitly declare them in the `plugin.yaml` manifest.

---

### Next Steps

- [x] You have a running Xcore application.
- [ ] Learn about [Execution Modes](../kernel/execution-modes.md) (Trusted vs. Sandboxed).
- [ ] Explore the [Service Container](../services/services.md) to access Databases and Cache.
- [ ] Understand the [Plugin Lifecycle](../kernel/kernel.md).
