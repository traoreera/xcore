"""
Régression : reload / load de plugins Trusted APRÈS le boot, avec un vrai
PluginRegistry (services noyau protégés) et un vrai ServiceContainer.

Avant le correctif, le 1er reload d'un plugin écrivait son proxy de
ramasse-miette dans le dict partagé du ServiceContainer à la place du vrai
scheduler ; le reload/load suivant de n'importe quel plugin échouait alors avec
« Impossible d'écraser le service protégé 'scheduler' » et le plugin restait
bloqué en FAILED (unload refusé).
"""

from types import SimpleNamespace

import pytest

from xcore.configurations.sections import SchedulerConfig, ServicesConfig
from xcore.kernel.context import KernelContext
from xcore.kernel.events.bus import EventBus
from xcore.kernel.events.hooks import HookManager
from xcore.kernel.observability.health import HealthChecker
from xcore.kernel.runtime.lifecycle import LifecycleManager, LoadError
from xcore.kernel.runtime.state_machine import PluginState
from xcore.registry.index import PluginRegistry
from xcore.services.container import ServiceContainer
from xcore.services.scheduler import service as scheduler_module
from xcore.services.scheduler.service import SchedulerService

PLUGIN_SRC = """
from xcore.kernel.api.contract import TrustedBase

class Plugin(TrustedBase):
    async def handle(self, action, payload):
        return {"status": "ok"}
"""


def _manifest(tmp_path, name):
    plugin_dir = tmp_path / name
    (plugin_dir / "src").mkdir(parents=True)
    (plugin_dir / "src" / "main.py").write_text(PLUGIN_SRC)
    return SimpleNamespace(
        name=name,
        plugin_dir=plugin_dir,
        entry_point="src/main.py",
        resources=SimpleNamespace(timeout_seconds=10),
        env={},
        requires=[],
        extra={},
    )


@pytest.fixture
async def booted_kernel():
    """Noyau « après boot » : scheduler réel + services noyau protégés."""
    scheduler = SchedulerService(SchedulerConfig())
    await scheduler.init()
    container = ServiceContainer(ServicesConfig())
    container._raw["scheduler"] = scheduler
    registry = PluginRegistry()
    ctx = KernelContext(
        config=SimpleNamespace(tenancy=SimpleNamespace(enabled=False)),
        services=container,
        registry=registry,
        events=EventBus(),
        hooks=HookManager(),
        health=HealthChecker(),
    )
    yield SimpleNamespace(
        ctx=ctx, container=container, registry=registry, scheduler=scheduler
    )
    scheduler_module._JOB_REGISTRY.clear()
    await scheduler.shutdown()


def _finish_boot(kernel):
    """Reproduit PluginSupervisor.boot() étape 5 : register_core_service()."""
    for name, svc in kernel.container.as_dict().items():
        kernel.registry.register_core_service(name, svc)


class TestReloadAfterBoot:
    async def test_reload_twice_succeeds(self, booted_kernel, tmp_path):
        lm = LifecycleManager(_manifest(tmp_path, "a"), booted_kernel.ctx)
        await lm.load()
        _finish_boot(booted_kernel)

        for _ in range(3):
            await lm.reload()
            assert lm.state == PluginState.READY

    async def test_reload_keeps_real_core_services_in_shared_container(
        self, booted_kernel, tmp_path
    ):
        lm = LifecycleManager(_manifest(tmp_path, "a"), booted_kernel.ctx)
        await lm.load()
        _finish_boot(booted_kernel)

        for _ in range(3):
            await lm.reload()
            assert (
                booted_kernel.container.as_dict()["scheduler"]
                is booted_kernel.scheduler
            )

    async def test_reload_of_one_plugin_does_not_break_the_others(
        self, booted_kernel, tmp_path
    ):
        a = LifecycleManager(_manifest(tmp_path, "a"), booted_kernel.ctx)
        b = LifecycleManager(_manifest(tmp_path, "b"), booted_kernel.ctx)
        await a.load()
        await b.load()
        _finish_boot(booted_kernel)

        await a.reload()
        await b.reload()
        await a.reload()

        # hot-load d'un plugin neuf après des reloads
        c = LifecycleManager(_manifest(tmp_path, "c"), booted_kernel.ctx)
        await c.load()

        assert [m.state for m in (a, b, c)] == [PluginState.READY] * 3

    async def test_plugin_exported_service_is_still_propagated(
        self, booted_kernel, tmp_path
    ):
        """Seuls les services injectés sont ignorés : un export du plugin passe."""
        manifest = _manifest(tmp_path, "exporter")
        (manifest.plugin_dir / "src" / "main.py").write_text(
            PLUGIN_SRC.replace(
                "    async def handle",
                "    async def on_load(self):\n"
                "        self._services['exported_svc'] = 'v1'\n\n"
                "    async def handle",
            )
        )
        lm = LifecycleManager(manifest, booted_kernel.ctx)
        await lm.load()

        assert booted_kernel.container.as_dict()["exported_svc"] == "v1"
        assert booted_kernel.container.as_dict()["scheduler"] is booted_kernel.scheduler

    async def test_override_of_core_service_is_still_rejected(
        self, booted_kernel, tmp_path
    ):
        """Un plugin qui remplace un service noyau par un AUTRE objet est bloqué."""
        manifest = _manifest(tmp_path, "evil")
        (manifest.plugin_dir / "src" / "main.py").write_text(
            PLUGIN_SRC.replace(
                "    async def handle",
                "    async def on_load(self):\n"
                "        self._services['scheduler'] = object()\n\n"
                "    async def handle",
            )
        )
        lm = LifecycleManager(manifest, booted_kernel.ctx)
        await lm.load()  # 1er boot : le registre ne protège pas encore le noyau
        _finish_boot(booted_kernel)

        with pytest.raises(LoadError, match="protégé"):
            await lm.reload()


class TestFailedPluginIsRecoverable:
    async def test_failed_reload_releases_what_the_plugin_registered(
        self, booted_kernel, tmp_path
    ):
        manifest = _manifest(tmp_path, "leaky")
        (manifest.plugin_dir / "src" / "main.py").write_text(
            PLUGIN_SRC.replace(
                "    async def handle",
                "    async def on_load(self):\n"
                "        self.ctx.services['scheduler'].add_job(\n"
                "            self.handle, 'interval', job_id='leaky_tick', seconds=3600)\n"
                "        raise RuntimeError('boom')\n\n"
                "    async def handle",
            )
        )
        lm = LifecycleManager(manifest, booted_kernel.ctx)
        with pytest.raises(LoadError):
            await lm.load()

        assert lm.state == PluginState.FAILED
        assert "leaky_tick" not in scheduler_module._JOB_REGISTRY
        assert booted_kernel.scheduler._scheduler.get_job("leaky_tick") is None

    async def test_unload_is_allowed_from_failed(self, booted_kernel, tmp_path):
        lm = LifecycleManager(_manifest(tmp_path, "a"), booted_kernel.ctx)
        await lm.load()
        lm._sm.force(PluginState.FAILED)

        await lm.unload()

        assert lm.state == PluginState.UNLOADED
        assert lm._instance is None

    async def test_reload_is_allowed_from_failed(self, booted_kernel, tmp_path):
        lm = LifecycleManager(_manifest(tmp_path, "a"), booted_kernel.ctx)
        await lm.load()
        lm._sm.force(PluginState.FAILED)

        await lm.reload()

        assert lm.state == PluginState.READY
