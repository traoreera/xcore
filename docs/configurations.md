# Module Documentation: configurations/

The `configurations/` module is the central hub for managing and loading the application's settings, primarily from the `config.json` file. It provides a structured, type-hinted approach to access various configuration sections, enabling different parts of the framework to retrieve their specific settings.

## Files and Their Roles

*   **`configurations/__init__.py`**: (Likely empty or for package initialization).
*   **`configurations/base.py`**:
    *   Defines the foundational `Configure` class responsible for loading the entire `config.json` file.
    *   Also defines `BaseCfg`, a generic base class for handling specific sections of the configuration, providing methods for getting, setting, saving, and printing configuration values.
*   **`configurations/core.py`**:
    *   Specializes `BaseCfg` for the "xcore" section of `config.json` (via `Xcorecfg` class).
    *   Defines `TypedDict`s (e.g., `Datatypes`, `RedisConfig`, `Xcore`) to provide type hints for the structure of the "xcore" configuration.
    *   Manages core application settings like global logging, database connection (data), enabled extensions, and general requirements.
*   **`configurations/deps.py`**:
    *   A utility file defining simple `TypedDict`s (e.g., `Logger`) used for type hinting within other configuration files.
*   **`configurations/manager.py`**:
    *   Specializes `BaseCfg` for the "manager" section of `config.json` (via `ManagerCfg` class).
    *   Defines `TypedDict`s (e.g., `PluginsType`, `TaskTypse`, `SnapshotType`, `ManagerType`) to strongly type the manager's configuration structure.
    *   Manages settings related to plugin discovery, task scheduling, logging for the manager, and snapshot exclusions.
*   **`configurations/middleware.py`**:
    *   Currently a sparse file defining `TypedDict`s (e.g., `MidlwareTypes`) potentially intended for middleware-specific configurations like CORS origins. It doesn't contain a `BaseCfg` specialization.
*   **`configurations/migrations.py`**:
    *   Specializes `BaseCfg` for the "migration" section of `config.json` (via `Migration` class).
    *   Defines `TypedDict`s (e.g., `AutoMigrationTypes`, `Backup`, `ExclusionTypes`, `MigrationTypes`) to structure migration-related settings.
    *   Manages database migration settings, including database URL, Alembic configuration, automatic model discovery paths, exclusion patterns, and backup strategies.
*   **`configurations/redis.py`**:
    *   Specializes `BaseCfg` for the "redis" section of `config.json` (via `Rediscfg` class).
    *   Defines `TypedDict` (`Redis`) for type hinting the Redis connection parameters (host, port, db, TTL).
    *   **Note**: There is a potential typo in `Rediscfg`'s `super().__init__(conf, "xcore")` call; it should likely be `super().__init__(conf, "redis")` to correctly load the top-level "redis" section from `config.json`.
*   **`configurations/secure.py`**:
    *   Specializes `BaseCfg` for the "secure" section of `config.json` (via `Secure` class).
    *   Defines `TypedDict`s (e.g., `PasswordType`, `SecureTypes`) for type hinting security-related configurations.
    *   Manages settings for password hashing algorithms and paths to security-specific environment variable files.

## Key Concepts and Functionality

### Centralized Configuration (`config.json`)

All primary application settings are consolidated into a single `config.json` file at the project root. This file is loaded by the `Configure` class and its sections are then managed by specialized `BaseCfg` subclasses.

### Structured Access with `BaseCfg` and Specialized Classes

The `configurations` module enforces a structured way to access and manage settings:
1.  **`Configure`**: Reads the entire `config.json` into memory.
2.  **Specialized `Cfg` classes**: Each top-level section of `config.json` (e.g., `xcore`, `manager`, `migration`, `redis`, `secure`) has a corresponding class (`Xcorecfg`, `ManagerCfg`, `Migration`, `Rediscfg`, `Secure`) that inherits from `BaseCfg`.
3.  **Type Hinting with `TypedDict`**: These specialized classes use `TypedDict` extensively to define the expected structure and types of values within their respective configuration sections, providing strong type checking and IDE assistance.

### Default Values

Each specialized `Cfg` class defines comprehensive default configuration values (e.g., `default_migration`). If a particular setting is not found in `config.json`, the system falls back to these defaults, ensuring the application can run even with a minimal `config.json`.

### Configuration Sections

The `config.json` typically contains the following top-level sections, each managed by a corresponding class in this module:

*   **`xcore`** (managed by `Xcorecfg`): Core application settings, enabled extensions, global logging, and main database connection parameters.
*   **`manager`** (managed by `ManagerCfg`): Settings for the plugin and task management system, including plugin directories, task behaviors, and snapshot rules.
*   **`migration`** (managed by `Migration`): All settings related to database migrations using Alembic, including database URL, auto-discovery, backup strategies, and migration logging.
*   **`redis`** (managed by `Rediscfg`): Connection parameters for the Redis server used for caching and other purposes.
*   **`secure`** (managed by `Secure`): Security-specific settings, primarily for password hashing algorithms and `.env` file locations.

## Integration with Other Modules

*   **`xcore/appcfg.py`**: This file is responsible for initializing the `Xcorecfg` instance (`xcfg`), making the core application configuration available globally.
*   **`cache/cached.py`**: Utilizes `configurations.redis.Rediscfg` to load Redis connection parameters for the caching mechanism.
*   **`main.py`**: The application's entry point implicitly relies on `configurations` through `xcfg`.
*   **Various other modules**: Many modules throughout the `xcore` framework access their specific settings by instantiating the relevant `Cfg` class (e.g., `ManagerCfg` in `manager/`).
