# Installation

This guide covers the installation of XCore Framework for development and production environments.

---

## 1. Prerequisites

XCore requires a modern Python environment:

-   **Python 3.11+**: Built on the latest `asyncio` features.
-   **Package Manager**: [Poetry](https://python-poetry.org/) is strongly recommended, but `pip` is also supported.
-   **OS**: Linux or macOS are recommended for the best sandboxing experience. Windows is supported for development.

---

## 2. Standard Installation

### Using Poetry (Recommended)
```bash
# Clone the repository
git clone https://github.com/traoreera/xcore.git
cd xcore

# Install core dependencies
poetry install

# Activate the environment
poetry shell
```

### Using Pip
```bash
pip install xcore-framework
```

---

## 3. Database & Service Drivers

By default, XCore comes with SQLite support. For other backends, install the required drivers:

```bash
# PostgreSQL
pip install asyncpg psycopg2-binary

# MySQL
pip install mysql-connector-python

# Redis (for Cache & Scheduler)
pip install redis hiredis
```

---

## 4. Environment Configuration

XCore uses a dual configuration system: `xcore.yaml` for system structure and `.env` for secrets.

1.  **Initialize Configuration**:
    ```bash
    cp .env.example .env
    ```

2.  **Required Environment Variables**:
    Ensure these are set in your `.env`:
    ```env
    XCORE_SECRET_KEY=generate-a-secure-random-string
    XCORE_SERVER_KEY=another-secure-random-string
    DATABASE_URL=sqlite+aiosqlite:///./xcore.db
    ```

---

## 5. Verification

Run the built-in health check to ensure everything is configured correctly:

```bash
xcore health
```

You should see a "Healthy" status for the Kernel and all enabled services.
