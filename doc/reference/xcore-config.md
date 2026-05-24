---
title: Xcore Configuration
description: Full reference for the xcore.yaml (integration.yaml) configuration file.
icon: material/cog
---

# Xcore Configuration

The `xcore.yaml` (or `integration.yaml`) file is the central configuration point for your application. It uses a structured hierarchy to define system-wide settings, service connections, and security policies.

---

### Key Concepts

#### Resolution Order
Xcore loads configuration in the following order:
1.  **Default Values**: Hardcoded in the framework's dataclasses.
2.  **YAML / JSON File**: Loaded from `./xcore.yaml` or `./integration.yaml`.
3.  **Environment Overrides**: `XCORE__SECTION__KEY=value` (case-insensitive).
4.  **Substitution**: `${ENV_VAR}` placeholders are resolved at runtime.

#### Secret Key Protection
In `production` mode, Xcore will refuse to boot if any `secret_key` matches the default value `b"change-me-in-production"`.

---

### `app` Section
General application and FastAPI settings.

| Key | Type | Default | Description |
|:--- | :--- | :--- | :--- |
| `name` | `str` | `"xcore-app"`| Application identifier. |
| `env` | `str` | `"development"`| `development` or `production`. |
| `debug` | `bool`| `false` | Enable/disable FastAPI debug mode. |
| `secret_key` | `str` | *Required* | Global secret for signing and encryption. |
| `plugin_prefix`| `str` | `"/plugin"` | Base path for all plugin HTTP routes. |
| `dotenv` | `str` | `null` | Path to a `.env` file to load at startup. |

---

### `plugins` Section
Configuration for the plugin supervisor and loader.

| Key | Type | Default | Description |
|:--- | :--- | :--- | :--- |
| `directory` | `str` | `"./plugins"`| Root directory for plugin discovery. |
| `secret_key` | `str` | *Required* | Secret used for HMAC plugin signatures. |
| `strict_trusted`| `bool`| `true` | Enforce signature check for Trusted plugins. |
| `interval` | `int` | `2` | Polling interval (seconds) for hot-reload. |
| `entry_point` | `str` | `"src/main.py"`| Default entry point filename. |

---

### `services` Section
Manage databases, caches, and custom extensions.

#### `databases`
Map of connection names to adapter configurations.

```yaml
services:
  databases:
    main:                # Aliased as 'db' if first
      type: "postgresql+aio"
      url: "${DB_URL}"
      pool_size: 10
      echo: false
```

#### `cache`
| Key | Type | Default | Description |
|:--- | :--- | :--- | :--- |
| `backend` | `str` | `"memory"` | `memory` or `redis`. |
| `ttl` | `int` | `300` | Global TTL in seconds. |
| `max_size`| `int` | `1000` | Max entries (memory backend only). |
| `url` | `str` | `null` | Required for Redis backend. |

#### `scheduler`
| Key | Type | Default | Description |
|:--- | :--- | :--- | :--- |
| `enabled` | `bool`| `true` | Enable/disable the task scheduler. |
| `backend` | `str` | `"memory"` | `memory` or `redis`. |
| `timezone`| `str` | `"UTC"` | Default timezone for jobs. |

---

### `tenancy` Section
Configure multi-tenant isolation strategies.

| Key | Type | Default | Description |
|:--- | :--- | :--- | :--- |
| `enabled` | `bool`| `false` | Enable/disable multi-tenancy. |
| `header` | `str` | `"X-Tenant-ID"`| HTTP header for tenant extraction. |
| `subdomain`| `bool`| `false` | Extract tenant from subdomain. |
| `isolate_db`| `bool`| `true` | PostgreSQL schema isolation. |
| `isolate_cache`| `bool`| `true` | Key prefixing isolation. |
| `enforce_ipc`| `bool`| `true` | Verify caller authorization on every call. |

---

### `observability` Section
Logging, metrics, and tracing settings.

#### `logging`
| Key | Type | Default | Description |
|:--- | :--- | :--- | :--- |
| `level` | `str` | `"INFO"` | `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `format`| `str` | `"text"` | `text` or `json`. |
| `file` | `str` | `null` | Path to log file (enables file rotation). |

---

### YAML Example with Substitution

```yaml linenums="1"
app:
  env: "production"
  secret_key: "${XCORE_APP_KEY}"

plugins:
  directory: "/var/lib/xcore/plugins"
  secret_key: "${XCORE_PLUGINS_KEY}"

services:
  databases:
    default:
      type: "postgresql+aio"
      url: "postgresql+asyncpg://${DB_USER}:${DB_PASS}@${DB_HOST}/xcore"

  cache:
    backend: "redis"
    url: "redis://${REDIS_HOST}:6379/0"

tenancy:
  enabled: true
  header: "X-Customer-ID"
```

!!! tip "Environment Variable Overrides"
    You can override any value using environment variables:
    `XCORE__SERVICES__CACHE__TTL=600` will set the cache TTL to 10 minutes, bypassing the YAML file.
