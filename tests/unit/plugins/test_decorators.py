"""
Tests for SDK decorators.
"""

from unittest.mock import MagicMock

import pytest

from xcore.sdk.decorators import action, require_service, route, validate_payload


class TestActionDecorator:
    """Test @action decorator."""

    @pytest.mark.asyncio
    async def test_action_decorator(self):
        """Test action decorator functionality."""

        class Plugin:
            @action("process")
            async def process_action(self, payload):
                return {"status": "ok"}

        plugin = Plugin()

        # Check decorator added metadata
        assert hasattr(plugin.process_action, "_action_name")
        assert plugin.process_action._action_name == "process"


class TestRouteDecorator:
    """Test @route decorator."""

    def test_route_decorator(self):
        """Test route decorator."""
        MagicMock()

        class Plugin:
            @route.get("/items")
            async def list_items(self):
                return []

        plugin = Plugin()

        # Verify route metadata
        assert hasattr(plugin.list_items, "_route_path")
        assert plugin.list_items._route_path == "/items"


class TestRequireServiceDecorator:
    """Test @require_service decorator."""

    @pytest.mark.asyncio
    async def test_require_service(self):
        """Test require_service decorator."""

        class Plugin:
            ctx = MagicMock()
            ctx.services = {"db": MagicMock()}

            @require_service("db")
            async def get_data(self, db):
                return db.query()

        plugin = Plugin()
        plugin.ctx.services.get.return_value = MagicMock()

        await plugin.get_data()

        plugin.ctx.services.get.assert_called_with("db")


class TestValidatePayloadDecorator:
    """Test @validate_payload decorator."""

    @pytest.mark.asyncio
    async def test_validate_payload(self):
        """Test payload validation."""
        from pydantic import BaseModel

        class InputModel(BaseModel):
            name: str
            count: int

        class Plugin:
            @validate_payload(InputModel)
            async def create(self, data: InputModel):
                return {"name": data.name, "count": data.count}

        plugin = Plugin()

        # Valid payload
        result = await plugin.create({"name": "test", "count": 5})
        assert result["name"] == "test"
        assert result["count"] == 5

        # Invalid payload should raise
        with pytest.raises(Exception):
            await plugin.create({"name": "test", "count": "not_an_int"})
