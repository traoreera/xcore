# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.3.4] - 2026-08-04

### Fixed
- **warm_pool.py**: Replaced `logging.getLogger()` with `get_logger()` from `xcore.kernel.observability` to comply with project logging conventions. Converted all 11 logger calls from `%s` stdlib style to structured kwargs logging.

### Documentation
- **ROADMAP_PROGRESS.md**: Updated V2 progress from 70% to 85% — Ephemeral mode and Warm Pool were already implemented but marked as not done. Corrected status for Hot Cache (now ⚠️). Added "Points d'Attention" section noting duplicate `kernel/middlewares/` directory.

## [2.3.3] - 2026-06-08

### Added
- **Mode Éphémère (Ephemeral Mode)**: Introduced a new execution mode for plugins that optimizes RAM usage on the host machine during hot reloads. This enables fully stateless plugins and reduces resource footprints.
- **Plugin Warm Pool**: Implemented a warm pool mechanism to accelerate plugin activation and lifecycle transitions.

### Changed
- **Event Bus Performance**: Optimized the `EventBus` for single-handler dispatch, reducing overhead for simple event flows.
- **Hot Reloading**: Optimized the hot reloading process to be more memory-efficient by leveraging ephemeral handlers.
- **Runtime Supervisor**: Updated the supervisor to manage ephemeral plugin instances and warm pools efficiently.
- **Internalization**: Updated RBAC error messages to English for better consistency.

### Fixed
- **Resource Management**: Addressed potential memory leaks during repeated hot reloads by implementing strict ephemeral lifecycle management.

## [2.3.2] - 2026-06-05

### Added
- **Python 3.12 Support**: Upgraded codebase and CI pipelines to support Python 3.12.
- **C++ Security Scanner**: Integrated high-performance `scanner_core` C++ extension for deeper security analysis.
- **Event Bus Singleton**: Implemented a global `EventBus` singleton available at configuration time, injected directly into middleware parameters.
- **Enhanced CI/CD**: Added comprehensive test coverage reporting and PR size validation to GitHub Actions.
- **CORS Configuration**: Centralized CORS configuration in `integration.yaml`.

### Changed
- **Modularization**: Decoupled core runtime from SDK and CLI.
    - `xcoreCli` is now an external dependency (`git+https://github.com/xcore-team/xcoreCli.git`).
    - `xcoresdk` is now an external dependency (`git+https://github.com/xcore-team/xcoreSDK.git`).
- **Internal Refactoring**:
    - Complete overhaul of the middleware pipeline for better performance and extensibility.
    - Improved database container connection handling with explicit session verification.
- **Documentation**: Migrated documentation system to MkDocs for better maintainability and rich search capabilities.

### Fixed
- **Plugin Sandbox**: Fixed a bug where environment variables were not correctly injected into the plugin context if missing from the manifest.
- **Database Reliability**: Resolved an issue where database connections could fail due to unverified sessions; added automatic verification before usage.
- **Plugin CLI**: Fixed various bugs in plugin-related CLI commands.

## [2.3.1] - 2026-05-29

### Fixed

- **database/session**: Connections were failing silently because the session was not verified before use. Added an explicit check on the session state (`is_active`) before each operation, with automatic reconnection if the session is expired or closed.
- **database/async_sql**: `pool_pre_ping=True` raised `ping() missing 1 required positional argument: 'reconnect'` when using the `aiomysql` driver. Pre-ping is now disabled automatically for `aiomysql` and `cymysql`, and is compensated by a pessimistic event listener (`engine_connect`) and `pool_recycle`.
- **database/async_sql**: Improved handling of dead connections — `OperationalError` and `DisconnectionError` errors during rollback are now caught and logged instead of crashing the worker.
- **database/_utils**: The `read_timeout` and `write_timeout` parameters are exclusive to `pymysql`. `sanitize_connect_args()` now filters them out for `aiomysql` with an explicit warning, avoiding a silent connection error.
- **database/migrations**: `MigrationRunner._is_async()` did not recognize the `+aiomysql` and `+asyncmy` suffixes, forcing the synchronous path on async connections. Both drivers are now included in `async_markers`.
- **database/container**: The `DatabaseConfig` configuration did not expose certain production parameters (`pool_timeout`, `pool_reset_on_return`, `connect_args`, `isolation_level`, `execution_options`). These fields are now read from `integration.yaml` and passed to the adapters.

