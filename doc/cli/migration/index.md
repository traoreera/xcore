# Database Migrations

`xcorecli` provides a streamlined wrapper around **Alembic** to manage your database schema migrations, with added safety features like automated backups.

!!! info "Async database support"
    `upgrade`/`downgrade`/`revision`/`current`/`stamp` all transparently
    bridge to an async engine first when your `integration.yaml` database
    URL uses an async driver (`sqlite+aiosqlite`, `postgresql+asyncpg`,
    ...) — the normal case for an xcore project. No configuration needed;
    it's detected from the URL itself.

## Getting Started

Migrations are managed via the `migration` command group.

### Initialize Migrations

If you are setting up a new project:

```bash
xcli migration init
```

This creates the `alembic/` directory, configuration files, and scans for initial models.

## Safety & Backups

Before performing dangerous operations, `xcorecli` can automatically backup your database.

### Create a Backup

Manually trigger a timestamped backup. Supports SQLite, PostgreSQL, MySQL, and MariaDB.

```bash
xcli migration backup
```

### Restore from Backup

Restore your database to a previous state. If no path is provided, it picks the latest backup.

```bash
xcli migration restore
```

### Manage Backups

List all available backups and their sizes.

```bash
xcli migration backups
```

!!! info "Backup Storage"
    Backups are stored in the directory specified in `integration.yaml` under `migration.backup_dir` (defaults to `./backups`).

## Common Workflows

### Scan for Models

Preview all discovered SQLAlchemy models across your project and plugins before generating a migration.

```bash
xcli migration scan
```

!!! note "Scan Paths"
    `xcorecli` supports multiple scan paths in `integration.yaml`. By default, it scans your main app and all installed plugins.

### Create a New Migration

Generate a new migration script based on changes to your models.

```bash title="Generate Migration"
xcli migration revision -m "add user table"
```

### Apply Migrations

Upgrade your database to the latest schema version.

```bash title="Upgrade with Backup"
xcli migration upgrade head --backup
```

### Rollback

Revert the last migration.

```bash title="Downgrade"
xcli migration downgrade -1
```

## Migration Status

Check which migrations have been applied.

```bash
xcli migration history
```

See the database's current revision, or where the migration chain's
unapplied heads are:

```bash
xcli migration current   # what revision the DB is actually stamped at
xcli migration heads     # latest revision(s) defined in the migration scripts
```

!!! tip "Stamping"
    Use `xcli migration stamp <id>` to mark the database at a specific revision without running the actual migration scripts.
