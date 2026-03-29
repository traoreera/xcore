# XCore Plugin Examples

This directory contains complete examples of plugins for the XCore framework, illustrating different execution modes and advanced patterns.

## Table of Contents

| Example | Mode | Complexity | Description |
|---------|------|------------|-------------|
| [Basic Plugin](./basic-plugin.md) | Trusted | Beginner | Simple calculator plugin with HTTP and IPC endpoints. |
| [Trusted Plugin](./trusted-plugin.md) | **Trusted** | Advanced | Task manager with separate `router.py` and `.env` configuration. |
| [Sandboxed Plugin](./sandboxed-plugin.md) | **Sandboxed** | Advanced | Secure document converter with process isolation. |
| [Complete Plugin](./complete-plugin.md) | **Trusted** | Advanced | Email notification service with event integration. |

---

## Choosing the Execution Mode

```
┌─────────────────────────────────────────────────────────────────┐
│                    Which mode to choose?                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐          ┌──────────────────┐               │
│  │   Trusted    │          │    Sandboxed     │               │
│  │              │          │                  │               │
│  │ • DB Access  │          │ • Max Isolation  │               │
│  │ • Services   │          │ • Resource       │               │
│  │ • Extended   │          │   Limits         │               │
│  │   Filesystem │          │ • Import         │               │
│  │              │          │   Whitelist      │               │
│  └──────┬───────┘          └────────┬─────────┘               │
│         │                           │                          │
│         ▼                           ▼                          │
│  ┌─────────────────┐      ┌────────────────────┐              │
│  │ User Management │      │ File Processing    │              │
│  │ Notifications   │      │ Doc Conversion     │              │
│  │ Complex Caching │      │ Code Execution     │              │
│  │ Analytics       │      │ Compression        │              │
│  └─────────────────┘      └────────────────────┘              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Typical Plugin Structure

### Trusted Mode (with .env)

```
plugins/my_plugin/
├── plugin.yaml          # Manifest + structural config
├── .env                 # Sensitive variables (not committed)
├── src/
│   ├── __init__.py
│   ├── main.py         # Entry point, lifecycle
│   ├── router.py       # FastAPI HTTP routes
│   ├── services.py     # Business logic
│   └── models.py       # Dataclasses/Pydantic models
└── data/               # Local persistence
    └── ...
```

### Sandboxed Mode

```
plugins/my_plugin/
├── plugin.yaml          # Manifest with restrictions
├── src/
│   ├── __init__.py
│   ├── main.py         # Sandboxed Plugin
│   ├── router.py       # HTTP Routes
│   └── logic.py        # Isolated logic
└── data/temp/          # Temporary workspace
```

---

## Pattern: Separate Router.py

Advanced examples utilize a pattern of separating HTTP routes from core logic.

### Benefits

1.  **Separation of Concerns**: HTTP routing is isolated from business logic.
2.  **Testability**: Routes can be tested independently.
3.  **Readability**: `main.py` remains focused on lifecycle and IPC actions.
4.  **Reusability**: Business logic can be used without the HTTP layer.

### Implementation

```python
# src/router.py
def create_router(plugin_instance) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["my-plugin"])

    @router.get("/items")
    async def list_items():
        return await plugin_instance.service.get_items()

    return router

# src/main.py
class Plugin(TrustedBase):
    def get_router(self) -> APIRouter | None:
        from .router import create_router
        return create_router(self)
```

---

## Pattern: Configuration via .env (Trusted only)

### Structure

```yaml
# plugin.yaml
env:
  DB_POOL_SIZE: "10"
  API_KEY: ""

envconfiguration:
  inject: true        # Injects variables into ctx.env
  required: true      # Fails if .env is missing
```

```bash
# .env (not committed)
DB_POOL_SIZE=20
API_KEY=sk_live_xxx
SECRET_KEY=super_secret
```

### Usage

```python
async def on_load(self):
    self.config = {
        "pool_size": int(self.ctx.env.get("DB_POOL_SIZE", "10")),
        "api_key": self.ctx.env.get("API_KEY"),
    }
```

---

## Key Points by Mode

### Trusted

- ✅ Full access to services (DB, Cache, Email, Scheduler).
- ✅ Configurable filesystem access.
- ✅ Unlimited Python imports.
- ✅ Configuration via `.env`.
- ⚠️ Beware of SQL injection and XSS.
- ⚠️ Validate all user inputs.

### Sandboxed

- 🔒 Complete system isolation.
- 🔒 Limited resources (memory, CPU, disk).
- 🔒 Import whitelisting.
- 🔒 Operation timeouts.
- ✅ Ideal for file processing.
- ❌ No direct DB access.

---

## Quick Commands

### Create a New Plugin

```bash
# Basic structure
mkdir -p plugins/my_plugin/src plugins/my_plugin/data

# Necessary files
touch plugins/my_plugin/plugin.yaml
touch plugins/my_plugin/src/__init__.py
touch plugins/my_plugin/src/main.py

# If Trusted with .env
touch plugins/my_plugin/.env
echo ".env" >> plugins/my_plugin/.gitignore
```

### Test a Plugin

```bash
# Start XCore
make run-dev

# Test HTTP
curl http://localhost:8082/plugins/my_plugin/health

# Test IPC
curl -X POST http://localhost:8082/app/my_plugin/action \
  -H "Content-Type: application/json" \
  -d '{"key": "value"}'
```

---

## Additional Resources

- [Main Documentation](../index.md)
- [SDK Reference](../reference/sdk.md)
- [Security Guide](../guides/security.md)
- [Troubleshooting](../guides/troubleshooting.md)