### Improved

- **CI/CD**: Updated `ci.yml` workflow — refined the coverage step, reviewed PR labels, and added the `pr.yml` workflow to validate PR titles (conventional commits) and PR sizes.
- **CI/CD**: `security.yml` workflow — restricted Bandit scans to existing folders (`xcore/`, `tests/`) to eliminate false positives on `extensions/` and `plugins/`.
- **Tests**: Fixed `test_tenancy.py` test — aligned assertion with actual `ContextVar` behavior after reset.
- **Documentation**: Complete overhaul of the CLI section (`doc/cli/`) with detailed guides for installation, configuration, and the `worker`, `plugin`, `sandbox`, `manager`, and `migration` commands. Added the SDK API reference (`doc/sdk/api/`).
- **Observability**: Enriched `XcoreLogger` with structural support for contextual fields; extended `MetricsCollector` with documented `memory` and `prometheus` backends.

## [2.3.0] - 2026-05-14

### Added
- **Multi-tenancy Native (Axe 1)**:
    - `TenantMiddleware`: Extracts `tenant_id` from HTTP header (`X-Tenant-ID`) or subdomain; injects `request.state.tenant_id`.
    - `TenantAwareCache`: Wraps cache and automatically prefixes all keys with `{tenant_id}:`.
    - `TenantAwareDB`: Wraps SQL adapters and executes `SET search_path TO {tenant_id}, public` (PostgreSQL) before each query.
    - `TenantAwareScheduler`: Prefixes APScheduler `job_id` with `{tenant_id}:`.
    - `wrap_services_for_tenant()`: Replaces services in plugin context at each call; zero code changes for existing plugins.
- **IPC Authorization (allowed_callers)**:
    - `IPCAuthMiddleware`: First middleware in the pipeline; checks `allowed_callers` declared in `plugin.yaml`.
    - **Deny-by-default**: IPC calls are denied if the list is empty or missing. Direct HTTP calls (caller=None) still pass.
    - `PluginLoader.get_manifest(name)`: Added method to retrieve manifest from middleware.
- **@schema Decorator (Axe 3)**:
    - Versioned decorator with built-in validation (Pydantic).
    - `SchemaRegistry`: Singleton storing all schemas declared via `@schema`.
    - `BreakingChangeDetector`: Detects breaking changes between two registry versions.
    - CLI: `xcore plugin validate --check-breaking schemas_v1.json`.
- **Configuration**:
    - `tenancy:` section in `integration.yaml` with 8 flags: `enabled`, `header`, `subdomain`, `default_tenant`, `isolate_cache`, `isolate_db`, `isolate_scheduler`, `enforce_ipc`.
    - `TenancyConfig` dataclass in `configurations/sections.py`.
    - `allowed_callers: list[str]` added to `PluginManifest`.
- **Testing**:
    - 58 new tests: `tests/unit/kernel/test_tenancy.py` (41) and `tests/integration/test_tenancy_integration.py` (17).
- **Documentation**:
    - `doc/guides/tenancy.md`: Complete multi-tenant guide.
    - `doc/guides/plugin-manifest.md`: `plugin.yaml` reference.
    - `doc/reference/configuration.md`: Documented `tenancy:` section.
    - `doc/reference/sdk.md`: Documented `@schema`.
    - `doc/guides/security.md`: IPC and `allowed_callers` section.
    - `doc/architecture/decisions.md`: Decisions 7 (location), 8 (IPC deny-by-default), 9 (@schema source of truth).

