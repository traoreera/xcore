import pytest

from xcore.registry.index import PluginRegistry


def test_protected_service_protection():
    registry = PluginRegistry()

    # 1. Register a core service (protected)
    registry.register_core_service("db", {"info": "real_db"})

    # 2. Verify it's there
    assert registry.get_service("db")["info"] == "real_db"

    # 3. Attempt to overwrite from a plugin
    with pytest.raises(PermissionError) as excinfo:
        registry.register_service("malicious_plugin", "db", {"info": "fake_db"})

    assert "Impossible d'écraser le service protégé 'db'" in str(excinfo.value)

    # 4. Verify the original service is still there
    assert registry.get_service("db")["info"] == "real_db"


def test_public_service_overwrite():
    registry = PluginRegistry()

    # 1. Register a public service
    registry.register_service("plugin1", "svc", {"val": 1})

    # 2. Overwrite it (public services can be overwritten by other plugins,
    # though it might log a warning, the code currently allows it unless protected)
    registry.register_service("plugin2", "svc", {"val": 2})

    assert registry.get_service("svc")["val"] == 2
