import pytest
from xcore.kernel.permissions.engine import PermissionEngine, PermissionDenied
from xcore.kernel.permissions.policies import PolicyEffect

class TestPermissionEngine:
    @pytest.fixture
    def engine(self):
        return PermissionEngine()

    def test_load_and_check(self, engine):
        permissions = [
            {"resource": "db.*", "actions": ["read"], "effect": "allow"}
        ]
        engine.load_from_manifest("test_plugin", permissions)

        # Should allow
        engine.check("test_plugin", "db.users", "read")
        assert engine.allows("test_plugin", "db.users", "read") is True

        # Should deny
        with pytest.raises(PermissionDenied):
            engine.check("test_plugin", "db.users", "write")
        assert engine.allows("test_plugin", "db.users", "write") is False

    def test_memoization(self, engine):
        permissions = [
            {"resource": "db.*", "actions": ["read"], "effect": "allow"}
        ]
        engine.load_from_manifest("test_plugin", permissions)

        # First call, populates cache
        assert engine.allows("test_plugin", "db.users", "read") is True
        assert ("test_plugin", "db.users", "read") in engine._cache

        # Modify policies directly (bypass load_from_manifest to test cache)
        engine._policies["test_plugin"].policies = []

        # Should still allow because of cache
        assert engine.allows("test_plugin", "db.users", "read") is True

        # Clear cache
        engine._cache.clear()

        # Now should deny
        assert engine.allows("test_plugin", "db.users", "read") is False

    def test_cache_invalidation_load(self, engine):
        permissions = [
            {"resource": "db.*", "actions": ["read"], "effect": "allow"}
        ]
        engine.load_from_manifest("test_plugin", permissions)
        engine.allows("test_plugin", "db.users", "read")
        assert len(engine._cache) > 0

        engine.load_from_manifest("test_plugin", [])
        assert len(engine._cache) == 0

    def test_cache_invalidation_grant_all(self, engine):
        engine.load_from_manifest("test_plugin", [{"resource": "db.*", "actions": ["read"], "effect": "deny"}])
        engine.allows("test_plugin", "db.users", "read")
        assert len(engine._cache) > 0

        engine.grant_all("test_plugin")
        assert len(engine._cache) == 0
        assert engine.allows("test_plugin", "db.users", "read") is True
