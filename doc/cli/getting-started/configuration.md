---
title: CLI Configuration Guide
description: Configure your Xcore project using the central integration.yaml file.
icon: material/file-settings
---

# Configuration Guide

The heart of any `xcore` project is the `integration.yaml` file. This central configuration file defines how services, plugins, and the core system behave.

## The Role of `integration.yaml`

`integration.yaml` acts as the "Source of Truth" for your application. It controls:

- **App Metadata**: Name, environment, and debug settings.
- **FastAPI/Uvicorn**: Server host, port, and API documentation details.
- **Plugins**: Directory location, security keys, and hot-reload intervals.
- **Services**: Database connections (SQLAlchemy/Redis), caching, and task scheduling.
- **Worker**: Celery/XWorker configurations including brokers and queues.
- **Observability**: Logging levels, Prometheus metrics, and tracing.
- **Security**: AST-based whitelists for plugin sandboxing.

## Basic Structure

```yaml title="integration.yaml" linenums="1"
app:
  name: my-xcore-app
  env: development
  debug: true
  secret_key: "${XCORE_SECRET_KEY}"

plugins:
  directory: ./plugins
  secret_key: "${XCORE_PLUGINS_KEY}"
  strict_trusted: false
  interval: 10

services:
  databases:
    default:
      type: sqlasync
      url: "sqlite+aiosqlite:///db.sqlite3"
  cache:
    backend: memory
    ttl: 300
```

## Key Sections

### App & Server

Control the application identity and FastAPI/Uvicorn behavior.

```yaml
app:
  name: my-xcore-app
  env: production          # "development" | "production"
  debug: false
  secret_key: "${APP_KEY}"
  plugin_prefix: "/plugin" # base URL for all plugin routes
```

### Security & Sandboxing

The `security` section defines which Python modules are allowed within the plugin sandbox.

```yaml
security:
  strict_trusted: true          # require plugin.sig for all trusted plugins
  scan_on_load: true            # re-scan sandboxed plugins on every load
  allowed_imports:
    - fastapi
    - pydantic
    - json
    - datetime
    - math
  forbidden_imports:
    - os
    - subprocess
    - socket
```

### Plugin Management

Configure how plugins are loaded and verified.

```yaml
plugins:
  directory: ./plugins
  secret_key: "${PLUGINS_KEY}"  # must match the key used with `xcli plugin sign`
  strict_trusted: false
  interval: 2                   # hot-reload polling interval in seconds
```

!!! note "Plugin Verification"
    `plugins.secret_key` is used to verify HMAC-SHA256 signatures (`plugin.sig`) of your plugins. Set `strict_trusted: true` in production.

### Services

Full services configuration including multi-database support:

```yaml title="integration.yaml — services section" linenums="1"
services:
  databases:
    default:                               # aliased as 'db'
      type: "postgresql+aio"
      url: "postgresql+asyncpg://user:pass@localhost/mydb"
      pool_size: 20
      echo: false

    mongo:
      type: "mongodb"
      url: "mongodb://localhost:27017"
      database: "app_logs"

  cache:
    backend: "redis"
    url: "redis://localhost:6379/0"
    ttl: 300

  scheduler:
    enabled: true
    backend: "redis"
    timezone: "UTC"

  xworker:
    enabled: true
    broker_url: "redis://localhost:6379/0"
    result_backend: "redis://localhost:6379/0"
    queues: ["default", "high"]
    concurrency: 4
```

### Observability

Manage logs and metrics from one place.

```yaml
observability:
  logging:
    level: INFO
    format: "json"        # "text" | "json"
    file: log/app.log

  metrics:
    enabled: true
    export_interval: 60

  tracing:
    enabled: true
    sample_rate: 1.0
```

## Validation

`xcorecli` validates this file upon startup. Check your configuration manually:

```bash
xcli config validate

# Output on success:
# configuration valid (integration.yaml)
#   app.env          = development
#   plugins.dir      = ./plugins (3 plugins found)
#   services.db      = sqlite+aiosqlite — connected
#   services.cache   = memory — ready
```

## Environment Variable Overrides

Any value can be overridden using environment variables with the pattern `XCORE__SECTION__KEY`:

```bash
XCORE__SERVICES__CACHE__TTL=600
XCORE__APP__ENV=production
XCORE__PLUGINS__STRICT_TRUSTED=true
```

## See Also

[Authentication](auth.md)
:   Configure marketplace credentials and API keys.

[Xcore Configuration Reference](../../reference/xcore-config.md)
:   Complete reference for all configuration fields.
