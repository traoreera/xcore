# CLI Reference

The `xcore` CLI is the primary tool for managing plugins, sandboxes, and the marketplace from the terminal.

## General Usage

```bash
PYTHONPATH=. python -m xcore.cli.main [COMMAND] [OPTIONS]
```
*(If installed via pip/poetry, you can simply use `xcore [COMMAND]`)*

---

## 1. Plugin Management (`plugin`)

Commands for interacting with the framework's plugins.

### `list`
Lists all discovered plugins and their current status.
```bash
xcore plugin list
```

### `load` / `unload`
Manually load or unload a plugin.
```bash
xcore plugin load my_plugin
xcore plugin unload my_plugin
```

### `reload`
Hot-reloads a plugin's code and manifest.
```bash
xcore plugin reload my_plugin
```

### `call`
Invokes an IPC action on a running plugin.
```bash
xcore plugin call my_plugin my_action '{"key": "value"}'
```

### `sign`
Generates a `plugin.sig` HMAC signature for a plugin directory.
```bash
xcore plugin sign ./plugins/my_plugin --key YOUR_SECRET_KEY
```

---

## 2. Sandbox Management (`sandbox`)

Tools for inspecting and testing sandboxed plugins.

### `limits`
Displays the resource limits and current consumption for a sandboxed plugin.
```bash
xcore sandbox limits my_plugin
```

### `network`
Audits and displays the network access policy for a sandbox.
```bash
xcore sandbox network my_plugin
```

### `fs`
Displays the allowed and denied filesystem paths for a sandbox.
```bash
xcore sandbox fs my_plugin
```

---

## 3. Marketplace (`marketplace`)

Commands for interacting with the official XCore Marketplace.

### `search`
Search for plugins in the marketplace.
```bash
xcore marketplace search "auth"
```

### `info`
Get detailed metadata for a specific marketplace plugin.
```bash
xcore marketplace info auth-provider
```

### `install`
Downloads and installs a plugin from the marketplace.
```bash
xcore marketplace install auth-provider
```

---

## 4. Validation & Utility

### `validate`
Checks a plugin's `plugin.yaml` and `src/` for syntax errors and security violations.
```bash
xcore validate ./plugins/my_plugin
```

### `health`
Displays the health status of the kernel and all registered services.
```bash
xcore health
```
