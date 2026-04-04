from unittest.mock import MagicMock

import pytest

from xcore.kernel.api.contract import BasePlugin
from xcore.kernel.runtime.lifecycle import LifecycleManager


class MockPlugin(BasePlugin):
    def __init__(self, services):
        self._services = services

    async def handle(self, action, payload):
        return {"status": "ok"}


@pytest.fixture
def mock_manifest():
    manifest = MagicMock()
    manifest.name = "malicious_plugin"
    manifest.plugin_dir = MagicMock()
    manifest.entry_point = "main.py"
    manifest.resources.timeout_seconds = 10
    return manifest


@pytest.mark.asyncio
async def test_lifecycle_propagate_services_protection():
    from xcore.registry.index import PluginRegistry
    shared_services = {"db": "core_db", "cache": "core_cache"}
    registry = PluginRegistry()
    # Register "db" as a core service in the registry to protect it
    registry.register_core_service("db", "core_db")

    # Instance du plugin qui tente d'écraser 'db'
    plugin_instance = MockPlugin(services={"db": "malicious_db"})

    lm = LifecycleManager(MagicMock(), shared_services, registry=registry)
    lm._instance = plugin_instance
    lm.manifest.name = "malicious_plugin"

    # L'appel à propagate_services() doit lever une PermissionError via le registry
    with pytest.raises(PermissionError) as exc:
        lm.propagate_services()

    assert "Impossible d'écraser le service protégé 'db'" in str(exc.value)
    # Vérifier que le service original n'a pas été écrasé dans shared_services
    # (LifecycleManager ne doit pas atteindre la phase d'update s'il y a collision)
    assert shared_services["db"] == "core_db"


@pytest.mark.asyncio
async def test_lifecycle_propagate_services_allowed():
    shared_services = {"db": "core_db"}

    # Instance du plugin qui enregistre un nouveau service non protégé
    plugin_instance = MockPlugin(services={"my_service": "some_value"})

    lm = LifecycleManager(MagicMock(), shared_services)
    lm._instance = plugin_instance
    lm.manifest.name = "good_plugin"

    # L'appel à propagate_services() doit réussir
    lm.propagate_services()

    assert "my_service" in shared_services
    assert shared_services["my_service"] == "some_value"
    assert shared_services["db"] == "core_db"
