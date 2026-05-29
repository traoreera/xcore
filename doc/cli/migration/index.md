---
title: Database Migrations
description: Manage database schema migrations using the Alembic wrapper with automated backups.
icon: material/database-refresh
---

# Database Migrations

`xcorecli` provides a streamlined wrapper around **Alembic** to manage your database schema migrations, with added safety features like automated backups.

## Getting Started

Migrations are managed via the `migration` command group.

### Initialize Migrations

Set up Alembic for a new project:

```bash
xcli migration init
# Creating alembic/ directory...
# Scanning for models...
#   Found: plugins/auth_plugin/models.py — User, Role
#   Found: plugins/billing_engine/models.py — Invoice, Subscription
# alembic.ini written
# env.py written (multi-model aware)
# Migrations initialized.
```

### Scan for Models

Preview all discovered SQLAlchemy models before generating a migration:

```bash
xcli migration scan

# Discovered Models
# ─────────────────────────────────────────
#  Model           Module               Table
#  User            auth_plugin.models   users
#  Role            auth_plugin.models   roles
#  Invoice         billing.models       invoices
#  Subscription    billing.models       subscriptions
```

!!! note "Scan Paths"
    Xcore automatically scans your main app and all installed plugins. Configure additional paths:
    ```yaml title="integration.yaml"
    migration:
      scan_paths:
        - "myapp/models"
        - "plugins/*/models.py"
    ```

## Common Workflows

### Create a Migration

Generate a new migration script based on model changes:

```bash title="Generate Migration"
xcli migration revision -m "add subscription table"
# Generating migrations/versions/2026_05_27_1234_add_subscription_table.py
# Done.
```

### Apply Migrations

Upgrade the database to the latest schema version:

```bash title="Upgrade (with automatic backup)"
xcli migration upgrade head --backup
# Creating backup: backups/2026-05-27T14-32-00.sql.gz
# Running migrations:
#   2026_05_27_1234_add_subscription_table ... OK
# Database at revision: 2026_05_27_1234
```

### Rollback

Revert the last applied migration:

```bash title="Downgrade by 1"
xcli migration downgrade -1
# Reverting: 2026_05_27_1234_add_subscription_table
# Done.
```

### Migration History

Check which migrations have been applied:

```bash
xcli migration history

# Revision               Applied At           Description
# ─────────────────────────────────────────────────────────
# 2026_05_27_1234   2026-05-27 14:32:00  add subscription table
# 2026_05_14_5678   2026-05-14 09:15:12  add user roles
# 2026_04_15_9012   2026-04-15 11:00:00  initial schema
```

## Safety & Backups

Before dangerous operations, `xcorecli` can automatically back up your database.

### Create a Backup

Manually trigger a timestamped backup (supports SQLite, PostgreSQL, MySQL, MariaDB):

```bash
xcli migration backup
# Backup created: backups/2026-05-27T14-32-00.sql.gz (2.3 MB)
```

### Restore from Backup

Restore to a previous state. Omit the path to use the latest backup:

```bash title="Restore latest"
xcli migration restore

# Or specify a specific backup file:
xcli migration restore backups/2026-05-14T09-15-12.sql.gz
```

### List Backups

```bash
xcli migration backups

# Available Backups
# ─────────────────────────────────────────
#  File                              Size    Date
#  2026-05-27T14-32-00.sql.gz       2.3 MB  2026-05-27
#  2026-05-14T09-15-12.sql.gz       2.1 MB  2026-05-14
#  2026-04-15T11-00-00.sql.gz       1.8 MB  2026-04-15
```

!!! info "Backup Storage"
    Backups are stored in `./backups` by default. Configure the path:
    ```yaml title="integration.yaml"
    migration:
      backup_dir: "/var/lib/xcore/backups"
    ```

!!! tip "Stamping"
    Use `xcli migration stamp <id>` to mark the database at a specific revision without running migration scripts — useful when adopting Xcore on an existing database.