## [2.2.1] - 2026-05-24

### Fixed
- **database/async_sql**: `pool_pre_ping=True` caused `ping() missing 1 required positional argument: 'reconnect'` with aiomysql. Pre-ping is now disabled automatically for aiomysql/cymysql and compensated by a pessimistic event listener + `pool_recycle`.
- **database/migrations**: `MigrationRunner._is_async()` did not recognize `+aiomysql` and `+asyncmy` drivers, forcing synchronous path on async connections.
- **database/_utils**: `read_timeout` and `write_timeout` are pymysql-only parameters. `sanitize_connect_args` now filters them for aiomysql with an explicit warning.

## [2.2.0] - 2026-05-24

### Added
- **DatabaseConfig**: New configurable pool parameters in `xcore.yaml`: `pool_pre_ping`, `pool_recycle`, `pool_timeout`, `pool_reset_on_return`, `connect_args`, `isolation_level`, `execution_options`.
- **database/adapters/_utils.py**: New module for driver detection and connection argument sanitization.

### Fixed
- **database/async_sql**: Fixed stale connections (MySQL/MariaDB) after `wait_timeout`.
- **database/async_sql**: Added missing `@asynccontextmanager` on `session()`.
- **database/async_sql + sql**: Added missing `disconnect()`.
- **database/async_sql + sql**: Improved error handling during rollback on dead connections.

## [2.2.0] - 2026-05-14

### Changed
- **Security**: Removed `python-jose` and `python-ecdsa` to eliminate vulnerability to Minerva timing attacks (CVE-2024-23342).
- **Cleanup**: Removed 7 unused dependencies (`pillow`, `watchdog`, `user-agents`, `aiocache`, `toml`, `mysql-connector-python`).
- **Optimization**: Moved `psutil` to dev dependencies and `markdown` to docs dependencies.

## [2.1.3] - 2026-05-13

### Added
- **XWorker (Native Celery)**: Full Celery integration in `ServiceContainer`.
- **CLI xcore worker**: Command to manage FastAPI and Celery processes (`start`, `stop`, `status`, `logs`, etc.).
- **Extended Configuration**: FastAPI constructor parameters and uvicorn parameters configurable via YAML.
- **Declarative Middleware System**: Automatic loading from `integration.yaml`.

## [2.1.2] - 2026-04-29

### Fixed
- 13 critical test failures resolved (kernel, permissions, sandbox).
- AST Scanner: detection of bypasses via import aliases.

### Improved
- **Performance**:
    - LRU Cache on `PermissionEngine`: +34% throughput.
    - Native `mset`/`mget` on Redis: up to 77x faster on batch operations.
    - Pre-compiled regex in `Policy.matches()`: short-circuit in 0.4 µs.
- **Quality**:
    - `pytest-benchmark` integration.
    - Pre-commit hooks for black, isort, and flake8.
    - `pyproject.toml` migrated to PEP 621.

## [2.0.0] - 2026-04-15

### Added
- **Plugin-First Architecture**: Modular kernel, separation of Kernel / Services / Plugins.
- **Advanced Sandboxing**: OS subprocess isolation, JSON-RPC 2.0 communication.
- **ServiceContainer**: Dependency injection for DB (SQLAlchemy 2.0), Cache (Redis/Memory), Scheduler (APScheduler).
- **MiddlewarePipeline**: Pre-compiled pipeline (Tracing → RateLimit → Permissions → Retry).
- **SDK**: `@action`, `@router`, `@validate_payload`, `AutoDispatchMixin`, `RoutedPlugin`.
- **RBAC**: Pluggable `AuthBackend` + declarative `RBACChecker`.
- **StateMachine**: FSM per plugin with validated transitions.
- **PluginRegistry**: Metadata, dependencies, semver versioning.

## [1.x] - Legacy

### Added
- Initial stable release based on FastAPI.
- Monolithic plugin system without isolation.
- Limited support for asynchronous services.
