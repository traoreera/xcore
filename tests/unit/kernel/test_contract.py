"""
Tests for plugin contracts (TrustedBase, ok, error).
"""

from unittest.mock import MagicMock

import pytest

from xcore.kernel.api.contract import ExecutionMode, TrustedBase, error, ok


class TestExecutionMode:
    """Test ExecutionMode enum."""

    def test_trusted_mode(self):
        """Test TRUSTED execution mode."""
        assert ExecutionMode.TRUSTED == "trusted"
        assert ExecutionMode.TRUSTED.value == "trusted"

    def test_sandboxed_mode(self):
        """Test SANDBOXED execution mode."""
        assert ExecutionMode.SANDBOXED == "sandboxed"
        assert ExecutionMode.SANDBOXED.value == "sandboxed"

    def test_legacy_mode(self):
        """Test LEGACY execution mode."""
        assert ExecutionMode.LEGACY == "legacy"
        assert ExecutionMode.LEGACY.value == "legacy"


class TestOkResponse:
    """Test ok() response builder."""

    def test_ok_minimal(self):
        """Test minimal ok response."""
        result = ok()
        assert result == {"status": "ok"}

    def test_ok_with_data(self):
        """Test ok with data dictionary."""
        result = ok({"message": "success", "id": "123"})
        assert result["status"] == "ok"
        assert result["message"] == "success"
        assert result["id"] == "123"

    def test_ok_with_kwargs(self):
        """Test ok with keyword arguments."""
        result = ok(count=5, items=[1, 2, 3])
        assert result["status"] == "ok"
        assert result["count"] == 5
        assert result["items"] == [1, 2, 3]

    def test_ok_with_data_and_kwargs(self):
        """Test ok with both data and kwargs."""
        result = ok({"id": "1"}, name="test")
        assert result["status"] == "ok"
        assert result["id"] == "1"
        assert result["name"] == "test"


class TestErrorResponse:
    """Test error() response builder."""

    def test_error_minimal(self):
        """Test minimal error response."""
        result = error("Something went wrong")
        assert result == {"status": "error", "msg": "Something went wrong"}

    def test_error_with_code(self):
        """Test error with code."""
        result = error("Not found", code="not_found")
        assert result["status"] == "error"
        assert result["msg"] == "Not found"
        assert result["code"] == "not_found"

    def test_error_with_extra(self):
        """Test error with extra fields."""
        result = error("Validation failed", code="validation", field="email")
        assert result["status"] == "error"
        assert result["msg"] == "Validation failed"
        assert result["code"] == "validation"
        assert result["field"] == "email"


class TestTrustedBase:
    """Test TrustedBase plugin class."""

    def test_trusted_base_init(self):
        """Test TrustedBase initialization."""

        class TestPlugin(TrustedBase):
            async def handle(self, action, payload):
                return ok()

        plugin = TestPlugin()
        assert plugin.ctx is None

    @pytest.mark.asyncio
    async def test_inject_context(self):
        """Test context injection."""

        class TestPlugin(TrustedBase):
            async def handle(self, action, payload):
                return ok()

        plugin = TestPlugin()
        mock_ctx = MagicMock()
        mock_ctx.services = {"db": MagicMock()}

        await plugin._inject_context(mock_ctx)

        assert plugin.ctx == mock_ctx
        assert plugin._services == mock_ctx.services

    @pytest.mark.asyncio
    async def test_get_service(self):
        """Test getting a service."""

        class TestPlugin(TrustedBase):
            async def handle(self, action, payload):
                return ok()

        plugin = TestPlugin()
        mock_db = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.services = {"db": mock_db}

        await plugin._inject_context(mock_ctx)

        service = plugin.get_service("db")
        assert service == mock_db

    def test_get_service_without_context(self):
        """Test getting service without context raises error."""

        class TestPlugin(TrustedBase):
            async def handle(self, action, payload):
                return ok()

        plugin = TestPlugin()

        with pytest.raises(RuntimeError) as exc:
            plugin.get_service("db")

        assert "Contexte non injecté" in str(exc.value)

    @pytest.mark.asyncio
    async def test_get_service_not_found(self):
        """Test getting non-existent service."""

        class TestPlugin(TrustedBase):
            async def handle(self, action, payload):
                return ok()

        plugin = TestPlugin()
        mock_ctx = MagicMock()
        mock_ctx.services = {}
        mock_ctx.services.keys = lambda: []

        await plugin._inject_context(mock_ctx)

        with pytest.raises(KeyError) as exc:
            plugin.get_service("db")

        assert "indisponible" in str(exc.value)

    def test_get_router_default(self):
        """Test default get_router returns None."""

        class TestPlugin(TrustedBase):
            async def handle(self, action, payload):
                return ok()

        plugin = TestPlugin()
        assert plugin.get_router() is None

    def test_lifecycle_hooks(self):
        """Test lifecycle hooks exist and are callable."""

        class TestPlugin(TrustedBase):
            async def handle(self, action, payload):
                return ok()

            async def on_load(self):
                pass

            async def on_unload(self):
                pass

            async def on_reload(self):
                pass

        plugin = TestPlugin()
        assert hasattr(plugin, "on_load")
        assert hasattr(plugin, "on_unload")
        assert hasattr(plugin, "on_reload")

    @pytest.mark.asyncio
    async def test_abstract_handle(self):
        """Test that handle is abstract."""

        class IncompletePlugin(TrustedBase):
            pass

        with pytest.raises(TypeError) as exc:
            IncompletePlugin()

        assert "abstract" in str(exc.value).lower()
