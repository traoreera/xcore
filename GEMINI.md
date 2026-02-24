# GEMINI.md - XCore Framework Context

This file provides a comprehensive overview of the XCore Framework to guide AI interactions within this repository.

## 🚀 Project Overview
XCore is a modular orchestration framework based on **FastAPI**, designed to manage, isolate, and orchestrate plugins in a secure environment. It allows for highly extensible applications where features are decoupled as independent plugins.

### Key Architectural Pillars
- **Dynamic Plugin System**: Hot-loading/unloading and real-time reloading of plugins.
- **Multi-Mode Execution**:
    - `TRUSTED`: High-performance, verified via signatures, direct execution.
    - `SANDBOXED`: Isolated execution with resource limits and supervisor control.
    - `LEGACY`: Compatibility mode.
- **Service Integration Layer**: Unified access to SQL (PostgreSQL, MySQL, SQLite), NoSQL (Redis), and Scheduling (APScheduler).
- **Event-Driven Architecture**: Powerful `HookManager` for inter-plugin communication and reacting to system events (e.g., `xcore.startup`, `xcore.shutdown`).
- **Security First**: AST scanning of plugin source code, signature verification, and rate limiting.

## 🛠️ Technical Stack
- **Core**: Python 3.11+, FastAPI, Pydantic v2.
- **Database**: SQLAlchemy (Async), Alembic (Migrations).
- **Services**: Redis (Caching/NoSQL), APScheduler (Tasks).
- **Environment**: Poetry (Dependency management), Docker/Docker-Compose.
- **Quality**: Pytest (Testing), Black/Isort/Flake8 (Linting), Bandit (Security Audit).
- **Documentation**: Sphinx, internal `docgen` tool.

## 📂 Directory Structure Highlights
- `xcore/`: Core framework logic.
    - `sandbox/`: Plugin management, isolation, and supervisors.
    - `integration/`: Service adapters and registry.
    - `hooks/`: Event system implementation.
- `plugins/`: Default directory for dynamic plugins. Each plugin requires a `plugin.yaml` manifest.
- `docs/`: Comprehensive technical documentation.
- `backgroundtask/`: Symlinked tasks for execution.
- `tools/`: CLI utilities for migrations and discovery.

## 📜 Development Workflows & Commands

### Initial Setup
```bash
make init  # Chmod scripts, install deps, and start dev server
```

### Running the Application
- **Development**: `make run-dev` (Runs on port 8000 with --reload)
- **Production**: `make run-st` (Static mode, no reload)

### Plugin Management
- **Add Plugin**: `make add-plugin PLUGIN_NAME=name AUTHOR=user`
- **Remove Plugin**: `make rm-plugin PLUGIN_NAME=name`

### Quality & Maintenance
- **Testing**: `make test`
- **Lint & Format**: `make lint-fix` (Applies Black, Isort, Autopep8)
- **Security Audit**: `make auto-security`
- **Clean Cache**: `make clean`

### Monitoring & Logs
XCore features an extensive logging system accessible via Makefile:
- `make logs-health-check`: Full system health diagnosis.
- `make logs-live`: Real-time log streaming.
- `make logs-stats`: Error/Warning statistics.
- `make logs-security-audit`: Authentication and security-related logs.

## 📝 Coding Conventions
1. **Type Hinting**: All new code should be fully typed using Python's `typing` module or native types.
2. **Plugin Development**: Plugins must inherit from `TrustedBase` (if trusted) and provide a `plugin.yaml` manifest.
3. **Service Access**: Services should be accessed via `self._services` within plugins, injected by the `PluginManager`.
4. **Asynchronous First**: Prioritize `async/await` for all I/O bound operations (DB, Network, Hooks).
5. **Testing**: Add unit tests in `test/` or within the plugin's directory for every new feature or bug fix.

## ⚠️ Safety & Security
- Never commit `.env` files or hardcoded credentials.
- Plugins in `TRUSTED` mode require a `.sig` signature file when `strict_trusted=True`.
- Use the `ASTScanner` logic to verify that third-party plugins do not use forbidden imports.
