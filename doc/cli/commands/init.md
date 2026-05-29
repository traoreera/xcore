---
title: Project Initialization
description: Scaffold a new Xcore project or upgrade an existing configuration.
icon: material/plus-box
---

# Project Initialization

`xcorecli` simplifies the lifecycle of an `xcore` project from scaffolding to upgrades.

## New Project Scaffolding

Use the `init` command to scaffold a new project. The wizard guides you through setup with sensible defaults.

```bash title="Interactive Init"
xcli init my-project
```

To skip the wizard and choose a database backend directly:

```bash title="Non-interactive with PostgreSQL"
xcli init my-project --db postgresql --env production
```

### Database Options

The initialization wizard supports several database backends with pre-configured URL templates:

| Backend | Default URL |
|---------|-------------|
| SQLite (default) | `sqlite+aiosqlite:///./data/xcore.db` |
| PostgreSQL | `postgresql+asyncpg://user:pass@localhost:5432/db` |
| MySQL | `mysql+aiomysql://user:pass@localhost:3306/db` |
| MariaDB | `mysql+aiomysql://user:pass@localhost:3306/db` |

### Generated Structure

`xcli init` generates a complete, production-ready project structure:

```text
my-project/
├── integration.yaml     # Central configuration file
├── main.py              # FastAPI entry point with Xcore lifespan
├── .env                 # Environment variables (gitignored)
├── requirements.txt     # Project dependencies
├── plugins/             # Plugin directory
└── log/                 # Application logs
```

The generated `main.py` looks like this:

```python title="main.py" linenums="1"
from contextlib import asynccontextmanager
from fastapi import FastAPI
from xcore import Xcore

xcore = Xcore("integration.yaml")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await xcore.boot(app)
    yield
    await xcore.shutdown()

app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def health():
    return await xcore.health()
```

!!! info "Built-in Health Check"
    The generated `main.py` includes a `/health` endpoint by default, allowing orchestrators like Kubernetes to monitor service status.

## Upgrade Workflows

As the `xcore` ecosystem evolves, your project may need updates to its core configuration or database schema.

### Upgrading Configuration

The `upgrade` command checks your current `integration.yaml` against the latest schema and applies migrations or additions automatically.

```bash
xcli upgrade

# Output example:
# Checking integration.yaml against schema v2.3.0...
# [OK] app section
# [ADD] tenancy.enforce_ipc = true (new in v2.3.0)
# [ADD] services.databases.default.pool_pre_ping = true (new in v2.2.0)
# Configuration upgraded successfully.
```

## Example Workflow

```bash
# 1. Scaffold
xcli init my-project --db postgresql

# 2. Enter the directory and configure .env
cd my-project
echo 'XCORE_SECRET_KEY=your-secret' >> .env
echo 'DB_URL=postgresql+asyncpg://user:pass@localhost/mydb' >> .env

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the development server
xcli manager start --reload

# 5. Verify
curl http://localhost:8000/health
# {"status": "ok", "services": {"db": "healthy", "cache": "healthy"}}
```

## See Also

[Configuration Guide](../getting-started/configuration.md)
:   Full reference for `integration.yaml`.

[Health Check](health.md)
:   Validate your environment after setup.
