# XCore Test Suite

Comprehensive test suite for XCore framework.

## Structure

```
tests/
├── conftest.py                    # Global fixtures and configuration
├── pytest.ini                     # Pytest configuration
├── README.md                      # This file
│
├── unit/                          # Unit tests
│   ├── kernel/                    # Kernel components
│   │   ├── test_contract.py     # Plugin contracts (TrustedBase, etc.)
│   │   └── test_events.py       # EventBus
│   ├── services/                # Services
│   │   └── test_cache.py        # CacheService
│   ├── plugins/                 # Plugins
│   │   ├── test_base.py         # PluginManifest, etc.
│   │   └── test_decorators.py   # SDK decorators
│   ├── security/                # Security
│   │   └── test_validation.py   # ManifestValidator, ASTScanner
│   └── test_configuration.py    # Configuration loading
│
└── integration/                   # Integration tests
    ├── test_xcore.py            # XCore boot/shutdown
    └── test_plugin_lifecycle.py # Plugin lifecycle
```

## Running Tests

### All Tests

```bash
# Using poetry
poetry run pytest

# Using pip
pytest
```

### Unit Tests Only

```bash
poetry run pytest tests/unit
```

### Integration Tests Only

```bash
poetry run pytest tests/integration
```

### Specific Test File

```bash
poetry run pytest tests/unit/kernel/test_events.py
```

### Specific Test

```bash
poetry run pytest tests/unit/kernel/test_events.py::TestEventBus::test_subscribe_and_emit
```

### With Coverage

```bash
poetry run pytest --cov=xcore --cov-report=html --cov-report=term
```

### Verbose Output

```bash
poetry run pytest -v
```

### Parallel Execution

```bash
poetry run pytest -n auto
```

## Test Categories

### Unit Tests

Fast, isolated tests for individual components:

- **Contract Tests**: Plugin base classes, ok/error responses
- **Event Tests**: EventBus subscription, emission, priorities
- **Cache Tests**: CacheService operations
- **Validation Tests**: Manifest validation, AST scanning
- **Configuration Tests**: Config loading, environment substitution

### Integration Tests

Tests for component interactions:

- **XCore Tests**: Boot/shutdown, service initialization
- **Lifecycle Tests**: Plugin loading, events, health checks

## Writing Tests

### Basic Test Structure

```python
import pytest

class TestMyFeature:
    """Test my feature."""

    def test_something(self):
        """Test something specific."""
        result = my_function()
        assert result == expected

    @pytest.mark.asyncio
    async def test_async_feature(self):
        """Test async feature."""
        result = await my_async_function()
        assert result == expected
```

### Using Fixtures

```python
@pytest.fixture
def mock_service():
    """Create mock service."""
    return MagicMock()

@pytest.mark.asyncio
async def test_with_service(mock_service):
    """Test using mock service."""
    result = await process(mock_service)
    assert result is not None
```

### Markers

```python
@pytest.mark.unit
def test_unit():
    pass

@pytest.mark.integration
def test_integration():
    pass

@pytest.mark.slow
def test_slow():
    pass

@pytest.mark.skip_ci
def test_not_in_ci():
    pass
```

## Coverage Goals

| Component | Target Coverage |
|-----------|-----------------|
| kernel/ | 90% |
| services/ | 85% |
| security/ | 90% |
| configurations/ | 85% |
| sdk/ | 80% |

## CI/CD Integration

Tests run automatically on:
- Pull requests
- Push to main branch
- Release creation

See `.github/workflows/` for CI configuration.

## Troubleshooting

### Tests Failing in CI but Not Locally

- Check environment variables
- Verify test isolation
- Check for race conditions

### Async Test Issues

```python
# Use pytest-asyncio
@pytest.mark.asyncio
async def test_async():
    pass
```

### Database Locks in Tests

Use in-memory SQLite for tests:
```yaml
# test config
databases:
  default:
    type: sqlite
    url: "sqlite:///:memory:"
```

## Contributing

When adding new features:
1. Write tests first (TDD)
2. Ensure tests pass locally
3. Check code coverage
4. Update this README if needed
