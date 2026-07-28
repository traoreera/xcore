---
title: Plugin Development Guide
description: Step-by-step guide to building, testing, and deploying Xcore plugins.
icon: material/xml
---

# Plugin Development Guide

This guide provides a comprehensive walkthrough for creating a new Xcore plugin, from the initial directory setup to production deployment.

---

### 1. Initialization

Use the `xcore` CLI to scaffold a new plugin. This ensures you follow the standard directory structure and have a valid manifest.

```bash
# In your project root
mkdir -p plugins/my_plugin
cd plugins/my_plugin
xcore plugin init --mode trusted
```

This will create:
- `plugin.yaml`: The manifest file.
- `src/main.py`: The entry point with a boilerplate `Plugin` class.
- `src/__init__.py`: To make `src` a package.
- `tests/`: A folder for your unit tests.

---

### 2. Implementing Logic

Open `src/main.py` and implement your business logic. For **Trusted** plugins, inherit from `TrustedBase`.

```python linenums="1"
from xcore import TrustedBase, ok, error

class Plugin(TrustedBase):
    async def on_load(self):
        # Resolve services once
        self.db = self.get_service("db")
        print(f"[{self.name}] loaded")

    async def handle(self, action: str, payload: dict) -> dict:
        if action == "save_data":
            data = payload.get("data")
            # Business logic here...
            return ok(msg="Data saved successfully")

        return error(f"Action '{action}' not found", code="not_found")
```

---

### 3. Declaring Dependencies

If your plugin needs to call another plugin, declare it in `plugin.yaml`. Xcore will ensure the dependency is loaded before your plugin.

```yaml title="plugin.yaml"
name: "my_plugin"
requires:
  - name: "auth_service"
    version: "^2.0.0"

permissions:
  - resource: "plugin:auth_service"
    actions: ["execute"]
```

---

### 4. Testing your Plugin

Xcore encourages testing plugins in isolation. You can use the `Xcore` instance in your tests to simulate the full environment.

```python linenums="1" title="tests/test_my_plugin.py"
import pytest
from xcore import Xcore

@pytest.mark.asyncio
async def test_save_data():
    # Setup a minimal Xcore instance for testing
    app = Xcore(config_path="test_config.yaml")
    await app.boot()

    # Call your plugin
    result = await app.plugins.call("my_plugin", "save_data", {"data": "test"})

    assert result["status"] == "ok"
    await app.shutdown()
```

---

### 5. Production Readiness

Before deploying to production, especially if `strict_trusted` is enabled, you must sign your plugin.

#### Step 1: Verification
Run the built-in scanner to check for common issues.
```bash
xcore plugin verify ./plugins/my_plugin
```

#### Step 2: Signing
Generate the HMAC signature file.
```bash
xcore plugin sign ./plugins/my_plugin --key YOUR_SECRET_KEY
```

---

### Deployment Checklist

- [ ] `plugin.yaml` version is bumped.
- [ ] `execution_mode` is correctly set.
- [ ] `permissions` are as restrictive as possible.
- [ ] Unit tests pass with 100% coverage.
- [ ] `plugin.sig` is generated and up-to-date.

---

### Next Steps

- [Events & Hooks](./events-hooks.md): Learn how to communicate asynchronously.
- [Custom Services](../services/custom-services.md): Learn how to expose new capabilities to other plugins.
- [Security Best Practices](../security/security.md): Deep dive into the isolation layers.
