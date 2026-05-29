---
title: CLI Installation
description: Install and set up xcorecli using Poetry and the provided Makefile.
icon: material/download-box
---

# Installation

Getting started with `xcorecli` is straightforward. The project uses [Poetry](https://python-poetry.org/) for dependency management and a `Makefile` to automate common tasks.

## Prerequisites

- **Python**: 3.12 or higher.
- **Poetry**: Recommended for environment management.
- **Make**: To use the provided automation scripts.

## Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/traoreera/xcore.git
cd xcore
```

### 2. Install Dependencies

You can use the provided `Makefile` to set up the environment and install all necessary packages.

```bash title="Standard Installation"
make install
```

!!! note "What happens under the hood?"
    `make install` runs `poetry lock` and `poetry install`, creating a virtual environment and installing all project dependencies listed in `pyproject.toml`.

Alternatively, using Poetry directly:

```bash
poetry install --with dev,docs
```

### 3. Initialize the Project

After installation, initialize the environment:

```bash title="Initialization"
make init
```

This script sets up necessary permissions and starts the development environment.

## Development Environment

For contributors, install additional development and documentation tools:

```bash title="Dev Setup"
make auto-setup
```

!!! tip "MkDocs Serve"
    To view this documentation locally with live-reload, run:
    ```bash
    make docs-serve
    ```

## Verify the Installation

After installation, confirm `xcli` is available:

```bash
xcli --version
# xcorecli 2.3.0

xcli --help
# Usage: xcli [OPTIONS] COMMAND [ARGS]...
#
#   XCore CLI — manage your Xcore project.
#
# Options:
#   --help  Show this message and exit.
#
# Commands:
#   config     Configuration management.
#   health     Global health check.
#   init       Scaffold a new project.
#   manager    Administration and monitoring.
#   migration  Database schema management.
#   plugin     Plugin lifecycle management.
#   sandbox    Sandbox inspection tools.
#   services   Show status of all services.
#   upgrade    Migrate integration.yaml to the latest schema.
#   worker     Background task management.
```

## See Also

[Configuration Guide](configuration.md)
:   Set up your `integration.yaml` file.

[Project Init](../commands/init.md)
:   Scaffold a complete project structure.
