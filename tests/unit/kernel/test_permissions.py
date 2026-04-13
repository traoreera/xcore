import pytest

from xcore.kernel.permissions.engine import PermissionDenied, PermissionEngine
from xcore.kernel.permissions.policies import PolicyEffect


class TestPermissionEngine:
    @pytest.fixture
    def engine(self):
        return PermissionEngine()

    def test_load_and_check(self, engine):
        permissions = [{"resource": "db.*",
                        "actions": ["read"], "effect": "allow"}]
        engine.load_from_manifest("test_plugin", permissions)

        # Should allow
        engine.check("test_plugin", "db.users", "read")
        assert engine.allows("test_plugin", "db.users", "read") is True

        # Should deny
        with pytest.raises(PermissionDenied):
            engine.check("test_plugin", "db.users", "write")
        assert engine.allows("test_plugin", "db.users", "write") is False

    def test_memoization(self, engine):
        permissions = [{"resource": "db.*",
                        "actions": ["read"], "effect": "allow"}]
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
        permissions = [{"resource": "db.*",
                        "actions": ["read"], "effect": "allow"}]
        engine.load_from_manifest("test_plugin", permissions)
        engine.allows("test_plugin", "db.users", "read")
        assert len(engine._cache) > 0

        engine.load_from_manifest("test_plugin", [])
        assert len(engine._cache) == 0

    def test_cache_invalidation_grant_all(self, engine):
        engine.load_from_manifest(
            "test_plugin", [{"resource": "db.*",
                             "actions": ["read"], "effect": "deny"}]
        )
        engine.allows("test_plugin", "db.users", "read")
        assert len(engine._cache) > 0

        engine.grant_all("test_plugin")
        assert len(engine._cache) == 0
        assert engine.allows("test_plugin", "db.users", "read") is True

    def test_audit_log_limits_and_filtering(self, engine):
        engine.load_from_manifest("p1", [{"resource": "*", "actions": ["*"]}])
        engine.load_from_manifest("p2", [{"resource": "*", "actions": ["*"]}])

        # Fill audit log
        for _ in range(10):
            engine.allows("p1", "res", "act")
        for _ in range(5):
            engine.allows("p2", "res", "act")

        # Global limit
        log = engine.audit_log(limit=5)
        assert len(log) == 5

        # Plugin filter
        p2_log = engine.audit_log(plugin_name="p2")
        assert len(p2_log) == 5
        assert all(e["plugin"] == "p2" for e in p2_log)

        # Plugin filter + limit
        p1_log = engine.audit_log(plugin_name="p1", limit=3)
        assert len(p1_log) == 3
        assert all(e["plugin"] == "p1" for e in p1_log)
