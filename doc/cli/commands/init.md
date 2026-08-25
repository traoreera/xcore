# Project Initialization

`xcorecli` simplifies the lifecycle of an `xcore` project from scaffolding to upgrades.

## New Project Scaffolding

To start a new project, use the `init` command. The improved wizard will guide you through the setup, providing sensible defaults for various database engines.

```bash title="Interactive Init"
xcli init my-project
```

### Database Options

The initialization wizard supports several database backends with
pre-configured URL templates — always the **async** driver variant, never
a sync one, since `xcore` is async end-to-end:

- **SQLite** (default): `sqlite+aiosqlite:///./xcore.db`
- **PostgreSQL**: `postgresql+asyncpg://user:pass@localhost:5432/dbname`
- **MySQL**: `mysql+aiomysql://user:pass@localhost:3306/dbname`
- **MariaDB**: `mysql+aiomysql://user:pass@localhost:3306/dbname`

`--db-url` overrides the template entirely if you need a different
host/user/password — but keep the `+aiosqlite`/`+asyncpg`/`+aiomysql`
driver suffix; a plain `postgresql://`/`mysql://` URL uses a sync driver
that doesn't work with this framework's async SQLAlchemy engine.

### Generated Structure

`xcli init` generates a complete, production-ready project structure:

- `integration.yaml`: Central configuration file.
- `main.py`: Application entry point with a built-in health check endpoint and plugin loading logic.
- `.env`: Environment variables for sensitive configuration (DB passwords, API keys).
- `requirements.txt`: Project dependencies.
- `plugins/`: Directory for your custom extensions.
- `log/`: Directory for application logs.

!!! info "Built-in Health Check"
    The generated `main.py` includes a `/health` endpoint by default, allowing you to monitor the status of all connected services (DB, Cache, etc.) via HTTP.

## Upgrade Workflows

As the `xcore` ecosystem evolves, your project may need updates to its core configuration or database schema.

### Upgrading Configuration

The `upgrade` command checks your current `integration.yaml` against the latest schema and suggests migrations or additions.

```bash
xcli upgrade
```

!!! tip "Automation"
    Running `make init` (if using the provided Makefile) is the recommended way to handle both installation and initial configuration in one go.

## Example Workflow

1. **Scaffold**: `xcli init my-project --db postgresql`
2. **Install**: `pip install -r requirements.txt`
3. **Run**: `xcli manager start --reload`
4. **Verify**: Open `http://localhost:8000/health`
