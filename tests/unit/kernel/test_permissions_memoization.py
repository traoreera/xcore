import pytest
from xcore.kernel.permissions.engine import PermissionEngine, PermissionDenied
from xcore.kernel.permissions.policies import PolicyEffect

def test_permission_engine_memoization():
    engine = PermissionEngine()
    plugin_name = "test_plugin"

    # 1. Setup policies
    policies = [
        {"resource": "db.*", "actions": ["read"], "effect": "allow"},
    ]
    engine.load_from_manifest(plugin_name, policies)

    # 2. First call (should populate cache)
    assert engine.allows(plugin_name, "db.users", "read") is True
    assert (plugin_name, "db.users", "read") in engine._cache
    assert engine._cache[(plugin_name, "db.users", "read")] == PolicyEffect.ALLOW

    # 3. Modify policies without calling load_from_manifest (simulation)
    # This shouldn't happen in real use, but tests if we are using the cache
    engine._policies[plugin_name].policies = []
    # Even if we removed policies, it should still allow because of cache
    assert engine.allows(plugin_name, "db.users", "read") is True

    # 4. Correctly reload policies (should clear cache)
    engine.load_from_manifest(plugin_name, [{"resource": "other.*", "actions": ["*"], "effect": "allow"}])
    assert (plugin_name, "db.users", "read") not in engine._cache
    assert engine.allows(plugin_name, "db.users", "read") is False # Now denied

    # 5. Test grant_all invalidation
    engine.grant_all(plugin_name)
    assert len(engine._cache) == 0
    assert engine.allows(plugin_name, "db.users", "read") is True
    assert (plugin_name, "db.users", "read") in engine._cache

if __name__ == "__main__":
    test_permission_engine_memoization()
    print("Memoization tests passed!")
