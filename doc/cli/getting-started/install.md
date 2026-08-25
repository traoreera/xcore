# Installation

Getting started with `xcorecli` is straightforward. The project uses [Poetry](https://python-poetry.org/) for dependency management and a `Makefile` to automate common tasks.

## Prerequisites

- **Python**: 3.12 or higher.
- **Poetry**: Recommended for environment management.
- **Make**: To use the provided automation scripts.

## Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/xcore-team/xcoreCli.git
cd xcorecli
```

### 2. Install Dependencies

You can use the provided `Makefile` to set up the environment and install all necessary packages.

```bash title="Standard Installation"
make install
```

!!! note "What happens under the hood?"
    `make install` runs `poetry lock` and `poetry install`, creating a virtual environment and installing all project dependencies listed in `pyproject.toml`.

### 3. Initialize the Project

After installation, initialize the environment:

```bash title="Initialization"
make init
```

This script sets up necessary permissions and starts the development environment.

## Development Environment

For contributors, you can install additional development and documentation tools:

```bash title="Dev Setup"
make auto-setup
```

!!! tip "MkDocs Serve"
    To view this documentation locally with live-reload, run:
    ```bash
    make docs-serve
    ```

## Python Environment Detection

If you need to check which Python environment `xcorecli` is using:

```bash
make autobuild-ast
```
