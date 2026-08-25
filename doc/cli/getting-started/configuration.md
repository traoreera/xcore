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

```yaml title="integration.yaml"
app:
  name: my-xcore-app
  env: development
  debug: true

plugins:
  directory: ./plugins
  strict_trusted: true
  interval: 10

services:
  databases:
    db:
      type: sqlasync
      url: sqlite+aiosqlite:///db.sqlite3
```

## Key Sections

### Security & Sandboxing
The `security` section defines which Python modules are allowed within the plugin sandbox.

```yaml
security:
  allowed_imports:
    - fastapi
    - json
    - datetime
  forbidden_imports:
    - os
```

### Plugin Management
Configure how plugins are loaded and verified.

!!! note "Plugin Verification"
    `plugins.secret_key` is used to verify HMAC-SHA256 signatures (`plugin.sig`) of your plugins.

### Observability
Manage logs and metrics from one place.

```yaml
observability:
  logging:
    level: INFO
    file: log/app.log
```

## Validation

`xcorecli` validates this file upon startup to ensure all required fields are present and correctly typed — there is no separate command to check it manually ahead of time; `xcli manager start` (or any command that touches the running project) is itself the validation step. This is unrelated to [`xcli config`](../config/index.md), which only stores your marketplace API/signing keys, not `integration.yaml` settings.
