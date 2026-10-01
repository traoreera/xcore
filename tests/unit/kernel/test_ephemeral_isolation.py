"""
Régression : plusieurs instances d'un même plugin Ephemeral coexistent (warm
pool, appels concurrents). Avant le correctif elles partageaient le même nom de
module dans `sys.modules` et chaque unload faisait `registry.unregister(plugin)` :
décharger UNE instance cassait les imports paresseux des instances sœurs
(`ModuleNotFoundError: No module named 'xcore_plugin_<nom>'`) et retirait du
registre un plugin pourtant toujours actif.
"""

import sys
from types import SimpleNamespace

from xcore.configurations.sections import EphemeralConfig, ServicesConfig
from xcore.kernel.context import KernelContext
from xcore.kernel.events.bus import EventBus
from xcore.kernel.events.hooks import HookManager
from xcore.kernel.observability.health import HealthChecker
from xcore.kernel.runtime.ephemeral_handler import EphemeralHandler
from xcore.kernel.runtime.lifecycle import LifecycleManager
from xcore.kernel.runtime.warm_pool import WarmPool
from xcore.registry.index import PluginRegistry
from xcore.services.container import ServiceContainer

PLUGIN_SRC = """
from xcore.kernel.api.contract import TrustedBase

class Plugin(TrustedBase):
    async def handle(self, action, payload):
        from . import helper          # import paresseux relatif
        return {"status": "ok", "v": helper.VALUE}
"""


def _setup(tmp_path):
    plugin_dir = tmp_path / "eph"
    (plugin_dir / "src").mkdir(parents=True)
    (plugin_dir / "src" / "main.py").write_text(PLUGIN_SRC)
    (plugin_dir / "src" / "helper.py").write_text("VALUE = 42\n")
    manifest = SimpleNamespace(
        name="eph",
        plugin_dir=plugin_dir,
        entry_point="src/main.py",
        resources=SimpleNamespace(timeout_seconds=10),
        env={},
        requires=[],
        extra={},
    )
    registry = PluginRegistry()
    ctx = KernelContext(
        config=SimpleNamespace(tenancy=None),
        services=ServiceContainer(ServicesConfig()),
        registry=registry,
        events=EventBus(),
        hooks=HookManager(),
        health=HealthChecker(),
    )
    return manifest, ctx, registry


class TestPooledLifecycleManagers:
    async def test_unloading_one_instance_does_not_break_its_sibling(self, tmp_path):
        manifest, ctx, _ = _setup(tmp_path)
        a = LifecycleManager(manifest, ctx, pooled=True)
        b = LifecycleManager(manifest, ctx, pooled=True)
        await a.load()
        await b.load()

        await a.unload()

        assert await b.call("x", {}) == {"status": "ok", "v": 42}
        await b.unload()

    async def test_unloading_a_pooled_instance_keeps_the_registry_entry(self, tmp_path):
        manifest, ctx, registry = _setup(tmp_path)
        registry.register("eph", object())
        lm = LifecycleManager(manifest, ctx, pooled=True)
        await lm.load()

        await lm.unload()

        assert registry.has("eph")

    async def test_pooled_instances_get_distinct_module_namespaces(self, tmp_path):
        manifest, ctx, _ = _setup(tmp_path)
        a = LifecycleManager(manifest, ctx, pooled=True)
        b = LifecycleManager(manifest, ctx, pooled=True)
        persistent = LifecycleManager(manifest, ctx)

        assert len({a._module_name, b._module_name, persistent._module_name}) == 3
        assert persistent._module_name == "xcore_plugin_eph"

    async def test_unload_only_purges_its_own_modules(self, tmp_path):
        manifest, ctx, _ = _setup(tmp_path)
        a = LifecycleManager(manifest, ctx, pooled=True)
        b = LifecycleManager(manifest, ctx, pooled=True)
        await a.load()
        await b.load()

        await a.unload()

        assert not [m for m in sys.modules if m.startswith(a._module_name)]
        assert f"{b._module_name}.main" in sys.modules
        await b.unload()

    async def test_non_pooled_unload_still_unregisters_the_plugin(self, tmp_path):
        manifest, ctx, registry = _setup(tmp_path)
        registry.register("eph", object())
        lm = LifecycleManager(manifest, ctx)
        await lm.load()

        await lm.unload()

        assert not registry.has("eph")


class TestWarmPoolInstances:
    async def test_discarding_a_pool_instance_keeps_the_other_ones_working(
        self, tmp_path
    ):
        manifest, ctx, _ = _setup(tmp_path)
        pool = WarmPool(manifest=manifest, ctx=ctx, pool_size=2)
        await pool.start()
        try:
            first = await pool.acquire()
            second = await pool.acquire()
            assert first._module_name != second._module_name

            await pool.discard(first)

            assert await second.call("x", {}) == {"status": "ok", "v": 42}
            await pool.release(second)
        finally:
            await pool.shutdown()


class TestEphemeralHandlerRegistry:
    async def test_stop_unregisters_the_plugin_from_the_registry(self, tmp_path):
        manifest, ctx, registry = _setup(tmp_path)
        registry.register("eph", object())
        handler = EphemeralHandler(
            manifest=manifest, ctx=ctx, config=EphemeralConfig(pool_size=1)
        )
        await handler.start()
        assert registry.has("eph")  # démarrer / servir ne la désinscrit pas
        assert (await handler.call("x", {}))["v"] == 42
        assert registry.has("eph")

        await handler.stop()

        assert not registry.has("eph")
