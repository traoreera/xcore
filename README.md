# ⚡ XCore Framework

[![Version](https://img.shields.io/badge/version-2.1.2-blue.svg)](https://github.com/traoreera/xcore)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135+-green.svg)](https://fastapi.tiangolo.com/)

**XCore** is a high-performance, plugin-first orchestration framework built on top of **FastAPI**. It is designed to load, isolate, and manage modular extensions (plugins) in a secure, sandboxed environment.

## 🏗️ Architecture Overview

XCore follows a "minimal core" philosophy where most features are provided via plugins or shared services.

```mermaid
flowchart TB
    subgraph Core["XCore Kernel"]
        X[Orchestrator] --> PS[Plugin Supervisor]
        X --> EB[Event Bus]
        X --> SC[Service Container]
    end

    PS --> Trusted[Trusted Plugins]
    PS --> Sandbox[Sandboxed Plugins]

    SC --> DB[(Database)]
    SC --> RD[(Redis)]
    SC --> SCH[Scheduler]
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.11+**
- **Poetry** (Package Manager)

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/traoreera/xcore
   cd xcore
   ```

2. **Install dependencies**:
   ```bash
   poetry install
   ```

3. **Run the development server**:
   ```bash
   poetry run uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

### Quick Install (uv)
```bash
uv add "xcore @ git+https://github.com/traoreera/xcore"
```

---

## 💻 Usage

### 1. Integration with FastAPI

```python
from fastapi import FastAPI
from xcore import Xcore
from contextlib import asynccontextmanager

xcore = Xcore(config_path="xcore.yaml")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await xcore.boot(app)
    yield
    await xcore.shutdown()

app = FastAPI(lifespan=lifespan)
```

### 2. Standalone Usage

```python
from xcore import Xcore

async def main():
    app = Xcore()
    await app.boot()

    # Call a plugin action
    result = await app.plugins.call("users_plugin", "get_user", {"id": 1})
    print(result)

    await app.shutdown()
```

---

## 🔌 Plugin Development

Plugins reside in the `plugins/` directory. A standard plugin structure looks like this:

```text
plugins/my_plugin/
├── plugin.yaml      # Manifest (metadata & entry point)
├── plugin.sig       # Security signature (for trusted plugins)
└── src/
    └── main.py      # Core logic
```

---

## 🛠️ CLI Reference

XCore comes with a powerful CLI for management and security.

| Command | Description |
| :--- | :--- |
| `xcore plugin list` | List all loaded plugins |
| `xcore plugin load <name>` | Load a specific plugin |
| `xcore plugin reload <name>` | Hot-reload a plugin |
| `xcore plugin info <name>` | Show plugin metadata and permissions |
| `xcore plugin sign <path>` | Generate a security signature for a plugin |
| `xcore plugin verify <path>` | Verify plugin signature |
| `xcore plugin validate <path>`| Validate plugin manifest and structure |
| `xcore plugin health` | Run plugin health checks |
| `xcore services status` | Check the health of DB, Cache, and Scheduler |
| `xcore health` | Perform a global system health check |

---

## 🧪 Quality & Performance

XCore is built with reliability and speed in mind:
- **Test Suite**: Automated unit, integration, and security tests.
- **Security**: Built-in AST scanning for forbidden imports and attribute access.
- **Benchmarks**: Integrated performance monitoring for core components.

---

## 📜 Makefile Commands

| Command | Description |
| :--- | :--- |
| `make install` | Install project dependencies |
| `make dev` | Run development server with auto-reload |
| `make test` | Run the test suite |
| `make lint-check` | Validate formatting/linting without modifying files |
| `make benchmark` | Run performance benchmarks with pytest-benchmark |
| `make lint-fix` | Auto-format code (Black, Isort, Autopep8) |
| `make security-check` | Run basic project security checks |
| `make pre-commit-run` | Run pre-commit hooks on all files |
| `make logs-live` | View real-time structured logs |

---

## 📄 License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

---

<p align="center">
  Built with ❤️ by <b>Xcore team's</b>
</p>
