# Installation

## Prerequisites

| Requirement | Version | Notes |
|:------------|:--------|:------|
| Python | 3.11+ | Required |
| Poetry | 2.x | Recommended package manager |
| uv | any | Alternative to Poetry |
| Redis | 7+ | Required only when `cache.backend: redis` or `scheduler.backend: redis` or `xworker` is enabled |
| PostgreSQL | 15+ | Optional — SQLite works without any extra setup |
| MySQL | 8+ | Optional |

---

## From Source

```bash
git clone https://github.com/traoreera/xcore
cd xcore

# With Poetry (recommended)
poetry install --with dev,docs

# With uv
uv sync
```

### Start the development server

```bash
# Via make (recommended)
make dev

# Via Poetry directly
poetry run uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Via uv
uv run uvicorn main:app --reload --port 8000
```

---

## As a Dependency

```bash
# uv
uv add "xcore @ git+https://github.com/traoreera/xcore"

# Poetry
poetry add "xcore @ git+https://github.com/traoreera/xcore"
```

---

## Environment Variables

XCore can override any config key via environment variables using the pattern:

```
XCORE__<SECTION>__<KEY>=value
```

Examples:

```bash
XCORE__APP__DEBUG=true
XCORE__APP__ENV=production
XCORE__SERVICES__CACHE__BACKEND=redis
XCORE__SERVICES__CACHE__URL=redis://localhost:6379/0
XCORE__SERVICES__DATABASES__DB__URL=postgresql+asyncpg://user:pass@host/db
```

To load a `.env` file automatically, set `app.dotenv` in `integration.yaml`:

```yaml
app:
  dotenv: "./.env"
```

---

## Minimal Project Structure

```
my-project/
├── integration.yaml    # Main configuration
├── main.py             # FastAPI entry point
├── plugins/
│   └── hello/
│       ├── plugin.yaml
│       └── src/
│           └── main.py
└── log/
    └── app.log         # Written automatically
```

---

## Verify the Installation

```bash
poetry run xcore --version
# xcore v2.1.3

poetry run xcore plugin list
# Lists all discovered plugins
```

---

## Optional Extras

| Feature | Extra | Install command |
|:--------|:------|:----------------|
| Celery task queue | `celery[redis]` | `poetry add "celery[redis]"` |
| MongoDB | `motor` | `poetry add motor` |
| Redis cache with hiredis | `hiredis` | `poetry add hiredis` |
| OpenTelemetry tracing | `opentelemetry-sdk` | `poetry add opentelemetry-sdk` |

!!! note "Lean core"
    XCore ships with a minimal core. Heavy optional libraries (psutil, markdown, etc.) are only needed if you use the relevant features.
