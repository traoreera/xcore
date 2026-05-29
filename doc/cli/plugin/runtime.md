---
title: Runtime Plugin Control
description: Load, unload, reload, and call plugin actions without restarting the application.
icon: material/play-circle
---

# Runtime Plugin Control

Manage the operational state of your plugins without restarting the entire application.

## Controlling Plugin State

The `plugin runtime` command group provides direct control over the loading mechanism.

### Load a Plugin

Activate an installed but inactive plugin:

```bash
xcli plugin runtime load my-plugin
# Loading plugin 'my-plugin'...
# my-plugin v1.0.0 — loaded successfully (243ms)
```

### Unload a Plugin

Temporarily disable a plugin and free its resources:

```bash
xcli plugin runtime unload my-plugin
# on_stop called
# on_unload called
# Plugin 'my-plugin' unloaded.
```

### Reload a Plugin

Apply code changes or configuration updates without restarting the server:

```bash
xcli plugin runtime reload my-plugin
# Reloading 'my-plugin'...
# on_stop -> on_unload -> on_load -> on_start
# Reloaded in 312ms
```

!!! tip "Hot Reloading"
    Enable automatic hot-reload by setting an `interval` in `integration.yaml`:
    ```yaml
    plugins:
      interval: 2    # Poll for file changes every 2 seconds
    ```

### Reload All Plugins

Reload every active plugin at once — useful after a framework upgrade:

```bash
xcli plugin runtime reload-all
# Reloading 3 plugins...
# auth_plugin       OK  (198ms)
# billing_engine    OK  (421ms)
# analytics_plugin  OK  (112ms)
```

## Calling Plugin Actions

Trigger a specific action directly from the CLI — useful for debugging and manual testing:

```bash title="Call with JSON payload"
xcli plugin runtime call my-plugin greet --payload '{"name": "World"}'
# Response:
# {"status": "ok", "message": "Hello, World!"}
```

```bash title="Call without payload"
xcli plugin runtime call my-plugin ping
# {"status": "ok", "pong": true}
```

## Monitoring Runtime Status

See which plugins are currently loaded and their operational state:

```bash
xcli plugin runtime status

# Plugin Runtime Status
# ─────────────────────────────────────────────────────
#  Name               Mode       State         Uptime
#  auth_plugin        trusted    RUNNING        3h 14m
#  billing_engine     trusted    RUNNING        3h 14m
#  sandbox_proc       sandboxed  RUNNING        3h 14m
#  experimental       sandboxed  INITIALIZING   12s
# ─────────────────────────────────────────────────────
```

### Plugin States

| State | Meaning |
|-------|---------|
| `INITIALIZING` | Plugin is being loaded (calling `on_load`) |
| `RUNNING` | Plugin is active and processing calls |
| `STOPPING` | Plugin is being unloaded (calling `on_stop`) |
| `FAILED` | Plugin threw an unhandled exception during load |

!!! warning "State Persistence"
    When a plugin is reloaded, all in-memory state is lost. Use the `cache` service to persist state across reloads:
    ```python
    async def on_load(self):
        await super().on_load()
        # Restore state from cache instead of instance variables
        self._state = await self.cache.get("my_plugin:state") or {}
    ```
