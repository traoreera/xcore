---
title: CLI Configuration
description: Manage xcorecli settings, view merged configuration, and validate integration.yaml.
icon: material/tune
---

# CLI Configuration

The `config` command group allows you to manage the behavior of `xcorecli` itself and its interaction with the `xcore` project.

## Commands Overview

| Command | Description |
|---------|-------------|
| `show` | Display the current merged configuration |
| `get` | Retrieve a specific configuration value |
| `set` | Update a configuration value |
| `validate` | Check `integration.yaml` for schema compliance |

## Managing Settings

### View Current Configuration

Display the full merged configuration including defaults, `integration.yaml` values, and environment overrides:

```bash
xcli config show

# Merged Configuration
# ─────────────────────────────────────────────────────
#  app.name                 = my-xcore-app
#  app.env                  = development
#  app.debug                = true
#  plugins.directory        = ./plugins
#  plugins.strict_trusted   = false
#  plugins.interval         = 2
#  services.db.type         = sqlasync
#  services.cache.backend   = memory
#  marketplace.api_key      = xdk_****...****
# ─────────────────────────────────────────────────────
```

### Get a Specific Value

```bash
xcli config get app.env
# development

xcli config get plugins.strict_trusted
# false
```

### Update a Value

Modify settings directly from the CLI:

```bash title="Enable debug mode"
xcli config set app.debug true

title="Change plugin reload interval"
xcli config set plugins.interval 5
```

!!! note "Layered Configuration"
    `xcorecli` merges configuration from multiple sources in this priority order (highest first):

    1. Environment variables (`XCORE__SECTION__KEY=value`)
    2. Local CLI config (user-level overrides)
    3. `integration.yaml` (project-level)
    4. Internal framework defaults

### Validate Configuration

Check `integration.yaml` for schema compliance before deploying:

```bash
xcli config validate

# Validating integration.yaml...
# [OK] app section
# [OK] plugins section
# [OK] services.databases.default
# [WARN] services.xworker: broker_url not set — XWorker disabled
# Validation passed with 1 warning.
```

## Setting Credentials

Sensitive values like API keys should be set via the `config` command (not stored in `integration.yaml`):

```bash
xcli config set marketplace.api_key "xdk_your-token"
xcli config set plugins.secret_key "${XCORE_PLUGINS_KEY}"
```

## Runtime Configuration

Some settings can be adjusted without restarting the server:

```yaml title="integration.yaml"
plugins:
  interval: 5     # Hot-reload polling every 5 seconds
```

Apply live changes by reloading the service that owns the setting:

```bash
xcli manager services reload plugin_supervisor
```

!!! info "Dynamic Updates"
    Use `xcli manager services reload <name>` to apply configuration changes without a full restart. Changes to `app.secret_key` or database URLs always require a full restart.

## See Also

[Configuration Guide](../getting-started/configuration.md)
:   Complete reference for `integration.yaml` sections and fields.
