# tools - Utility Scripts Module

## Overview

The `tools` module provides CLI utilities for database migrations, model discovery, and other maintenance tasks.

## Module Structure

```
tools/
├── __init__.py              # Module exports
├── migrate.py               # Database migration runner
├── model_discovery.py       # Auto-discovery of SQLAlchemy models
├── auto_migrate.py          # Automated migration
└── migration_utils.py       # Migration utilities
```

## Core Components

### Migration Runner (`migrate.py`)

Main entry point for running database migrations.

```python
# migrate.py

def run_migrations(alembic_cfg_path: str = "alembic.ini"):
    """
    Run pending database migrations.

    Args:
        alembic_cfg_path: Path to alembic configuration file
    """

def create_migration(
    message: str,
    autogenerate: bool = True,
    alembic_cfg_path: str = "alembic.ini"
):
    """
    Create a new migration script.

    Args:
        message: Migration description
        autogenerate: Auto-generate from model changes
        alembic_cfg_path: Path to alembic configuration
    """

def rollback_migrations(steps: int = 1):
    """
    Rollback migrations.

    Args:
        steps: Number of migrations to rollback
    """

def show_migration_status():
    """Display current migration status."""
```

### Model Discovery (`model_discovery.py`)

Automatically discovers SQLAlchemy models from the codebase.

```python
# model_discovery.py

def discover_models(
    package_path: str = None,
    base_class = None
) -> List[Type]:
    """
    Auto-discover SQLAlchemy models.

    Args:
        package_path: Path to search for models (default: project root)
        base_class: Base model class (default: database.db.Base)

    Returns:
        List of discovered model classes

    Usage:
        models = discover_models("plugins/my_plugin/models")
        for model in models:
            print(f"Found model: {model.__name__}")
    """

def get_model_table_names(models: List[Type]) -> List[str]:
    """Get table names from model classes."""

def import_models_module(module_path: str) -> Optional[ModuleType]:
    """Import a module and return its models."""
```

### Automated Migration (`auto_migrate.py`)

Handles automatic migration on application startup.

```python
# auto_migrate.py

class AutoMigration:
    """
    Handles automatic database migrations.

    Features:
    - Backup before migration
    - Auto-create migrations from model changes
    - Safe rollback on failure
    """

    def __init__(self, config: MigrationsConfig):
        self.config = config

    async def run(self) -> MigrationResult:
        """
        Run automatic migration process.

        Returns:
            MigrationResult with status and details
        """

    def backup_database(self) -> str:
        """
        Create database backup before migration.

        Returns:
            Path to backup file
        """

    def should_migrate(self) -> bool:
        """Check if migration is needed."""
```

### Migration Utilities (`migration_utils.py`)

Helper functions for migrations.

```python
# migration_utils.py

def get_current_revision(alembic_cfg: Config) -> Optional[str]:
    """Get current database revision."""

def get_latest_revision(alembic_cfg: Config) -> Optional[str]:
    """Get latest available revision."""

def revisions_are_equal(rev1: str, rev2: str) -> bool:
    """Compare two revision strings."""

def get_revision_history(alembic_cfg: Config) -> List[Revision]:
    """Get list of all revisions."""

def validate_models(models: List[Type]) -> List[str]:
    """
    Validate model definitions.

    Returns:
        List of validation errors (empty if valid)
    """

def generate_migration_diff(
    current_models: List[Type],
    target_models: List[Type]
) -> MigrationDiff:
    """Generate diff between model states."""
```

## CLI Usage

### Running Migrations

```bash
# Run all pending migrations
python -m tools.migrate upgrade

# Run specific migration
python -m tools.migrate upgrade +1

# Downgrade
python -m tools.migrate downgrade -1

# Show current version
python -m tools.migrate current

# Show history
python -m tools.migrate history
```

### Creating Migrations

```bash
# Create auto-generated migration
python -m tools.migrate revision --autogenerate -m "Add user table"

# Create empty migration
python -m tools.migrate revision -m "Manual data migration"

# Create migration with specific dependencies
python -m tools.migrate revision --autogenerate -m "Add posts" --head head
```

### Model Discovery

```bash
# Discover all models
python -m tools.model_discovery

# Discover models in specific package
python -m tools.model_discovery --package plugins/my_plugin

# List discovered models
python -m tools.model_discovery --list

# Verify models
python -m tools.model_discovery --verify
```

### Auto Migration

```bash
# Run auto-migration (from config)
python -m tools.auto_migrate

# Run with backup
python -m tools.auto_migrate --backup

# Dry run (show what would be done)
python -m tools.auto_migrate --dry-run

# Skip confirmation
python -m tools.auto_migrate --yes
```

## Usage Examples

### Programmatic Migration

