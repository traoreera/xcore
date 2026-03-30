# Installation

This guide walks you through installing XCore and setting up your development environment.

## Prerequisites

Before installing XCore, ensure you have:

- **Python 3.11** or higher
- **Poetry** 1.7+ (dependency management)
- **Git** (for cloning the repository)

### Verify Python Version

```bash
python --version
# Should output: Python 3.11.x or higher
```

### Install Poetry

If you don't have Poetry installed:

```bash
# On macOS/Linux
curl -sSL https://install.python-poetry.org | python3 -

# On Windows (PowerShell)
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -
```

Add Poetry to your PATH:

```bash
# Add to your ~/.bashrc, ~/.zshrc, or ~/.profile
export PATH="$HOME/.local/bin:$PATH"
```

## Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/traoreera/xcore.git
cd xcore
```

### 2. Install Dependencies

```bash
poetry install
```

This will:
- Create a virtual environment
- Install all production and development dependencies
- Install pre-commit hooks (if configured)

### 3. Verify Installation

```bash
poetry run xcore --version
# Output: xcore v2.0.0
```

## Environment Configuration

### Create Environment File

```bash
cp .env.example .env
```

Or create `.env` manually:

```bash
# Required variables
echo "APP_SECRET_KEY=$(openssl rand -hex 32)" > .env
echo "PLUGIN_SECRET_KEY=$(openssl rand -hex 32)" >> .env
echo "DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/xcore" >> .env
echo "REDIS_URL=redis://localhost:6379/0" >> .env
```

### Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `APP_SECRET_KEY` | Yes | Application secret (min 32 chars) |
| `PLUGIN_SECRET_KEY` | Yes | Plugin signing key |
| `DATABASE_URL` | Yes | Main database connection |
| `DATABASE_ASYNC_URL` | No | Async database connection |
| `REDIS_URL` | Yes | Redis connection string |
| `SENTRY_DSN` | No | Sentry error tracking |

## Development Setup

### IDE Configuration

#### VS Code

Recommended extensions:
- Python
- Pylance
- Black Formatter
- isort
- YAML

Create `.vscode/settings.json`:

```json
{
  "python.defaultInterpreterPath": "./.venv/bin/python",
  "python.formatting.provider": "black",
  "python.sortImports.args": ["--profile", "black"],
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  }
}
```

#### PyCharm

1. Open the project in PyCharm
2. Set Python interpreter to Poetry virtualenv
3. Enable Black formatter in Settings → Tools → Black

### Pre-commit Hooks

Install pre-commit hooks:

```bash
poetry run pre-commit install
```

## Running the Application

### Development Mode

```bash
# With hot reload
poetry run uvicorn app:app --reload --port 8082

# Or using the Makefile
make run-dev
```

### Production Mode

```bash
# Using the configuration file
XCORE_CONFIG=integration.yaml uvicorn app:app --workers 4

# Or using the Makefile
make run-st
```

### Verify the Server

```bash
curl http://localhost:8082/plugin/status
```

## Troubleshooting

### Common Issues

#### Poetry not found

```bash
# Add to your shell profile
export PATH="$HOME/.local/bin:$PATH"
source ~/.bashrc  # or ~/.zshrc
```

#### Database connection errors

Ensure PostgreSQL is running:

```bash
# macOS with Homebrew
brew services start postgresql

# Ubuntu/Debian
sudo systemctl start postgresql

# Docker
docker run -d -p 5432:5432 -e POSTGRES_DB=xcore -e POSTGRES_USER=user -e POSTGRES_PASSWORD=pass postgres:15
```

#### Redis connection errors

```bash
# macOS with Homebrew
brew services start redis

# Ubuntu/Debian
sudo systemctl start redis

# Docker
docker run -d -p 6379:6379 redis:7-alpine
```

### Getting Help

If you encounter issues:

1. Check the [Troubleshooting Guide](../guides/troubleshooting.md)
2. Search [GitHub Issues](https://github.com/traoreera/xcore/issues)
3. Join [GitHub Discussions](https://github.com/traoreera/xcore/discussions)

## Next Steps

Now that XCore is installed:

- [Create Your First Plugin](../guides/creating-plugins.md)
- [Learn about Configuration](../reference/configuration.md)
- [Explore the Architecture](../architecture/overview.md)
