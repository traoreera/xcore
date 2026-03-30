# XCore Versions

This page lists the version history of the XCore framework, major changes, and update notes.

## Current Version

### XCore v2.0.0 (Stable)

**Release Date**: March 2025

**Status**: ✅ Stable and Recommended

Version 2.0 is a complete rewrite of the framework with a plugin-first architecture, a reinforced sandboxing system, and native service integration.

#### Main Features

- **🏗️ Plugin-First Architecture** — The core is minimal; all features are implemented as plugins.
- **🔒 Sandboxing System** — Isolated plugin execution with AST and IPC restrictions.
- **⚡ Native FastAPI Integration** — Plugins can expose their own HTTP routes seamlessly.
- **🔄 Hot Reloading** — Dynamic plugin reloading without server restarts.
- **📊 Built-in Observability** — Structured logging, Prometheus metrics, and OpenTelemetry tracing.
- **🗄️ Multi-Database Support** — Support for PostgreSQL, MySQL, SQLite, MongoDB, and Redis.
- **⏰ Integrated Scheduler** — APScheduler with Redis persistence.
- **🔐 Reinforced Security** — HMAC signatures, granular permissions, and rate limiting.

#### Changes from v1.x

| Feature | v1.x | v2.0 |
|---------|------|------|
| Architecture | Monolithic | Plugin-first |
| Isolation | Basic Process | AST Sandboxing + IPC |
| HTTP Routes | Limited | Full via `get_router()` |
| Plugin Types | Trusted Only | Trusted + Sandboxed |
| Configuration | Python-only | YAML + Environment |
| Database | SQL Only | SQL + NoSQL + Cache |
| EventBus | Basic | Priorities + Hooks |
| Reloading | Manual | Automatic (Watchdog) |

#### Migration from v1.x

