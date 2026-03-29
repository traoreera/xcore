# Contributing to XCore

Thank you for your interest in contributing to XCore! This guide will help you get started with our development process.

## 1. Getting Started

### Fork and Clone
1.  Fork the repository on GitHub.
2.  Clone your fork locally:
    ```bash
    git clone https://github.com/your-username/xcore.git
    cd xcore
    ```

### Development Environment
We use **Poetry** for dependency management.
```bash
# Install dependencies
poetry install

# Activate the virtual environment
poetry shell
```

## 2. Development Workflow

### Branching Policy
-   `main`: The stable branch. Do not commit directly here.
-   `feature/your-feature`: For new features.
-   `fix/bug-name`: For bug fixes.
-   `docs/improvement`: For documentation updates.

### Coding Standards
We follow PEP 8 and use **Black** for formatting.
-   Run `make lint-fix` before committing.
-   Ensure all public classes and methods have docstrings.
-   Use type hints wherever possible.

## 3. Testing

Every new feature or bug fix must include tests.
-   **Unit Tests**: Located in `tests/unit/`.
-   **Integration Tests**: Located in `tests/integration/`.

Run the test suite:
```bash
# Run all tests
make test

# Run with coverage report
poetry run pytest --cov=xcore
```

## 4. Documentation

Documentation is built with **MkDocs Material**.
-   Source files are in the `doc/` directory.
-   To preview documentation locally:
    ```bash
    poetry run mkdocs serve
    ```

## 5. Pull Request Process

1.  Create a new branch from `main`.
2.  Implement your changes and add tests.
3.  Ensure the linting and tests pass.
4.  Commit your changes using [Conventional Commits](https://www.conventionalcommits.org/).
5.  Submit a Pull Request (PR) to the `main` branch.
6.  Provide a clear description of the changes and link any related issues.

## 6. Community

-   **Issues**: Use GitHub Issues to report bugs or suggest features.
-   **Discussions**: Join our GitHub Discussions for questions and ideas.

---
By contributing, you agree that your contributions will be licensed under the project's [MIT License](LICENSE).
