"""
Régression : un plugin qui EXPORTE un service (dans `self._services`) doit rester
rechargeable après le boot.

`PluginSupervisor.boot()` enregistrait, à son étape 5, tout le contenu du
ServiceContainer comme service noyau protégé — y compris les services que les
plugins venaient d'y propager. Le propriétaire devenait « kernel » et le reload
du plugin qui l'exportait échouait avec « Impossible d'écraser le service
protégé ».
"""

from types import SimpleNamespace

import pytest

from xcore.configurations.sections import ServicesConfig
from xcore.kernel.context import KernelContext
from xcore.kernel.events.bus import EventBus
from xcore.kernel.events.hooks import HookManager
from xcore.kernel.observability.health import HealthChecker
from xcore.kernel.runtime.supervisor import PluginSupervisor
from xcore.registry.index import PluginRegistry
from xcore.services.container import ServiceContainer

MANIFEST = """
name: exporter
version: 1.0.0
execution_mode: trusted
entry_point: src/main.py
"""

SRC = """
from xcore.kernel.api.contract import TrustedBase

class Plugin(TrustedBase):
    async def on_load(self):
        self._services["exported_svc"] = self

    async def handle(self, action, payload):
        return {"status": "ok"}
"""


@pytest.fixture
async def booted(tmp_path):
    plugins = tmp_path / "plugins"
    (plugins / "exporter" / "src").mkdir(parents=True)
    (plugins / "exporter" / "plugin.yaml").write_text(MANIFEST)
    (plugins / "exporter" / "src" / "main.py").write_text(SRC)

    container = ServiceContainer(ServicesConfig())
    container._raw["cache"] = object()  # un service noyau
    registry = PluginRegistry()
    ctx = KernelContext(
        config=SimpleNamespace(
            directory=str(plugins),
            tenancy=None,
            strict_trusted=False,
            secret_key=b"test",
        ),
        services=container,
        registry=registry,
        events=EventBus(),
        hooks=HookManager(),
        health=HealthChecker(),
    )
    supervisor = PluginSupervisor(ctx)
    await supervisor.boot()
    yield SimpleNamespace(supervisor=supervisor, container=container, registry=registry)
    await supervisor.shutdown()


async def test_plugin_is_loaded_and_its_export_stays_owned_by_the_plugin(booted):
    assert "exporter" in booted.supervisor.list_plugins()
    exported = [
        s for s in booted.registry.list_services() if s["name"] == "exported_svc"
    ]
    assert exported and exported[0]["plugin"] == "exporter"
    assert booted.registry.is_core_service("cache") is True
    assert booted.registry.is_core_service("exported_svc") is False


async def test_plugin_exporting_a_service_can_be_reloaded_after_boot(booted):
    await booted.supervisor.reload("exporter")
    await booted.supervisor.reload("exporter")  # le 2e reload cassait aussi

    handler = booted.supervisor._loader.get("exporter")
    assert handler.state.value == "ready"
    assert booted.container.as_dict()["exported_svc"] is handler._instance
