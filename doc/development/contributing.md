# Contributing Guide

How to contribute to XCore.

## Getting Started

### Fork and Clone

```bash
# Fork the repository on GitHub

# Clone your fork
git clone https://github.com/your-username/xcore.git
cd xcore

# Add upstream remote
git remote add upstream https://github.com/traoreera/xcore.git
```

### Development Setup

```bash
# Install dependencies
poetry install

# Install pre-commit hooks
poetry run pre-commit install

# Run tests
poetry run pytest
```

## Development Workflow

### Branch Naming

- `feature/description` — New features
- `bugfix/description` — Bug fixes
- `docs/description` — Documentation
- `refactor/description` — Refactoring

### Making Changes

```bash
# Create a branch
git checkout -b feature/my-feature

# Make your changes
# ...

# Run tests
poetry run pytest

# Run linting
poetry run black .
poetry run isort .
poetry run flake8

# Commit
poetry run cz commit

# Push
git push origin feature/my-feature
```

### Commit Convention

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: Add new feature
fix: Fix bug
docs: Update documentation
style: Fix formatting
refactor: Refactor code
test: Add tests
chore: Update dependencies
```

## Code Style

### Python

Follow PEP 8 with these specifics:

```python
# Imports: stdlib, third-party, local
import json
from typing import Any

import httpx
from fastapi import APIRouter

from xcore.sdk import TrustedBase


class Plugin(TrustedBase):
    """Class docstring."""

    def method(self, param: str) -> dict:
        """Method docstring."""
        return {}
```

### Formatting

- **Black**: Code formatting
- **isort**: Import sorting
- **flake8**: Linting

```bash
# Auto-format
make lint-fix

# Check only
make lint-check
```

## Testing

### Writing Tests

```python
# tests/test_my_feature.py
import pytest
from xcore import Xcore


@pytest.fixture
async def xcore_app():
    app = Xcore(config_path="tests/test.yaml")
    await app.boot()
    yield app
    await app.shutdown()


async def test_plugin_loading(xcore_app):
    assert xcore_app.plugins is not None
    plugins = xcore_app.plugins.list_plugins()
    assert "test_plugin" in plugins
```

### Running Tests

```bash
# All tests
poetry run pytest

# With coverage
poetry run pytest --cov=xcore --cov-report=html

# Specific test
poetry run pytest tests/test_plugin.py::test_specific

# Parallel
poetry run pytest -n auto
```

## Documentation

### Building Docs

```bash
# Install docs dependencies
poetry install --with docs

# Build
poetry run mkdocs build

# Serve locally
poetry run mkdocs serve
```

### Writing Documentation

- Use clear, concise language
- Include code examples
- Add diagrams where helpful
- Keep line length ≤ 100

## Pull Request Process

1. **Update documentation**
2. **Add tests**
3. **Ensure CI passes**
4. **Request review**

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation

## Testing
- [ ] Tests pass
- [ ] Added tests for new features

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
```

## Release Process

1. Update version in `__version__.py`
2. Update CHANGELOG.md
3. Create release PR
4. Merge and tag
5. GitHub Actions builds and publishes

## Code of Conduct

Be respectful, constructive, and inclusive.

## Questions?

- GitHub Discussions
- Discord: [invite link]
- Email: team@example.com
