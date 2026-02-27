# Testing Guide

Testing XCore plugins and applications.

## Testing Setup

### Test Dependencies

```bash
# Install test dependencies
poetry install --with test

# Or manually
pip install pytest pytest-asyncio pytest-cov httpx
```

### Test Configuration

```python
# pytest.ini or pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = "-v --cov=xcore --cov-report=html"
```

## Writing Tests

### Basic Plugin Test

```python
# tests/conftest.py
import pytest
from xcore import Xcore


@pytest.fixture
async def xcore_app():
    """Create XCore test instance."""
    app = Xcore(config_path="tests/test.yaml")
    await app.boot()
    yield app
    await app.shutdown()


@pytest.fixture
def test_config():
    """Test configuration."""
    return {
        "database_url": "sqlite:///:memory:",
        "redis_url": "redis://localhost:6379/1"
    }
```

### Testing Plugin Actions

```python
# tests/test_my_plugin.py
import pytest
from xcore import Xcore


@pytest.mark.asyncio
async def test_plugin_ping(xcore_app):
    """Test basic ping action."""
    result = await xcore_app.plugins.call(
        "my_plugin",
        "ping",
        {}
    )

    assert result["status"] == "ok"
    assert result["message"] == "pong"


@pytest.mark.asyncio
async def test_plugin_echo(xcore_app):
    """Test echo action."""
    payload = {"key": "value", "number": 123}

    result = await xcore_app.plugins.call(
        "my_plugin",
        "echo",
        payload
    )

    assert result["status"] == "ok"
    assert result["received"] == payload


@pytest.mark.asyncio
async def test_plugin_error_handling(xcore_app):
    """Test error handling."""
    result = await xcore_app.plugins.call(
        "my_plugin",
        "unknown_action",
        {}
    )

    assert result["status"] == "error"
    assert "code" in result
```

### Testing HTTP Routes

```python
# tests/test_http_routes.py
import pytest
from httpx import AsyncClient
from fastapi import FastAPI


@pytest.fixture
def fastapi_app(xcore_app):
    """Create FastAPI test app."""
    from app import app
    return app


@pytest.mark.asyncio
async def test_list_items(fastapi_app):
    """Test GET /plugins/my_plugin/items/."""
    async with AsyncClient(app=fastapi_app, base_url="http://test") as client:
        response = await client.get("/plugins/my_plugin/items/")

    assert response.status_code == 200
    assert "items" in response.json()


@pytest.mark.asyncio
async def test_create_item(fastapi_app):
    """Test POST /plugins/my_plugin/items/."""
    data = {"name": "Test Item", "value": 42}

    async with AsyncClient(app=fastapi_app, base_url="http://test") as client:
        response = await client.post(
            "/plugins/my_plugin/items/",
            json=data
        )

    assert response.status_code == 201
    result = response.json()
    assert result["name"] == data["name"]
    assert "id" in result


@pytest.mark.asyncio
async def test_item_not_found(fastapi_app):
    """Test 404 handling."""
    async with AsyncClient(app=fastapi_app, base_url="http://test") as client:
        response = await client.get("/plugins/my_plugin/items/99999")

    assert response.status_code == 404
```

### Testing Services

