# Installation

This guide covers the installation of XCore Framework for development and production environments.

## Prerequisites

Before you begin, ensure you have the following installed on your system:

- **Python 3.11+**: The core framework and plugins require Python 3.11 or newer.
- **Poetry**: Recommended for dependency management and project isolation.
- **Git**: For cloning the repository.
- **Make** (Optional): For using provided shortcuts (e.g., `make init`).

## Standard Installation

To install XCore and its dependencies in a virtual environment:

1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/traoreera/xcore.git
    cd xcore
    ```

2.  **Initialize Project with Poetry**:
    ```bash
    poetry install
    ```
    This will install the core dependencies, including FastAPI, Pydantic, and others required for basic operation.

3.  **Install Optional Extensions**:
    Depending on your database or cache choice, you may need additional libraries:
    ```bash
    # For Redis support
    poetry add aioredis

    # For PostgreSQL support
    poetry add asyncpg psycopg2-binary
    ```

## Environment Configuration

XCore uses a `.env` file for sensitive configuration (passwords, API keys) and an `xcore.yaml` for system-wide settings.

1.  **Copy Example Environment**:
    ```bash
    cp .env.example .env
    ```

2.  **Edit `.env`**:
    Update the values to match your local or production environment:
    ```env
    XCORE_ENV=development
    DATABASE_URL=postgresql+asyncpg://user:password@localhost/xcore
    REDIS_URL=redis://localhost:6379/0
    SECRET_KEY=your_secure_secret_key
    ```

## Initializing and Running

The easiest way to get started is using the `make` commands:

```bash
# Install dependencies and run the development server
make init

# Alternatively, run manually
poetry run uvicorn app:app --reload --port 8082
```

## Verifying the Installation

Once the server is running, you can verify the installation by accessing the health endpoint or using the CLI:

- **Health Check**: `http://localhost:8082/health`
- **CLI Check**:
  ```bash
  PYTHONPATH=. python -m xcore.cli.main health
  ```

If everything is configured correctly, you should see a JSON response indicating that the kernel and services are "healthy".

## Production Deployment Considerations

For production environments, ensure you:
- Use a production-grade WSGI/ASGI server (e.g., `gunicorn` with `uvicorn` workers).
- Disable `debug` mode in `xcore.yaml`.
- Secure your `SECRET_KEY`.
- Set up proper monitoring and logging (XCore integrates with standard Python logging).
