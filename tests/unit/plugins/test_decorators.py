"""
Tests for SDK decorators.
"""

from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from xcore.sdk.decorators import (
    AutoDispatchMixin,
    RoutedPlugin,
    action,
    require_service,
    route,
    sandboxed,
    trusted,
    validate_payload,
)


class TestActionDecorator:
    """Test @action decorator."""

    def test_action_decorator(self):
        """Test action decorator marks function with _xcore_action."""

        class Plugin:
            @action("process")
            async def process_action(self, payload):
                return {"status": "ok"}

        plugin = Plugin()

        # Check decorator added metadata
        assert hasattr(plugin.process_action, "_xcore_action")
        assert plugin.process_action._xcore_action == "process"


class TestTrustedDecorator:
    """Test @trusted decorator."""

    def test_trusted_marks_function(self):
        """Test that trusted decorator marks function."""

        @trusted
        async def trusted_func(self, payload: dict) -> dict:
            return {"status": "ok"}

        assert hasattr(trusted_func, "_xcore_trusted_only")
        assert trusted_func._xcore_trusted_only is True


class TestSandboxedDecorator:
    """Test @sandboxed decorator."""

    def test_sandboxed_marks_function(self):
        """Test that sandboxed decorator marks function."""

        @sandboxed
        async def sandboxed_func(self, payload: dict) -> dict:
            return {"status": "ok"}

        assert hasattr(sandboxed_func, "_xcore_sandboxed")
        assert sandboxed_func._xcore_sandboxed is True


class TestRouteDecorator:
    """Test @route decorator."""

    def test_route_decorator(self):
        """Test route decorator."""

        class Plugin:
            @route("/items", method="GET")
            async def list_items(self):
                return []

        plugin = Plugin()

        # Verify route metadata
        assert hasattr(plugin.list_items, "_xcore_route")
        assert plugin.list_items._xcore_route["path"] == "/items"
        assert plugin.list_items._xcore_route["method"] == "GET"

    def test_route_full_config(self):
        """Test route decorator with full configuration."""

        class Plugin:
            @route(
                "/items/{item_id}",
                method="GET",
                tags=["items"],
                summary="Get an item",
                status_code=200,
            )
            async def get_item(self, item_id: int):
                return {"id": item_id}

        plugin = Plugin()

        route_info = plugin.get_item._xcore_route
        assert route_info["path"] == "/items/{item_id}"
        assert route_info["method"] == "GET"
        assert route_info["tags"] == ["items"]
        assert route_info["summary"] == "Get an item"
        assert route_info["status_code"] == 200


class TestRequireServiceDecorator:
    """Test @require_service decorator."""

    @pytest.mark.asyncio
    async def test_require_service_success(self):
        """Test require_service decorator when service is available."""

        class Plugin:
            def get_service(self, name):
                return MagicMock()

            @require_service("db")
            async def get_data(self, payload: dict) -> dict:
                return {"status": "ok"}

        plugin = Plugin()

        result = await plugin.get_data({})
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_require_service_failure(self):
        """Test require_service decorator when service is missing."""

        class Plugin:
            def get_service(self, name):
                raise KeyError(f"Service '{name}' not found")

            @require_service("db")
            async def get_data(self, payload: dict) -> dict:
                return {"status": "ok"}

        plugin = Plugin()

        with pytest.raises(KeyError, match="db"):
            await plugin.get_data({})

    @pytest.mark.asyncio
    async def test_require_service_multiple(self):
        """Test require_service with multiple services."""

        services_called = []

        class Plugin:
            def get_service(self, name):
                services_called.append(name)
                return MagicMock()

            @require_service("db", "cache")
            async def get_data(self, payload: dict) -> dict:
                return {"status": "ok"}

        plugin = Plugin()

        await plugin.get_data({})
        assert "db" in services_called
        assert "cache" in services_called

    def test_require_service_stores_requirements(self):
        """Test that require_service stores service requirements."""

        class Plugin:
            @require_service("db", "cache", "scheduler")
            async def my_action(self, payload: dict) -> dict:
                return {"status": "ok"}

        plugin = Plugin()

        assert hasattr(plugin.my_action, "_requires_services")
        assert plugin.my_action._requires_services == ["db", "cache", "scheduler"]


class TestValidatePayloadDecorator:
    """Test @validate_payload decorator."""

    @pytest.mark.asyncio
    async def test_validate_payload(self):
        """Test payload validation."""

        class InputModel(BaseModel):
            name: str
            count: int

        class Plugin:
            @validate_payload(InputModel, type_response="dict")
            async def create(self, data: dict):
                return {"name": data["name"], "count": data["count"]}

        plugin = Plugin()

        # Valid payload
        result = await plugin.create({"name": "test", "count": 5})
        assert result["name"] == "test"
        assert result["count"] == 5

    @pytest.mark.asyncio
    async def test_validate_payload_invalid(self):
        """Test payload validation with invalid data."""

        class InputModel(BaseModel):
            name: str
            count: int

        class Plugin:
            @validate_payload(InputModel)
            async def create(self, data):
                return {"name": data.name, "count": data.count}

        plugin = Plugin()

        # Invalid payload should return error dict
        result = await plugin.create({"name": "test", "count": "not_an_int"})
        assert result["status"] == "error"
        assert result["code"] == "validation_error"


class TestAutoDispatchMixin:
    """Test AutoDispatchMixin class."""

    @pytest.mark.asyncio
    async def test_handle_calls_marked_action(self):
        """Test handle() calls method marked with @action."""

        class TestPlugin(AutoDispatchMixin):
            @action("greet")
            async def greet(self, payload: dict) -> dict:
                return {"status": "ok", "msg": f"Hello {payload.get('name')}"}

        plugin = TestPlugin()
        result = await plugin.handle("greet", {"name": "World"})

        assert result["status"] == "ok"
        assert result["msg"] == "Hello World"

    @pytest.mark.asyncio
    async def test_handle_unknown_action(self):
        """Test handle() returns error for unknown action."""

        class TestPlugin(AutoDispatchMixin):
            @action("greet")
            async def greet(self, payload: dict) -> dict:
                return {"status": "ok"}

        plugin = TestPlugin()
        result = await plugin.handle("unknown", {})

        assert result["status"] == "error"
        assert "unknown" in result["msg"]
        assert result["code"] == "unknown_action"

    @pytest.mark.asyncio
    async def test_handle_lists_available_actions(self):
        """Test handle() error message lists available actions."""

        class TestPlugin(AutoDispatchMixin):
            @action("action1")
            async def method1(self, payload: dict) -> dict:
                return {"status": "ok"}

            @action("action2")
            async def method2(self, payload: dict) -> dict:
                return {"status": "ok"}

        plugin = TestPlugin()
        result = await plugin.handle("unknown", {})

        assert "action1" in result["msg"]
        assert "action2" in result["msg"]


class TestRoutedPlugin:
    """Test RoutedPlugin class."""

    @pytest.mark.asyncio
    async def test_routerin_returns_router(self):
        """Test RouterIn returns APIRouter."""
        pytest.importorskip("fastapi")

        class TestPlugin(RoutedPlugin):
            @route("/ping", method="GET")
            async def ping(self):
                return {"pong": True}

        plugin = TestPlugin()
        router = plugin.RouterIn()

        assert router is not None
        assert len(router.routes) == 1

    def test_routerin_no_routes(self):
        """Test RouterIn returns None when no routes defined."""

        class TestPlugin(RoutedPlugin):
            pass

        plugin = TestPlugin()
        router = plugin.RouterIn()

        assert router is None
