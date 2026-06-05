"""Tests for PluginContext."""

import pytest
from unittest.mock import MagicMock

from xcore.kernel.api.context import PluginContext


class TestPluginContext:
    def test_default_tenant(self):
        ctx = PluginContext(name="auth")
        assert ctx.tenant_id == "default"

    def test_get_service_found(self):
        ctx = PluginContext(name="auth", services={"db": "mydb"})
        assert ctx.get_service("db") == "mydb"

    def test_get_service_not_found_raises(self):
        ctx = PluginContext(name="auth", services={})
        with pytest.raises(KeyError, match="db"):
            ctx.get_service("db")

    def test_has_service_true(self):
        ctx = PluginContext(name="auth", services={"db": "mydb"})
        assert ctx.has_service("db") is True

    def test_has_service_false(self):
        ctx = PluginContext(name="auth", services={})
        assert ctx.has_service("db") is False

    def test_repr(self):
        ctx = PluginContext(name="auth", services={"db": "mydb"})
        r = repr(ctx)
        assert "auth" in r
        assert "db" in r

    def test_get_service_via_registry(self):
        registry = MagicMock()
        registry.get_service.return_value = "registry_db"
        ctx = PluginContext(name="auth", services={"db": "direct_db"}, registry=registry)
        result = ctx.get_service("db")
        assert result == "registry_db"
        registry.get_service.assert_called_once_with("db", requester="auth")

    def test_get_service_registry_permission_error(self):
        registry = MagicMock()
        registry.get_service.side_effect = PermissionError("not allowed")
        ctx = PluginContext(name="auth", services={"db": "direct_db"}, registry=registry)
        with pytest.raises(PermissionError):
            ctx.get_service("db")

    def test_get_service_registry_key_error_falls_back(self):
        registry = MagicMock()
        registry.get_service.side_effect = KeyError("db")
        ctx = PluginContext(name="auth", services={"db": "direct_db"}, registry=registry)
        result = ctx.get_service("db")
        assert result == "direct_db"

    def test_env_default_empty(self):
        ctx = PluginContext(name="auth")
        assert ctx.env == {}

    def test_config_default_empty(self):
        ctx = PluginContext(name="auth")
        assert ctx.config == {}
