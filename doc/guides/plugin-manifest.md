# Plugin Manifest (`plugin.yaml`)

Every plugin is described by a `plugin.yaml` at the root of its directory. This file controls execution mode, permissions, resources, IPC security, and metadata.

---

## Full Reference

```yaml
# ── Identity ──────────────────────────────────────────────────────────────
name: my_plugin              # required — must be unique across all plugins
version: "1.0.0"             # required — semver string
author: "XCore Team"
description: "What this plugin does"
framework_version: ">=2.0"   # minimum XCore version required

# ── Execution ──────────────────────────────────────────────────────────────
execution_mode: trusted      # trusted | sandboxed | legacy
entry_point: src/main.py     # path relative to the plugin directory

# ── Dependencies ───────────────────────────────────────────────────────────
requires:
  - auth_plugin                        # any version
  - name: database_helper
    version: ">=1.2,<2.0"              # semver constraint

# ── Permissions (RBAC) ────────────────────────────────────────────────────
permissions:
  - resource: "cache.*"
    actions: ["read", "write"]
    effect: allow
  - resource: "db.users"
    actions: ["read"]
    effect: allow
  - resource: "db.admin"
    actions: ["*"]
    effect: deny

# ── IPC Access Control ────────────────────────────────────────────────────
# deny-by-default: empty list blocks all IPC callers
# ["*"] to allow all plugins
allowed_callers:
  - auth_plugin
  - billing_plugin

# ── Environment ───────────────────────────────────────────────────────────
env:
  API_KEY: "${EXTERNAL_API_KEY}"   # ${VAR} substitution supported
  TIMEOUT: "30"

# ── Sandboxed import whitelist (extends global security.allowed_imports) ──
allowed_imports:
  - statistics
  - decimal

# ── Resource limits ───────────────────────────────────────────────────────
resources:
  timeout_seconds: 10          # max time for a single handle() call
  max_memory_mb: 128           # RSS memory cap (sandboxed only)
  max_disk_mb: 50              # disk I/O cap (sandboxed only)
  rate_limit:
    calls: 200                 # max handle() calls
    period_seconds: 60

# ── Runtime options ───────────────────────────────────────────────────────
runtime:
  health_check:
    enabled: true
    interval_seconds: 30
    timeout_seconds: 3
  retry:
    max_attempts: 3
    backoff_seconds: 1.0

# ── Filesystem access (sandboxed only) ────────────────────────────────────
filesystem:
  allowed_paths: ["data/"]
  denied_paths: ["src/"]

# ── Arbitrary extra config (available as self.ctx.manifest.extra) ─────────
my_feature_flag: true
api_endpoint: "https://api.example.com"
```

---

## Required Fields

| Field | Type | Description |
|:------|:-----|:------------|
| `name` | `str` | Unique plugin identifier (snake_case) |
| `version` | `str` | Semver version string |

---

## Execution Modes

| Mode | Process | Imports | Sig required |
|:-----|:--------|:--------|:-------------|
| `trusted` | Main FastAPI process | Unrestricted | When `strict_trusted: true` |
| `sandboxed` | Isolated OS subprocess | AST whitelist | No |
| `legacy` | Main process | Unrestricted | No |

---

## Dependencies

```yaml
requires:
  - other_plugin              # any version — shorthand
  - name: other_plugin
    version: "*"              # explicit — any version
  - name: other_plugin
    version: ">=2.0,<3.0"    # semver range
  - name: other_plugin
    version: "^1.5"           # ^1.5 := >=1.5, <2.0
  - name: other_plugin
    version: "~1.5.0"         # ~1.5.0 := >=1.5.0, <1.6.0
```

XCore resolves a dependency DAG and loads plugins in topological order.

---

## Permissions

```yaml
permissions:
  - resource: "cache.*"           # glob pattern
    actions: ["read", "write"]    # specific actions
    effect: allow

  - resource: "db.*"
    actions: ["*"]                # all actions
    effect: allow

  - resource: "db.admin"
    actions: ["delete"]
    effect: deny                  # deny-by-default: explicit deny
```

**Resource naming convention:** `service.collection` or `service.*` for all collections.

---

## IPC Access Control

```yaml
allowed_callers:
  - auth_plugin        # only these plugins may call this plugin via IPC
  - billing_plugin
```

| Value | Effect |
|:------|:-------|
| `[]` (empty) | All IPC calls blocked |
| `["*"]` | All plugins allowed |
| `["plugin_a", "plugin_b"]` | Only named plugins allowed |

Enforcement is enabled globally with `tenancy.enforce_ipc: true`.

---

## Rate Limits

Overrides the global default set in `integration.yaml → security.rate_limit_default`:

```yaml
resources:
  rate_limit:
    calls: 50
    period_seconds: 60   # 50 calls per minute
```

---

## Extra Fields

Any unrecognized keys are collected into `manifest.extra` and accessible at runtime:

```python
# plugin.yaml
my_api_url: "https://api.example.com"

# src/main.py
async def on_load(self):
    self.api_url = self.ctx.manifest.extra.get("my_api_url")
```