See the detailed migration guide in [Migrations](#migration-from-v1x).

---

## Version History

### v2.0.0 (2025-03-21)

**Major New Features**

- Complete architectural shift to plugin-first.
- Introduction of the sandboxing system with process-level isolation.
- Support for Sandboxed plugins via IPC.
- Full FastAPI integration with automatic router mounting.
- ServiceContainer with typed dependency injection.
- EventBus with priorities (HIGH, NORMAL, LOW).
- HookManager for filters and actions.
- PermissionEngine for granular access control.
- Per-plugin RateLimiter with YAML configuration.
- Integrated health checks for all services.
- Redis support as a cache and scheduler backend.
- Comprehensive CLI (`xcore plugin`, `xcore sandbox`, `xcore services`).
- Auto-discovery and automatic plugin loading.

**Breaking Changes**

- The `Plugin` class from v1 is replaced by `TrustedBase`.
- Imports have changed: `from xcore import Xcore, TrustedBase`.
- Configuration file moved from `config.py` to `xcore.yaml`.
- Plugins must now define a `plugin.yaml` manifest.

**Fixes**

- Complete plugin isolation (no module name conflicts).
- Clean lifecycle management (load/reload/unload).
- Memory leaks fixed during reloading.

---

### v1.2.0 (2024-11-15)

**New Features**

- Support for Python 3.12.
- Performance improvements for PluginLoader.
- New CLI commands.

**Fixes**

- Memory leak in plugin reloading.
- Race condition in EventBus.

---

### v1.1.0 (2024-08-20)

**New Features**

- Redis support for distributed cache.
- Logging system improvements.
- MkDocs documentation.

**Fixes**

- Async DB connection issue.
- Timeouts too short for some plugins.

---

### v1.0.0 (2024-06-01)

**First Stable Version**

- Basic plugin system.
- Support for PostgreSQL and SQLite.
- Simple EventBus.
- Python-based configuration.
- Minimal CLI.

---

### v0.9.0-beta (2024-04-10)

**Initial Beta Version**

- Core architecture.
- Dynamic plugin loading.
- Basic FastAPI support.

---

## Roadmap

### v2.1.0 (Planned - Q2 2025)

**Planned Features**

- [ ] Integrated Plugin Marketplace.
- [ ] GraphQL support for plugins.
- [ ] Native WebSocket for real-time communication.
- [ ] Automatic auto-scaling of sandbox workers.
- [ ] Web-based monitoring dashboard.

### v2.2.0 (Planned - Q3 2025)

**Planned Features**

- [ ] gRPC support for inter-service communication.
- [ ] Integrated Circuit Breaker.
- [ ] End-to-end encryption for IPC.
- [ ] Plugin marketplace with automatic verification.

### v3.0.0 (Planned - 2026)

**Long-term Goals**

- WebAssembly support for ultra-isolated plugins.
- Distributed XCore (multi-node cluster).
- Integrated Machine Learning for auto-scaling.

---

## Support Policy

| Version | Status | Supported Until |
|---------|--------|------------------|
| v2.0.x | ✅ Active | March 2026 |
| v1.2.x | 🛟 Maintenance | June 2025 |
| v1.1.x | ❌ End of Life | November 2024 |
| v1.0.x | ❌ End of Life | August 2024 |
| < v1.0 | ❌ End of Life | June 2024 |

**Legend**:

- ✅ **Active** — Receives all fixes and new features.
- 🛟 **Maintenance** — Security fixes only.
- ❌ **End of Life** — No longer supported; update recommended.

---

## Detailed Release Notes

### XCore v2.0.0

#### Kernel Architecture

The XCore v2 kernel is designed around several key components:

```
XCore
├── PluginSupervisor      # Plugin orchestration
├── ServiceContainer      # Service management
├── EventBus             # Event-driven communication
├── HookManager          # Hooks and filters
└── PluginRegistry       # Plugin registry
```

#### Plugin Types

**Trusted Plugins**

- Run in the main process.
- Full access to services.
- Can expose HTTP routes.
- HMAC signature required in strict mode.

**Sandboxed Plugins**

- Run in isolated processes.
- AST restrictions on imports.
- Communication via IPC.
- Resource limits (memory, CPU, time).

#### Integrated Services

| Service | Description | Configuration |
|---------|-------------|---------------|
| Database | SQL and NoSQL | `services.databases` |
| Cache | Memory or Redis | `services.cache` |
| Scheduler | Scheduled tasks | `services.scheduler` |
| Extensions | Custom services | `services.extensions` |

#### Migration from v1.x

**Step 1**: Update imports

```python
# v1.x
from xcore import Plugin

# v2.0
from xcore import TrustedBase
```

**Step 2**: Create `plugin.yaml`

```yaml
# plugin.yaml
name: my_plugin
version: "2.0.0"
execution_mode: trusted
entry_point: src/main.py
```

**Step 3**: Migrate configuration

```yaml
# xcore.yaml (new)
app:
  name: my-app
  env: production

plugins:
  directory: ./plugins

services:
  databases:
    default:
      type: postgresql
      url: "${DATABASE_URL}"
```

**Step 4**: Adapt lifecycle hooks

```python
# v1.x
class Plugin:
    def load(self):
        pass

# v2.0
class Plugin(TrustedBase):
    async def on_load(self):
        pass

    async def on_unload(self):
        pass
```

---

## Specific Version Installation

### Via Poetry

```bash
# Latest version
poetry add xcore

# Specific version
poetry add xcore@2.0.0

# Version constraint
poetry add "xcore@^2.0"
```

### Via pip

```bash
# Latest version
pip install xcore

# Specific version
pip install xcore==2.0.0

# Minimum version
pip install "xcore>=2.0.0"
```

### Via git

```bash
# Latest stable version
git clone https://github.com/traoreera/xcore.git
cd xcore
poetry install

# Specific tag
git checkout v2.0.0
poetry install
```

---

## Reporting Issues

If you encounter issues with a specific version:

1. Check [GitHub issues](https://github.com/traoreera/xcore/issues).
2. Verify if the issue exists in the latest version.
3. Create an issue including:
   - XCore version.
   - Python version.
   - Operating system.
   - Description of the issue.
   - Reproduction code.

---

## Verify Your Version

```python
import xcore

print(xcore.__version__)       # "2.0.0"
print(xcore.__version_info__)  # (2, 0, 0)
```

Via CLI:

```bash
poetry run xcore --version
# xcore v2.0.0
```

---

## Compatibility

### Python

| XCore Version | Python 3.11 | Python 3.12 | Python 3.13 |
|---------------|-------------|-------------|-------------|
| v2.0.x | ✅ | ✅ | ✅ |
| v1.2.x | ✅ | ✅ | ⚠️ |
| v1.1.x | ✅ | ⚠️ | ❌ |
| v1.0.x | ✅ | ❌ | ❌ |

### Major Dependencies

| XCore | FastAPI | SQLAlchemy | Pydantic |
|-------|---------|------------|----------|
| v2.0.x | 0.118+ | 2.0+ | 2.11+ |
| v1.2.x | 0.100+ | 1.4+ | 1.10+ |
| v1.1.x | 0.95+ | 1.4+ | 1.10+ |
| v1.0.x | 0.90+ | 1.3+ | 1.10+ |

---

## Contributing

To contribute to XCore development:

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/amazing`).
3. Commit your changes (`git commit -m 'Add amazing feature'`).
4. Push to the branch (`git push origin feature/amazing`).
5. Open a Pull Request.

See the [contribution guide](development/contributing.md) for more details.

---

*Last updated: March 21, 2025*