```python
# tests/test_services.py
import pytest


@pytest.mark.asyncio
async def test_database_service(xcore_app):
    """Test database operations."""
    db = xcore_app.services.get("db")

    with db.session() as session:
        # Create test table
        session.execute("""
            CREATE TABLE test_table (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
        """)
        session.commit()

        # Insert data
        session.execute(
            "INSERT INTO test_table (name) VALUES (:name)",
            {"name": "test"}
        )
        session.commit()

        # Query data
        result = session.execute("SELECT * FROM test_table")
        rows = result.fetchall()
        assert len(rows) == 1
        assert rows[0]["name"] == "test"


@pytest.mark.asyncio
async def test_cache_service(xcore_app):
    """Test cache operations."""
    cache = xcore_app.services.get("cache")

    # Set value
    await cache.set("test_key", "test_value", ttl=60)

    # Get value
    value = await cache.get("test_key")
    assert value == "test_value"

    # Check exists
    exists = await cache.exists("test_key")
    assert exists is True

    # Delete
    await cache.delete("test_key")
    value = await cache.get("test_key")
    assert value is None


@pytest.mark.asyncio
async def test_cache_get_or_set(xcore_app):
    """Test cache get_or_set pattern."""
    cache = xcore_app.services.get("cache")

    call_count = 0

    async def expensive_operation():
        nonlocal call_count
        call_count += 1
        return {"data": "expensive"}

    # First call - should execute
    result = await cache.get_or_set(
        "test_expensive",
        factory=expensive_operation,
        ttl=60
    )
    assert result["data"] == "expensive"
    assert call_count == 1

    # Second call - should use cache
    result = await cache.get_or_set(
        "test_expensive",
        factory=expensive_operation,
        ttl=60
    )
    assert result["data"] == "expensive"
    assert call_count == 1  # Not incremented
```

### Testing Events

```python
# tests/test_events.py
import pytest
import asyncio


@pytest.mark.asyncio
async def test_event_emit_and_receive(xcore_app):
    """Test event emission and handling."""
    events = xcore_app.events
    received = []

    @events.on("test.event")
    async def handler(event):
        received.append(event.data)

    # Emit event
    await events.emit("test.event", {"message": "hello"})

    # Wait for handlers
    await asyncio.sleep(0.1)

    assert len(received) == 1
    assert received[0]["message"] == "hello"


@pytest.mark.asyncio
async def test_event_priority(xcore_app):
    """Test event handler priority."""
    events = xcore_app.events
    order = []

    @events.on("priority.test", priority=10)
    async def handler_low(event):
        order.append("low")

    @events.on("priority.test", priority=100)
    async def handler_high(event):
        order.append("high")

    @events.on("priority.test", priority=50)
    async def handler_medium(event):
        order.append("medium")

    await events.emit("priority.test", {})
    await asyncio.sleep(0.1)

    assert order == ["high", "medium", "low"]


@pytest.mark.asyncio
async def test_event_stop_propagation(xcore_app):
    """Test event propagation stopping."""
    events = xcore_app.events
    called = []

    @events.on("stop.test", priority=100)
    async def handler_first(event):
        called.append("first")
        event.stop()

    @events.on("stop.test", priority=50)
    async def handler_second(event):
        called.append("second")

    await events.emit("stop.test", {}, gather=False)

    assert called == ["first"]  # Second not called
```

### Integration Tests

```python
# tests/test_integration.py
import pytest


@pytest.mark.asyncio
async def test_full_user_workflow(xcore_app):
    """Test complete user workflow."""
    # Create user
    create_result = await xcore_app.plugins.call(
        "users",
        "create",
        {
            "username": "testuser",
            "email": "test@example.com",
            "password": "SecurePass123"
        }
    )
    assert create_result["status"] == "ok"
    user_id = create_result["user_id"]

    # Get user
    get_result = await xcore_app.plugins.call(
        "users",
        "get",
        {"user_id": user_id}
    )
    assert get_result["status"] == "ok"
    assert get_result["user"]["username"] == "testuser"

    # Update user
    update_result = await xcore_app.plugins.call(
        "users",
        "update",
        {
            "user_id": user_id,
            "full_name": "Test User"
        }
    )
    assert update_result["status"] == "ok"
    assert update_result["user"]["full_name"] == "Test User"

    # Delete user
    delete_result = await xcore_app.plugins.call(
        "users",
        "delete",
        {"user_id": user_id}
    )
    assert delete_result["status"] == "ok"

    # Verify deletion
    get_result = await xcore_app.plugins.call(
        "users",
        "get",
        {"user_id": user_id}
    )
    assert get_result["status"] == "error"
```

## Mocking

### Mock Services

