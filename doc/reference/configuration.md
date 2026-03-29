# Detailed Configuration Reference

This reference covers every configuration key available in XCore's system and plugin manifests.

## 1. System Configuration (`xcore.yaml`)

The root configuration controls the kernel and shared services.

### `app` Section: Global Settings
- `name` (str): The logical name of your application.
- `env` (str): Environment identifier (`development`, `staging`, `production`).
- `debug` (bool): If True, enables verbose logging and detailed error messages.
- `secret_key` (str): Used for cryptographic operations within plugins.
- `server_key` (str): High-entropy key used for core-to-plugin authentication and signing.
- `plugin_prefix` (str): Base URL for all plugin-exposed HTTP routes.

### `plugins` Section: Loader Settings
- `directory` (str): Filesystem path to the plugins folder.
- `autoload` (bool): If True, all valid plugins in the directory are loaded at boot.
- `strict_trusted` (bool): If True, `trusted` plugins MUST have a valid `plugin.sig` file.
- `interval` (int): Polling interval in seconds for the hot-reload watcher.

### `services` Section: Shared Infrastructure
#### `database`
- `enabled` (bool): Enable the database manager.
- `databases` (dict): A map of named database connections.
    - `url` (str): Connection string (e.g., `postgresql+asyncpg://...`).
    - `pool_size` (int): Number of permanent connections.
    - `max_overflow` (int): Extra connections allowed during peak load.
#### `cache`
- `backend` (str): `memory` or `redis`.
- `url` (str): Redis URL (required if backend is `redis`).
- `ttl` (int): Default expiration time in seconds.
#### `scheduler`
- `enabled` (bool): Enable APScheduler integration.
- `backend` (str): `memory` or `redis` (for persistent jobs).

### `observability` Section: Monitoring
- `logging.level` (str): `DEBUG`, `INFO`, `WARNING`, `ERROR`.
- `metrics.enabled` (bool): Enable Prometheus metric collection.
- `tracing.enabled` (bool): Enable OpenTelemetry tracing.

---

## 2. Plugin Manifest (`plugin.yaml`)

The manifest defines how a plugin behaves and what it can access.

### Identity & Type
- `name` (str): Unique plugin ID.
- `version` (str): Semantic version (e.g., `1.2.3`).
- `execution_mode` (str): `trusted` or `sandboxed`.
- `entry_point` (str): Path to the `.py` file containing the `Plugin` class.

### Dependencies & Imports
- `requires` (list): List of plugins needed before this one can start. Supports versioning:
  ```yaml
  requires:
    - name: user_api
      version: ">=2.0.0"
  ```
- `allowed_imports` (list): Modules allowed in `sandboxed` mode (AST whitelisting).

### Security (Permissions)
- `permissions` (list): List of policy rules.
    - `resource` (str): Resource pattern (e.g., `db.*`).
    - `actions` (list): List of strings (e.g., `["read", "write"]`).
    - `effect` (str): `allow` or `deny`.

### Resource Management
- `resources`:
    - `timeout_seconds` (int): Max time an IPC call can take.
    - `max_memory_mb` (int): Max RAM usage for the sandbox.
    - `rate_limit`:
        - `calls` (int): Max calls allowed in the period.
        - `period_seconds` (int): Rolling window duration.

### Runtime Behavior
- `runtime.health_check`:
    - `enabled` (bool): Enable automatic health checks.
    - `interval_seconds` (int): Frequency.
- `runtime.retry`:
    - `max_attempts` (int): Retries on failure.
    - `backoff_seconds` (float): Delay between retries.

### Environment Injection
- `env` (dict): Environment variables available via `self.ctx.env`. Supports `${VAR}` expansion from the host.
- `envconfiguration.inject` (bool): If True, loads a `.env` file from the plugin root.
