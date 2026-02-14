# GEMINI.md: Project Overview

## Project Overview

This project, named "xcore," is a sophisticated Python-based framework for FastAPI designed to dynamically manage plugins, execute scheduled tasks, and provide a comprehensive administration and monitoring interface. The framework is built to allow for hot-reloading of plugins, isolation of plugins in a sandboxed environment, and detailed monitoring of their performance.

The core of the project is a `Manager` class that orchestrates the entire plugin lifecycle, from loading and unloading to execution and resource management. The framework is designed to be highly modular, with a clear separation of concerns between the core application and the plugins.

### Key Technologies

*   **Backend Framework:** FastAPI
*   **Plugin Management:** Custom-built plugin management system with support for "Trusted" and "Sandboxed" plugins.
*   **Database:** SQLAlchemy with Alembic for migrations.
*   **Task Scheduling:** APScheduler for running background tasks.
*   **Dependency Management:** Poetry
*   **Configuration:** Pydantic and `.env` files.
*   **Security:** Passlib for password hashing, JWT for authentication.

### Architecture

The project follows a modular architecture with a central `Manager` that handles the plugin lifecycle. The application is structured as follows:

*   **`main.py` & `app.py`:** The entry points of the FastAPI application. `app.py` initializes the `Manager` and integrates it into the FastAPI application's lifecycle.
*   **`xcore/`:** This directory contains the core framework components, including the `Manager`, the plugin sandbox, and other essential utilities.
*   **`integrations/`:** This directory contains the integration logic, including the routes for managing plugins and tasks, and the database models.
*   **`plugins/`:** This directory is where the custom plugins are located. The framework dynamically loads and manages the plugins from this directory.
*   **`pyproject.toml`:** Defines the project dependencies and other metadata.
*   **`README.md`:** Provides a detailed overview of the project, its features, and how to get started.

## Building and Running

### Prerequisites

*   Python >= 3.11
*   Poetry

### Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/traoreera/xcore.git
    ```
2.  Navigate to the project directory:
    ```bash
    cd xcore
    ```
3.  Install the dependencies using Poetry:
    ```bash
    poetry install
    ```

### Running the Application

To run the FastAPI application, use the following command:

```bash
uvicorn main:app --reload
```

This will start the server, and you can access the API documentation at `http://127.0.0.1:8000/docs`.

### Running Tests

To run the tests, you will need to install the development dependencies and then run `pytest`:

```bash
poetry install --with dev
pytest
```

## Development Conventions

*   **Code Style:** The project uses `black` for code formatting and `flake8` for linting. The maximum line length is 88 characters.
*   **Plugin Development:** Plugins are developed as separate modules within the `plugins/` directory. Each plugin must have a specific structure, including a `run.py` file that contains the plugin's metadata and a `Plugin` class.
*   **Commits:** The project does not have a strict commit message format, but the commit history suggests using descriptive messages that explain the changes made.
*   **Branching:** The `README.md` suggests using a `feature/xyz` branching model for new features.
*   **Database Migrations:** Database migrations are managed using Alembic. The `pyproject.toml` file defines several scripts for managing migrations.