```python
# tests/test_with_mocks.py
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_db():
    """Create mock database."""
    db = MagicMock()
    db.session.return_value.__enter__ = MagicMock()
    db.session.return_value.__exit__ = MagicMock()
    return db


@pytest.fixture
def mock_cache():
    """Create mock cache."""
    cache = AsyncMock()
    cache.get.return_value = None
    cache.set.return_value = None
    return cache


@pytest.mark.asyncio
async def test_with_mocks(mock_db, mock_cache):
    """Test with mocked services."""
    from my_plugin import Plugin

    plugin = Plugin()
    plugin.ctx = MagicMock()
    plugin.ctx.services.get.side_effect = lambda name: {
        "db": mock_db,
        "cache": mock_cache
    }.get(name)

    # Test plugin logic
    result = await plugin.handle("get_user", {"user_id": "123"})

    # Verify mocks called
    mock_db.session.assert_called()
```

### Mock External APIs

```python
import pytest
import respx
from httpx import Response


@pytest.mark.asyncio
@respx.mock
def test_external_api_call():
    """Test with mocked external API."""
    # Mock the API
    route = respx.post("https://api.example.com/data").mock(
        return_value=Response(200, json={"status": "ok"})
    )

    # Call your code that makes the request
    result = await your_function_that_calls_api()

    # Verify request was made
    assert route.called
    assert result["status"] == "ok"
```

## Running Tests

### Command Line

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=xcore --cov-report=html

# Run specific test file
poetry run pytest tests/test_my_plugin.py

# Run specific test
poetry run pytest tests/test_my_plugin.py::test_ping

# Run with verbose output
poetry run pytest -v

# Run with debug
poetry run pytest --log-cli-level=DEBUG

# Run in parallel
poetry run pytest -n auto

# Run failed tests only
poetry run pytest --lf

# Run with watch mode
poetry run ptw
```

### Makefile Targets

```makefile
# Makefile
test:
	poetry run pytest

test-coverage:
	poetry run pytest --cov=xcore --cov-report=html --cov-report=term

test-watch:
	poetry run ptw
```

## Test Data

### Fixtures

```python
# tests/fixtures.py
import pytest


@pytest.fixture
def sample_user():
    return {
        "id": "user123",
        "username": "testuser",
        "email": "test@example.com",
        "created_at": "2024-01-01T00:00:00"
    }


@pytest.fixture
def sample_items():
    return [
        {"id": "1", "name": "Item 1", "price": 10.99},
        {"id": "2", "name": "Item 2", "price": 20.99},
    ]
```

### Factories

```python
# tests/factories.py
import factory


class UserFactory(factory.Factory):
    class Meta:
        model = dict

    id = factory.Sequence(lambda n: f"user{n}")
    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    created_at = factory.Faker("iso8601")


# Usage
def test_with_factory():
    user = UserFactory()
    assert user["username"].startswith("user")
```

## Continuous Integration

### GitHub Actions

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install Poetry
        run: pip install poetry

      - name: Install dependencies
        run: poetry install

      - name: Run tests
        run: poetry run pytest --cov=xcore --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
```

## Best Practices

1. **Isolate Tests**: Each test should be independent
2. **Use Fixtures**: Reuse setup code
3. **Mock External**: Don't call real external services
4. **Test Edge Cases**: Empty inputs, large inputs, special characters
5. **Fast Tests**: Keep tests under 1 second each
6. **Clear Names**: Describe what the test verifies

```python
# Good
async def test_user_create_fails_with_duplicate_email():
    pass

# Bad
async def test_create():
    pass
```

## Troubleshooting Tests

### Async Issues

```python
# If getting "RuntimeError: no running event loop"
import pytest

@pytest.mark.asyncio
async def test_async():
    pass
```

### Database Locks

```python
# Use separate databases for tests
# integration.yaml for tests
databases:
  default:
    type: sqlite
    url: "sqlite:///:memory:"
```

### Flaky Tests

```python
import pytest

@pytest.mark.flaky(reruns=3)
async def test_sometimes_fails():
    pass
```
