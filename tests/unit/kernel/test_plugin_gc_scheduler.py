"""
Régression : le ramasse-miette forcé du scheduler doit fonctionner aussi APRÈS
le boot, quand le registre contient les services noyau bruts, et deux plugins
ne doivent pas se marcher dessus dans le registre de jobs global.
"""

import gc
import weakref
from types import SimpleNamespace

import pytest

from xcore.configurations.sections import SchedulerConfig, ServicesConfig
from xcore.kernel.context import KernelContext
from xcore.kernel.events.bus import EventBus
from xcore.kernel.events.hooks import HookManager
from xcore.kernel.observability.health import HealthChecker
from xcore.kernel.runtime.lifecycle import LifecycleManager
from xcore.kernel.tenancy.services import TenantAwareDB
from xcore.registry.index import PluginRegistry
from xcore.services.container import ServiceContainer
from xcore.services.scheduler import service as scheduler_module
from xcore.services.scheduler.service import SchedulerService

PLUGIN_TEMPLATE = """
from xcore.kernel.api.contract import TrustedBase

class Plugin(TrustedBase):
    async def on_load(self):
        self.blob = bytearray(100_000)
{body}

    async def tick(self):
        return len(self.blob)

    async def handle(self, action, payload):
        return {{"status": "ok"}}
"""

VIA_GET_SERVICE = """
        self.get_service("scheduler").add_job(
            self.tick, "interval", job_id="cleanup", seconds=3600
        )
"""


def _manifest(tmp_path, name, body=VIA_GET_SERVICE):
    plugin_dir = tmp_path / name
    (plugin_dir / "src").mkdir(parents=True)
    (plugin_dir / "src" / "main.py").write_text(PLUGIN_TEMPLATE.format(body=body))
    return SimpleNamespace(
        name=name,
        plugin_dir=plugin_dir,
        entry_point="src/main.py",
        resources=SimpleNamespace(timeout_seconds=10),
        env={},
        requires=[],
        extra={},
    )


def _kernel(scheduler, tenancy=None, extra_services=None):
    container = ServiceContainer(ServicesConfig())
    container._raw["scheduler"] = scheduler
    container._raw.update(extra_services or {})
    registry = PluginRegistry()
    ctx = KernelContext(
        config=SimpleNamespace(tenancy=tenancy),
        services=container,
        registry=registry,
        events=EventBus(),
        hooks=HookManager(),
        health=HealthChecker(),
    )
    return ctx, container, registry


def _finish_boot(container, registry):
    for name, svc in container.as_dict().items():
        registry.register_core_service(name, svc)


@pytest.fixture
async def scheduler():
    svc = SchedulerService(SchedulerConfig())
    await svc.init()
    yield svc
    scheduler_module._JOB_REGISTRY.clear()
    await svc.shutdown()


class TestSchedulerReleasedAfterBoot:
    async def test_job_registered_via_get_service_is_released_on_unload(
        self, scheduler, tmp_path
    ):
        ctx, container, registry = _kernel(scheduler)
        lm = LifecycleManager(_manifest(tmp_path, "p"), ctx)
        _finish_boot(container, registry)  # plugin (re)chargé APRÈS le boot

        await lm.load()
        job_id = "p:cleanup"
        assert job_id in scheduler_module._JOB_REGISTRY
        assert scheduler._scheduler.get_job(job_id) is not None
        ref = weakref.ref(lm._instance)

        await lm.unload()
        gc.collect()

        assert job_id not in scheduler_module._JOB_REGISTRY
        assert scheduler._scheduler.get_job(job_id) is None
        assert ref() is None, "l'instance déchargée est encore référencée"

    async def test_reload_after_boot_does_not_accumulate_jobs(
        self, scheduler, tmp_path
    ):
        ctx, container, registry = _kernel(scheduler)
        lm = LifecycleManager(_manifest(tmp_path, "p"), ctx)
        await lm.load()
        _finish_boot(container, registry)

        for _ in range(3):
            await lm.reload()

        assert [j for j in scheduler_module._JOB_REGISTRY if j.startswith("p:")] == [
            "p:cleanup"
        ]
        refs = scheduler_module._JOB_REGISTRY["p:cleanup"].__self__
        assert refs is lm._instance


class TestJobIdsAreNamespacedPerPlugin:
    async def test_two_plugins_with_same_job_name_do_not_collide(
        self, scheduler, tmp_path
    ):
        ctx, container, registry = _kernel(scheduler)
        a = LifecycleManager(_manifest(tmp_path, "a"), ctx)
        b = LifecycleManager(_manifest(tmp_path, "b"), ctx)
        await a.load()
        await b.load()

        assert {"a:cleanup", "b:cleanup"} <= set(scheduler_module._JOB_REGISTRY)
        assert scheduler_module._JOB_REGISTRY["a:cleanup"].__self__ is a._instance
        assert scheduler_module._JOB_REGISTRY["b:cleanup"].__self__ is b._instance

    async def test_unloading_one_plugin_keeps_the_other_plugins_job(
        self, scheduler, tmp_path
    ):
        ctx, container, registry = _kernel(scheduler)
        a = LifecycleManager(_manifest(tmp_path, "a"), ctx)
        b = LifecycleManager(_manifest(tmp_path, "b"), ctx)
        await a.load()
        await b.load()

        await a.unload()

        assert "a:cleanup" not in scheduler_module._JOB_REGISTRY
        assert "b:cleanup" in scheduler_module._JOB_REGISTRY
        assert scheduler._scheduler.get_job("b:cleanup") is not None

    async def test_plugin_keeps_using_its_own_unprefixed_ids(self, scheduler, tmp_path):
        body = """
        sch = self.get_service("scheduler")
        sch.add_job(self.tick, "interval", job_id="cleanup", seconds=3600)
        sch.add_job(self.tick, "interval", job_id="other", seconds=3600)
        sch.remove_job("cleanup")
"""
        ctx, _, _ = _kernel(scheduler)
        lm = LifecycleManager(_manifest(tmp_path, "p", body), ctx)
        await lm.load()

        assert "p:cleanup" not in scheduler_module._JOB_REGISTRY
        assert "p:other" in scheduler_module._JOB_REGISTRY

    async def test_interval_decorator_is_namespaced_and_released(
        self, scheduler, tmp_path
    ):
        body = """
        @self.get_service("scheduler").interval(seconds=3600)
        async def heartbeat():
            return 1
"""
        ctx, _, _ = _kernel(scheduler)
        lm = LifecycleManager(_manifest(tmp_path, "p", body), ctx)
        await lm.load()
        assert "p:heartbeat" in scheduler_module._JOB_REGISTRY

        await lm.unload()
        assert "p:heartbeat" not in scheduler_module._JOB_REGISTRY


class TestCoreServicesKeepTheirPerPluginWrapping:
    async def test_get_service_after_boot_is_still_tenant_aware(
        self, scheduler, tmp_path
    ):
        """Après le boot, get_service('db') rendait le db brut (registre)."""
        body = """
        self.db = self.get_service("db")
"""
        tenancy = SimpleNamespace(
            enabled=True,
            isolate_db=True,
            isolate_cache=False,
            isolate_scheduler=False,
        )
        raw_db = object()
        ctx, container, registry = _kernel(
            scheduler, tenancy=tenancy, extra_services={"db": raw_db}
        )
        lm = LifecycleManager(_manifest(tmp_path, "p", body), ctx)
        _finish_boot(container, registry)

        await lm.load()

        assert isinstance(lm._instance.db, TenantAwareDB)
        assert lm._instance.db is not raw_db
