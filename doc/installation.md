---
title: Installation & Setup
description: Guide to installing Xcore v2.3.0 and its dependencies.
icon: material/download
---

# Installation & Setup

Xcore requires **Python 3.12** or higher. It uses **Poetry** for dependency management and requires a C++ compiler for the security scanning module.

### Prerequisites

- [x] Python 3.12+ installed
- [x] [Poetry](https://python-poetry.org/docs/#installation) installed
- [x] C++ compiler (GCC, Clang, or MSVC) for `pybind11` extensions
- [ ] Redis (optional, required for Redis cache and background workers)
- [ ] PostgreSQL (optional, required for multi-tenant database isolation)

---

### Step-by-Step Installation

#### 1. Clone the repository
```bash
git clone https://github.com/traoreera/xcore.git
cd xcore
```

#### 2. Install dependencies
Use the provided `makefile` for a standardized setup:

```bash
make install
```

Alternatively, using Poetry directly:
```bash
poetry install --with dev,docs
```

#### 3. Compile the C++ Security Scanner
Xcore uses a compiled C++ module (`scanner_core`) for high-performance AST scanning of sandboxed plugins.

```bash
cd xcore/kernel/security
poetry run python setup.py build_ext --inplace
```

!!! success "Build verification"
    After compilation, you should see a `.so` (Linux/macOS) or `.pyd` (Windows) file in the `xcore/kernel/security/` directory.

---

### Development Environment

To initialize the full development environment (permissions, installation, and dev server):

```bash
make init
```

Press ++ctrl+c++ to stop the server once it starts.

### Docker Support

Xcore includes a `.devcontainer` configuration for VS Code, allowing you to develop in a pre-configured container with all dependencies installed.

```bash
# To build and run using Docker Compose (if provided)
docker-compose up --build
```

---

### Verification

Run the test suite to ensure everything is correctly configured:

```bash
make test
```

!!! note "Security Audit"
    You can also run a security audit on the codebase using Bandit:
    ```bash
    make auto-security
    ```

---

### YAML Configuration

Before running Xcore, ensure you have an `xcore.yaml` (or `integration.yaml`) in your project root.

```yaml linenums="1"
app:
  name: "my-xcore-app"
  env: "development"  # (1)!
  secret_key: "change-me-in-production"  # (2)!

plugins:
  directory: "./plugins"
  strict_trusted: false  # (3)!
```

1.  Set to `production` to enable strict security checks.
2.  **MANDATORY**: Must be changed in production. Xcore will fail to boot if the default value is used in `production` mode.
3.  If `true`, all Trusted plugins must have a valid `.sig` signature file.

---

### See Also

[Quickstart](./quickstart.md)
:   Learn how to integrate Xcore into your FastAPI application.

[CLI Reference](cli/index.md)
:   Explore the `xcore` command-line tools.
