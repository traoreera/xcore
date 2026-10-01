"""
Régression : ce qu'un plugin laisse derrière lui au unload / reload — router et
middlewares, services exportés dans le container partagé, tâches de fond.
"""

import asyncio
import gc
import weakref
from types import SimpleNamespace

from xcore.configurations.sections import ServicesConfig
from xcore.kernel.context import KernelContext
from xcore.kernel.events.bus import EventBus
from xcore.kernel.events.hooks import HookManager
from xcore.kernel.observability.health import HealthChecker
from xcore.kernel.runtime.lifecycle import LifecycleManager
from xcore.registry.index import PluginRegistry
from xcore.services.container import ServiceContainer

HEADER = """
import asyncio
from xcore.kernel.api.contract import TrustedBase
"""


def _plugin(body: str) -> str:
    return (
        HEADER
        + "\nclass Plugin(TrustedBase):\n"
        + body
        + "\n    async def handle(self, action, payload):\n"
        + '        return {"status": "ok"}\n'
    )


def _manifest(tmp_path, name="p"):
    plugin_dir = tmp_path / name
    (plugin_dir / "src").mkdir(parents=True)
    return SimpleNamespace(
        name=name,
        plugin_dir=plugin_dir,
        entry_point="src/main.py",
        resources=SimpleNamespace(timeout_seconds=10),
        env={},
        requires=[],
        extra={},
    )


def _write(manifest, body):
    (manifest.plugin_dir / "src" / "main.py").write_text(_plugin(body))


def _manager(manifest):
    container = ServiceContainer(ServicesConfig())
    ctx = KernelContext(
        config=SimpleNamespace(tenancy=None),
        services=container,
        registry=PluginRegistry(),
        events=EventBus(),
        hooks=HookManager(),
        health=HealthChecker(),
    )
    return LifecycleManager(manifest, ctx), container


ROUTER_V1 = """
    def get_router(self):
        return object()

    def add_state(self):
        return {"mw_v1": 1}
"""

NO_ROUTER_V2 = """
    def add_state(self):
        return {"mw_v2": 2}
"""


class TestRouterAndMiddlewares:
    async def test_unload_clears_router_and_middlewares(self, tmp_path):
        manifest = _manifest(tmp_path)
        _write(manifest, ROUTER_V1)
        lm, _ = _manager(manifest)
        await lm.load()
        assert lm.plugin_router is not None
        assert lm.plugin_middlewares == {"mw_v1": 1}

        await lm.unload()

        assert lm.plugin_router is None
        assert lm.plugin_middlewares == {}

    async def test_reload_drops_router_the_new_code_no_longer_exposes(self, tmp_path):
        manifest = _manifest(tmp_path)
        _write(manifest, ROUTER_V1)
        lm, _ = _manager(manifest)
        await lm.load()

        _write(manifest, NO_ROUTER_V2)
        await lm.reload()

        assert lm.plugin_router is None

    async def test_reload_replaces_middlewares_instead_of_merging(self, tmp_path):
        manifest = _manifest(tmp_path)
        _write(manifest, ROUTER_V1)
        lm, _ = _manager(manifest)
        await lm.load()

        _write(manifest, NO_ROUTER_V2)
        await lm.reload()

        assert lm.plugin_middlewares == {"mw_v2": 2}


EXPORTS = """
    async def on_load(self):
        self.blob = bytearray(100_000)
        self._services["probe_svc"] = self
"""


class TestExportedServices:
    async def test_unload_removes_exported_service_from_shared_container(
        self, tmp_path
    ):
        manifest = _manifest(tmp_path)
        _write(manifest, EXPORTS)
        lm, container = _manager(manifest)
        await lm.load()
        assert "probe_svc" in container.as_dict()
        ref = weakref.ref(lm._instance)

        await lm.unload()
        gc.collect()

        assert "probe_svc" not in container.as_dict()
        assert ref() is None, "le plugin déchargé est encore référencé"

    async def test_reload_swaps_in_the_new_instance(self, tmp_path):
        manifest = _manifest(tmp_path)
        _write(manifest, EXPORTS)
        lm, container = _manager(manifest)
        await lm.load()
        first = container.as_dict()["probe_svc"]

        await lm.reload()

        assert container.as_dict()["probe_svc"] is lm._instance
        assert container.as_dict()["probe_svc"] is not first

    async def test_unload_keeps_a_service_another_plugin_took_over(self, tmp_path):
        manifest = _manifest(tmp_path)
        _write(manifest, EXPORTS)
        lm, container = _manager(manifest)
        await lm.load()
        takeover = object()
        container.as_dict()["probe_svc"] = takeover

        await lm.unload()

        assert container.as_dict()["probe_svc"] is takeover


SPAWNING = """
    async def on_load(self):
        self.cleaned = []
        self.ctx.spawn_task(self._worker(), name="worker")

    async def _worker(self):
        try:
            await asyncio.sleep(3600)
        finally:
            await asyncio.sleep(0)       # nettoyage asynchrone du plugin
            self.cleaned.append("worker")
"""


class TestSpawnedTasks:
    async def test_unload_waits_for_cancelled_tasks_to_finish_their_cleanup(
        self, tmp_path
    ):
        manifest = _manifest(tmp_path)
        _write(manifest, SPAWNING)
        lm, _ = _manager(manifest)
        await lm.load()
        await asyncio.sleep(0)  # laisse la tâche démarrer
        instance = lm._instance

        await lm.unload()

        # le `finally` de la tâche s'est exécuté AVANT le retour de unload()
        assert instance.cleaned == ["worker"]

    async def test_finished_tasks_are_dropped_from_the_tracking_list(self, tmp_path):
        manifest = _manifest(tmp_path)
        _write(
            manifest,
            """
    async def on_load(self):
        async def short():
            return 1
        for _ in range(5):
            self.ctx.spawn_task(short())
""",
        )
        lm, _ = _manager(manifest)
        await lm.load()
        assert len(lm._spawned_tasks) == 5

        await asyncio.sleep(0.01)

        assert lm._spawned_tasks == []

    async def test_task_that_ignores_cancellation_does_not_block_unload(self, tmp_path):
        manifest = _manifest(tmp_path)
        _write(
            manifest,
            """
    async def on_load(self):
        self.stop = False
        self.ctx.spawn_task(self._stubborn(), name="stubborn")

    async def _stubborn(self):
        while not self.stop:
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                pass
""",
        )
        lm, _ = _manager(manifest)
        lm._TASK_CANCEL_TIMEOUT_S = 0.05
        await lm.load()
        await asyncio.sleep(0)
        instance = lm._instance
        stubborn = next(t for t in asyncio.all_tasks() if t.get_name() == "stubborn")

        try:
            await asyncio.wait_for(lm.unload(), timeout=2)
            assert lm._instance is None
        finally:  # laisse la tâche récalcitrante se terminer pour fermer le loop
            instance.stop = True
            stubborn.cancel()
            await asyncio.wait([stubborn], timeout=1)

    async def test_unload_from_inside_a_spawned_task_does_not_cancel_itself(
        self, tmp_path
    ):
        manifest = _manifest(tmp_path)
        _write(
            manifest,
            """
    async def on_load(self):
        self.done = asyncio.Event()
""",
        )
        lm, _ = _manager(manifest)
        await lm.load()

        async def unload_from_task():
            lm._spawned_tasks.append(asyncio.current_task())
            await lm.unload()

        await asyncio.create_task(unload_from_task())

        assert lm._instance is None
