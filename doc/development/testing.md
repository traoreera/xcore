# Testing Guide

This guide covers how to test XCore plugins and the framework itself.

## 1. Testing Setup

Ensure you have the test dependencies installed:
```bash
poetry install --with test
```

We use **pytest** as our primary testing framework.

## 2. Testing Plugins

Plugins should be tested for both their IPC actions and their HTTP routes.

### IPC Action Testing
Use a standard `pytest` class and the `Xcore` instance in test mode.

```python
import pytest
from xcore import Xcore

@pytest.fixture
async def app():
    x = Xcore(config_path="tests/test_config.yaml")
    await x.boot()
    yield x
    await x.shutdown()

@pytest.mark.asyncio
async def test_my_plugin_action(app):
    # Call a plugin action directly
    result = await app.plugins.call("my_plugin", "ping", {})
    assert result["status"] == "ok"
    assert result["message"] == "pong"
```

### HTTP Route Testing
Use `httpx.AsyncClient` to test plugin-exposed FastAPI routes.

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_plugin_route(app):
    async with AsyncClient(app=app.fastapi_app, base_url="http://test") as ac:
        response = await ac.get("/plugins/my_plugin/hello")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello World"}
```

## 3. Mocking Services

When testing plugins, you may want to mock core services like the database or cache.

```python
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_with_mock_cache(app):
    # Mock the cache service
    mock_cache = AsyncMock()
    app.services.register_service("cache", mock_cache)

    await app.plugins.call("my_plugin", "save_data", {"key": "val"})
    mock_cache.set.assert_called_with("val", ...)
```

## 4. Testing Sandboxed Plugins

To test sandboxed plugins, use the XCore CLI to run them in an isolated environment.

```bash
# Run a plugin in a test sandbox
xcore sandbox run my_plugin

# Verify resource limits are enforced
xcore sandbox limits my_plugin
```

## 5. Best Practices

1.  **Isolated State**: Each test should run with a clean state. Use fixtures to boot/shutdown the app.
2.  **Test Edge Cases**: Include tests for invalid inputs, rate limit hits, and permission denials.
3.  **Use Coverage**: Aim for at least 80% code coverage in your plugins.
    ```bash
    pytest --cov=plugins/my_plugin
    ```
4.  **Mock Externals**: Always mock external API calls to keep tests fast and deterministic.
