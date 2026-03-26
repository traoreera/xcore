import pytest
from xcore.registry.index import PluginRegistry

def test_registry_service_registration():
    registry = PluginRegistry()

    # Mock plugin handler
    class MockHandler:
        manifest = type('Manifest', (), {'version': '1.0.0', 'execution_mode': type('Mode', (), {'value': 'trusted'})()})

    registry.register("plugin1", MockHandler())

    # Register service
    service_obj = {"key": "value"}
    registry.register_service("plugin1", "my_service", service_obj, metadata={"scope": "public"})

    # Retrieve service
    assert registry.get_service("my_service") == service_obj

    # List services
    services = registry.list_services()
    assert len(services) == 1
    assert services[0]["name"] == "my_service"
    assert services[0]["plugin"] == "plugin1"

def test_registry_service_scoping():
    registry = PluginRegistry()
    registry.register_service("plugin1", "private_svc", {"secret": 123}, metadata={"scope": "private"})

    # Access by owner should work
    assert registry.get_service("private_svc", requester="plugin1") == {"secret": 123}

    # Access by others should fail
    with pytest.raises(PermissionError):
        registry.get_service("private_svc", requester="plugin2")

def test_registry_unregister_cleans_services():
    registry = PluginRegistry()
    registry.register("plugin1", type('H', (), {'manifest': None})())
    registry.register_service("plugin1", "svc1", {})
    registry.register_service("plugin2", "svc2", {})

    assert len(registry.list_services()) == 2

    registry.unregister("plugin1")
    services = registry.list_services()
    assert len(services) == 1
    assert services[0]["name"] == "svc2"