```python
from tools.migrate import run_migrations, create_migration

# Run migrations on startup
async def startup_event():
    result = run_migrations()
    if result.success:
        print(f"Applied {result.applied_count} migrations")
    else:
        print(f"Migration failed: {result.error}")

# Create migration programmatically
def add_new_feature():
    migration = create_migration(
        message="Add notification system",
        autogenerate=True
    )
    print(f"Created migration: {migration.revision}")
```

### Custom Model Discovery

```python
from tools.model_discovery import discover_models
from database.db import Base

# Discover models in plugins
def load_plugin_models(plugin_path: str):
    models = discover_models(
        package_path=plugin_path,
        base_class=Base
    )

    for model in models:
        print(f"Found model: {model.__name__}")
        # Register model for migrations
        register_model(model)

# Use discovered models
models = discover_models("plugins/LibraryHub/models")
table_names = [model.__tablename__ for model in models]
```

### Auto Migration in Application

```python
from tools.auto_migrate import AutoMigration
from configurations import Xcorecfg

config = Xcorecfg.from_file("config.json")

async def initialize_database():
    if config.migrations.auto_migrate:
        auto_migrate = AutoMigration(config.migrations)
        result = await auto_migrate.run()

        if not result.success:
            # Handle migration failure
            if result.backup_path:
                print(f"Restored from backup: {result.backup_path}")
            raise MigrationError(result.error)

        print(f"Database is up to date: {result.current_revision}")
```

### Migration in Plugin Context

```python
# In plugin install hook
from tools.migrate import create_migration, run_migrations
from tools.model_discovery import discover_models

class MyPlugin:
    def on_install(self):
        # Discover plugin models
        models = discover_models("plugins/my_plugin/models")

        # Create migration for plugin tables
        migration = create_migration(
            message=f"Install {self.name} plugin tables",
            autogenerate=True
        )

        # Run the migration
        run_migrations()
```

## Configuration

Configuration in `config.json`:

```json
{
  "migrations": {
    "auto_migrate": false,
    "auto_discovery": true,
    "models_package": "models",
    "script_location": "alembic",
    "backup_policy": {
      "enabled": true,
      "before_migrate": true,
      "keep_count": 5,
      "location": "backups"
    }
  }
}
```

### Alembic Configuration (`alembic.ini`)

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os

[post_write_hooks]
hooks = ruff
ruff.type = exec
ruff.executable = %(here)s/.venv/bin/ruff
ruff.options = --fix REVISION_SCRIPT_FILENAME

[loggers]
keys = root,sqlalchemy,alembic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handlers]
keys = console

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatters]
keys = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

## Best Practices

### 1. Always Backup Before Migration

```python
from tools.auto_migrate import AutoMigration

async def safe_migrate():
    migrator = AutoMigration(config)

    # Create backup
    backup_path = migrator.backup_database()
    print(f"Backup created: {backup_path}")

    try:
        result = await migrator.run()
        if not result.success:
            # Restore from backup
            restore_database(backup_path)
    except Exception:
        restore_database(backup_path)
        raise
```

### 2. Test Migrations

```python
# Test migration in isolated environment
@pytest.fixture
def test_migration():
    # Create test database
    test_db = create_test_database()

    # Run migrations
    run_migrations()

    # Verify schema
    assert table_exists("users")
    assert table_exists("posts")

    yield test_db

    # Cleanup
    drop_test_database(test_db)
```

### 3. Version Control Migrations

```bash
# Always commit migrations
git add alembic/versions/
git commit -m "Add migration for user table"

# Never delete old migrations
git log --oneline alembic/versions/
```

### 4. Document Complex Migrations

```python
# In migration file
"""
Revision ID: abc123
Revises: prev456
Create Date: 2024-01-15 10:30:00

Changes:
- Add 'status' column to users table
- Migrate existing data to 'active' status
- Create index on status column

Note: This migration may take time on large databases.
"""
```

## Troubleshooting

### Common Issues

1. **"Can't locate revision"**
   ```bash
   # Check current version
   python -m tools.migrate current

   # Stamp to specific version
   python -m tools.migrate stamp <revision>
   ```

2. **"Table already exists"**
   ```bash
   # Mark as applied without running
   python -m tools.migrate stamp head
   ```

3. **Migration conflicts**
   ```bash
   # Merge branches
   python -m tools.migrate merge -m "Merge branches"
   ```

4. **Auto-generation not detecting changes**
   - Ensure models import `Base` from `database.db`
   - Check model is in discoverable path
   - Verify `target_metadata` in `alembic/env.py`

## Dependencies

- `alembic` - Database migrations
- `sqlalchemy` - Database ORM
- `configurations` - Migration configuration
- `database` - Database connection

## Related Documentation

- [database.md](database.md) - Database module
- [configurations.md](configurations.md) - Migration configuration
- [alembic/README.md](../alembic/README.md) - Alembic documentation
