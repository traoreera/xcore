# Exhaustive Configuration Reference

This reference covers every configuration key available in XCore's system and plugin manifests.

---

## 1. System Configuration (`xcore.yaml`)

The root configuration file controls the kernel and shared services. It supports environment variable injection using `${VARIABLE_NAME}`.

### `app` Section: Global Identity
| Key | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `name` | `str` | `xcore-app` | Logical name for the application. |
| `env` | `str` | `development` | Environment mode: `development`, `staging`, `production`. |
| `debug` | `bool` | `false` | Enables verbose logging and detailed error responses. |
| `secret_key` | `str` | - | Primary key for cryptographic operations. |
| `server_key` | `str` | - | High-entropy key for core-to-plugin authentication. |
| `plugin_prefix` | `str` | `/plugin` | Base URL prefix for all plugin-exposed HTTP routes. |

### `plugins` Section: Lifecycle & Discovery
| Key | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `directory` | `str` | `./plugins` | Filesystem path to search for plugins. |
| `autoload` | `bool` | `true` | Automatically load all valid plugins found in the directory. |
| `strict_trusted` | `bool` | `true` | In production, `trusted` plugins MUST have a valid `plugin.sig`. |
| `interval` | `int` | `2` | Polling interval (seconds) for the hot-reload watcher. |
| `entry_point` | `str` | `src/main.py` | Default entry point file for all plugins. |

### `services` Section: Shared Infrastructure

#### `database`
| Key | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `enabled` | `bool` | `true` | Enable/disable the global database manager. |
| `databases` | `dict` | `{}` | Map of named database configurations (see below). |

**Individual Database Entry:**
- `type`: `sqlite`, `postgresql`, `mysql`, `mongodb`.
- `url`: Connection string (e.g., `postgresql+asyncpg://...`).
- `pool_size`: Number of persistent connections (SQL only).
- `max_overflow`: Extra connections allowed during peak load (SQL only).
- `echo`: Log all SQL queries to the console.

#### `cache`
| Key | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `backend` | `str` | `memory` | `memory` or `redis`. |
| `url` | `str` | - | Redis URL (required if backend is `redis`). |
| `ttl` | `int` | `300` | Default expiration time in seconds. |
| `max_size` | `int` | `1000` | Maximum number of items for `memory` backend. |

#### `scheduler`
| Key | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `enabled` | `bool` | `true` | Enable/disable the APScheduler integration. |
| `backend` | `str` | `memory` | `memory` or `redis` (for persistent jobs). |
| `timezone` | `str` | `UTC` | Timezone for cron triggers. |

### `observability` Section: Monitoring
- **`logging`**: `level` (DEBUG/INFO/WARN/ERROR), `format`, `file`, `max_bytes`, `backup_count`.
- **`metrics`**: `enabled` (bool), `backend` (`prometheus`/`statsd`), `prefix`.
- **`tracing`**: `enabled` (bool), `backend` (`opentelemetry`/`jaeger`), `endpoint`.

---

## 2. Plugin Manifest (`plugin.yaml`)

Each plugin must have a `plugin.yaml` in its root directory.

### Identity
- `name` (str): Unique plugin ID.
- `version` (str): Semantic version.
- `execution_mode` (str): `trusted` (in-process) or `sandboxed` (isolated process).
- `entry_point` (str): Relative path to the `.py` file containing the `Plugin` class.

### Dependencies & Imports
- `requires` (list): List of plugins needed before this one can start.
- `allowed_imports` (list): Modules allowed in `sandboxed` mode (e.g., `math`, `json`, `pydantic`).

### Security (Permissions)
A list of policy rules:
```yaml
permissions:
  - resource: "db.users.*"  # Pattern matching
    actions: ["read", "write"]
    effect: allow           # allow | deny
```

### Resource Management (`resources`)
- `timeout_seconds` (int): Max time an IPC call can take.
- `max_memory_mb` (int): RAM limit for sandboxed processes.
- `max_disk_mb` (int): Disk limit for sandboxed processes.
- `rate_limit`:
    - `calls` (int): Max calls allowed in the period.
    - `period_seconds` (int): Rolling window duration.

### Runtime Behavior (`runtime`)
- `health_check`:
    - `enabled` (bool): Enable automatic health polling.
    - `interval_seconds` (int): Frequency.
- `retry`:
    - `max_attempts` (int): Retries on IPC failure.
    - `backoff_seconds` (float): Delay between retries.

### Filesystem & Env
- `filesystem.allowed_paths` (list): Paths relative to plugin root.
- `env` (dict): Environment variables passed to the plugin.
- `envconfiguration.inject` (bool): Automatically load a local `.env` file.
