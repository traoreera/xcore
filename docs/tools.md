# Module Documentation: tools/

The `tools/` module provides a collection of utility scripts designed to assist with database management, migrations, and model discovery within the `xcore` framework. These scripts are crucial for maintaining the database schema, performing migrations, and ensuring that the ORM models are correctly integrated.

## Files and Their Roles

*   **`tools/__init__.py`**: (Likely empty or for package initialization). It also imports `cfg` (from `configurations.migrations.Migration`) and `logger` (from `loggers.logger_config`), making these globally accessible within the `tools` module.
*   **`tools/auto_migrate.py`**: A script for automating the discovery of SQLAlchemy models across core and plugin directories and updating the `alembic/env.py` file to include necessary imports for Alembic's autogenerate feature.
*   **`tools/migrate.py`**: The primary command-line interface (CLI) for performing Alembic database migration operations, such as upgrading, downgrading, checking status, generating new migrations, and managing database backups.
*   **`tools/migration_utils.py`**: Provides supplementary database utilities, including schema inspection, schema export to JSON, and a comprehensive backup/restore manager for SQLite databases.
*   **`tools/model_discovery.py`**: A dedicated script focused on discovering SQLAlchemy models within specified directories (core and plugins) and providing a summary of these models, including their class names, table names, and module paths.

## Key Concepts and Functionality

### Automated Model Discovery and `env.py` Updates (`auto_migrate.py`)

The `auto_migrate.py` script simplifies the process of keeping Alembic migration scripts in sync with your application's SQLAlchemy models:

*   **Model Scanning**: It recursively scans predefined core application paths (e.g., `auth/models.py`, `manager/models/`) and plugin directories for Python files that define SQLAlchemy models (by looking for classes inheriting from `Base` or having `__tablename__`).
*   **`alembic/env.py` Modification**: Once models are discovered, the script automatically generates the necessary Python `import` statements for these models. It then inserts these imports into `alembic/env.py` within special markers, ensuring that Alembic's `target_metadata` is aware of all models when generating new migrations (e.g., `alembic revision --autogenerate`).
*   **Configuration**: The paths to scan and exclusion patterns are configured in `config.json` under the `migration` section.

### Comprehensive Migration Management (`migrate.py`)

The `migrate.py` script provides a powerful CLI wrapper around Alembic, offering a unified interface for all migration-related tasks:

*   **`init`**: Initializes the database by creating all tables defined in the SQLAlchemy `Base.metadata`.
*   **`generate "message"`**: Creates a new migration script with a descriptive message. Can be combined with Alembic's `--autogenerate` for automatic schema comparison.
*   **`upgrade [revision]`**: Applies pending migrations up to a specified `revision` (or `head` for all pending migrations).
*   **`downgrade [revision]`**: Reverts migrations down to a specified `revision` (e.g., `-1` for the last one).
*   **`status`**: Displays the current database revision, the latest head revision, and the number of pending migrations.
*   **`current`**: Shows the current revision applied to the database.
*   **`history`**: Lists all migration scripts and their messages.
*   **`backup`**: Creates a physical backup of the database file (currently supports SQLite databases).
*   **Configuration**: Reads Alembic's configuration from `alembic.ini` and database URL from `config.json`.

### Database Utilities (`migration_utils.py`)

This script offers supplementary tools for database inspection and robust backup management:

*   **`DatabaseInspector`**:
    *   `inspect`: Connects to the database and retrieves detailed information about all tables, including columns, indexes, foreign keys, and constraints.
    *   `export`: Exports the full database schema (table structures) to a JSON file, useful for documentation or comparison.
*   **`BackupManager`**:
    *   `create-backup`: Creates a timestamped copy of the database file (primarily for SQLite).
    *   `restore-backup`: Restores the database from a specified backup file.
    *   `list-backup`: Lists all available backup files in the configured backup directory.
    *   `delete-backup`, `delete-all-backup`: Manages the removal of individual or all backup files.
*   **Configuration**: Uses `config.json` for database URL, backup directory, and naming formats.

### Standalone Model Discovery (`model_discovery.py`)

The `model_discovery.py` script provides a focused tool for identifying and summarizing SQLAlchemy models:

*   **Comprehensive Scan**: It scans designated directories (core and plugin paths from `config.json`) for Python files.
*   **Model Analysis**: Analyzes each file to find `class` definitions that are likely SQLAlchemy models.
*   **Detailed Output**: Generates a summary of discovered models, including their Python class names, corresponding database table names, and the module paths where they are defined.
*   **Import Statement Generation**: Can output a list of Python `import` statements for all discovered models, which can be useful for manual `env.py` updates or other integration tasks.

## Integration with Other Modules

*   **`alembic/`**: These scripts directly interact with Alembic's components (`alembic.ini`, `alembic/env.py`, migration versions) to perform database schema management.
*   **`database/`**: `migrate.py` and `migration_utils.py` use `database.Base` and `database.create_engine` to interact with the database.
*   **`configurations/`**: All `tools` scripts heavily rely on configuration settings from `config.json` (specifically the `migration` and `xcore` sections) for database URLs, model discovery paths, and backup strategies.
*   **`makefile`**: Many of these `tools` scripts are integrated into the project's `makefile` (e.g., `make auto_migrate`, `poetry run migrate upgrade`) for convenient execution during development and deployment workflows.
*   **`plugins/`**: The model discovery feature (`auto_migrate.py`, `model_discovery.py`) explicitly scans plugin directories to ensure models defined within plugins are included in the migration process.
