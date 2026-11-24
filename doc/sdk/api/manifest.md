---
title: Manifest
description: PluginManifest, ResourceConfig, and RuntimeConfig — plugin.yaml Python representation.
icon: material/file-code
---

# Manifest

Every xcore plugin requires a `plugin.yaml` manifest in its root directory. The manifest declares metadata, execution mode, environment variables, resource limits, and runtime configuration.

```python
from xcore.sdk import PluginManifest, ResourceConfig, RuntimeConfig
```

---

## plugin.yaml reference

```yaml
# ── Identity ──────────────────────────────────────────────────────────────────
name: my_plugin                 # unique plugin identifier (snake_case)
version: 1.0.0                  # semver

# ── Execution ─────────────────────────────────────────────────────────────────
execution_mode: trusted         # trusted | sandboxed | legacy

# ── Service contract (checked at LOAD time) ───────────────────────────────────
requires_services:              # the plugin is refused if one is missing or too old
  - doctype_registry
  - name: doctype_writer
    version: ">=2"
provides_services:              # what this plugin exports, with its contract version
  - name: billing_api
    version: "1.2"

# ── Python dependencies (checked by xcore-plugin-check) ───────────────────────
dependencies:
  - cryptography>=42

# ── Environment variables ─────────────────────────────────────────────────────
env:
  MY_SECRET: "${MY_SECRET}"                 # value injected at runtime, default = ""
  MAX_ITEMS: "100"

# ── Resource limits ───────────────────────────────────────────────────────────
resources:
  timeout_seconds: 15           # per-action timeout
  rate_limit:
    requests: 200               # max requests
    window_seconds: 60          # per window

# ── Runtime options ───────────────────────────────────────────────────────────
runtime:
  health_check: true            # expose @health_check endpoints
  retry:
    max_attempts: 2             # auto-retry on transient failure
    backoff_seconds: 1.0
```

---

## Service contract

`get_service("doctype_writer")` fails at **call** time. Declaring the service in the manifest moves the failure to **load** time, in the deployment logs:

- a consumer whose required service has no provider, or whose version constraint is not met, is refused before any of its code runs — the message names both plugins;
- providers are loaded before their consumers, even without `requires`;
- a plugin that declares `provides_services` but has not exported the service by the end of `on_load` is refused; so is a second plugin declaring an already provided service;
- kernel services (`db`, `cache`, `scheduler`…) satisfy a requirement without a version constraint.

## Python dependencies

`xcore-plugin-check` compares what a plugin imports with what it declares (`pyproject.toml`, `requirements.txt`, or `dependencies:` above) and exits with status 1 when a package is missing — run it in the plugin's CI:

```bash
xcore-plugin-check plugins/erp_mail          # or: python -m xcore.kernel.security.dependencies
```

Ignored: the standard library, the plugin's own modules, `if TYPE_CHECKING:` blocks and imports guarded by `try/except ImportError`. xcore and its core dependencies (fastapi, pydantic, pyyaml…) are provided by the host; its extras (sqlalchemy, redis, celery…) must be declared. The same check runs at load time as a non-blocking warning (`plugins.check_dependencies`).

## Execution modes

| Value | Description |
|-------|-------------|
| `trusted` | Full kernel access. Can call `get_service()`, emit events, access all APIs. |
| `sandboxed` | Restricted access. Cannot access services directly; action calls go through a proxy. |
| `legacy` | Compatibility mode for plugins written before the current API. |

---

## PluginManifest

Pydantic model representing a parsed `plugin.yaml`.

```python
from xcore.sdk import PluginManifest

manifest = PluginManifest(
    name="my_plugin",
    version="1.0.0",
    execution_mode="trusted",
)

manifest.name            # str
manifest.version         # str
manifest.execution_mode  # ExecutionMode
manifest.env             # dict[str, str]
manifest.resources       # ResourceConfig | None
manifest.runtime         # RuntimeConfig | None
```

---

## ResourceConfig

```python
from xcore.sdk import ResourceConfig

config = ResourceConfig(
    timeout_seconds=15,
    rate_limit={"requests": 200, "window_seconds": 60},
)
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `timeout_seconds` | `int` | `30` | Per-action timeout |
| `rate_limit` | `dict \| None` | `None` | Rate limiting config |

---

## RuntimeConfig

```python
from xcore.sdk import RuntimeConfig

config = RuntimeConfig(
    health_check=True,
    retry={"max_attempts": 3, "backoff_seconds": 1.0},
)
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `health_check` | `bool` | `False` | Enable health check exposure |
| `retry` | `dict \| None` | `None` | Auto-retry configuration |

---

## Minimal manifest

```yaml
name: my_plugin
version: 1.0.0
execution_mode: trusted
```

This is the minimum required manifest. All other fields are optional.

---

## Environment variable injection

Variables declared under `env` are injected into `self.ctx.env` at plugin load time. The kernel reads them from the process environment:

```yaml
env:
  DATABASE_URL: ""
  API_KEY: ""
```

```python
async def on_load(self) -> None:
    await super().on_load()
    db_url = self.ctx.env.get("DATABASE_URL", "sqlite:///local.db")
```

Missing env vars default to the value specified in the manifest (empty string if `""`).
