# Runtime Management

Manage the operational state of your plugins without restarting the entire application.

## Controlling Plugin State

The `plugin runtime` command group provides direct control over the loading mechanism.

### Load a Plugin

If a plugin is installed but not active:

```bash
xcli plugin runtime load my-plugin
```

### Unload a Plugin

To temporarily disable a plugin and free up resources:

```bash
xcli plugin runtime unload my-plugin
```

### Reload a Plugin

Useful for applying updates or configuration changes:

```bash
xcli plugin runtime reload my-plugin
```

!!! tip "Hot Reloading"
    `xcore` supports automatic hot-reloading. Configure the `interval` in `integration.yaml` to enable it:
    ```yaml
    plugins:
      interval: 10 # Check every 10 seconds
    ```

## Direct Actions

### Call a Plugin Action

You can trigger a specific action within a plugin directly from the CLI, passing a JSON payload if required.

```bash
xcli plugin runtime call my-plugin send_email --payload '{"to": "user@example.com", "subject": "Hello"}'
```

## Monitoring Runtime Status

To see which plugins are currently loaded and their operational state (e.g., `running`, `initializing`):

```bash
xcli plugin runtime status
```

## Global Reload

To reload all active plugins at once:

```bash
xcli plugin runtime reload-all
```

!!! warning "State Persistence"
    When a plugin is reloaded, its in-memory state is lost. Ensure your plugins implement proper state persistence (e.g., via the `cache` service) if needed.
