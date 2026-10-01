"""
Après un unload/reload, une collecte du GC est forcée (différée, regroupée) et
les instances qui survivent sont signalées. Sans ça, un plugin déchargé — qui vit
dans des cycles de références — restait en mémoire jusqu'à la prochaine collecte
complète de Python, qui peut ne jamais venir sur un gros tas.
"""

import asyncio
import gc
import logging
import weakref
from types import SimpleNamespace

import pytest

from xcore.configurations.sections import ServicesConfig
from xcore.kernel.context import KernelContext
from xcore.kernel.events.bus import EventBus
from xcore.kernel.events.hooks import HookManager
from xcore.kernel.observability.health import HealthChecker
from xcore.kernel.runtime import lifecycle as lifecycle_module
from xcore.kernel.runtime.lifecycle import LifecycleManager
from xcore.registry.index import PluginRegistry
from xcore.services.container import ServiceContainer

PLUGIN_SRC = """
from xcore.kernel.api.contract import TrustedBase

class Plugin(TrustedBase):
    async def on_load(self):
        self.me = self                      # cycle : le comptage de références seul ne libère pas
        self.blob = bytearray(100_000)

    async def handle(self, action, payload):
        return {"status": "ok"}
"""


@pytest.fixture(autouse=True)
def fast_delay(monkeypatch):
    monkeypatch.setattr(lifecycle_module, "_GC_DELAY_S", 0.02)
    watcher = lifecycle_module._release_watcher
    watcher._pending, watcher._handle, watcher._loop = [], None, None
    yield
    watcher._pending, watcher._handle, watcher._loop = [], None, None


def _manager(tmp_path, name="p", gc_after_unload=True, pooled=False):
    plugin_dir = tmp_path / name
    (plugin_dir / "src").mkdir(parents=True)
    (plugin_dir / "src" / "main.py").write_text(PLUGIN_SRC)
    manifest = SimpleNamespace(
        name=name,
        plugin_dir=plugin_dir,
        entry_point="src/main.py",
        resources=SimpleNamespace(timeout_seconds=10),
        env={},
        requires=[],
        extra={},
    )
    ctx = KernelContext(
        config=SimpleNamespace(tenancy=None, gc_after_unload=gc_after_unload),
        services=ServiceContainer(ServicesConfig()),
        registry=PluginRegistry(),
        events=EventBus(),
        hooks=HookManager(),
        health=HealthChecker(),
    )
    return LifecycleManager(manifest, ctx, pooled=pooled)


async def test_dead_plugin_generation_is_collected_without_manual_gc(tmp_path):
    gc.disable()  # le GC automatique ne doit pas être ce qui libère l'instance
    try:
        lm = _manager(tmp_path)
        await lm.load()
        ref = weakref.ref(lm._instance)

        await lm.unload()
        assert ref() is not None  # le cycle la retient jusqu'à la collecte différée

        await asyncio.sleep(0.1)
        assert ref() is None
    finally:
        gc.enable()


async def test_reload_collects_the_previous_generation(tmp_path):
    gc.disable()
    try:
        lm = _manager(tmp_path)
        await lm.load()
        old = weakref.ref(lm._instance)

        await lm.reload()
        await asyncio.sleep(0.1)

        assert old() is None
        assert lm._instance is not None
    finally:
        gc.enable()


async def test_instance_still_referenced_after_unload_is_reported(tmp_path, caplog):
    lm = _manager(tmp_path)
    await lm.load()
    leak = lm._instance  # quelque chose la retient encore (tâche brute, callback…)

    with caplog.at_level(logging.WARNING):
        await lm.unload()
        await asyncio.sleep(0.1)

    messages = [r.getMessage() for r in caplog.records]
    assert any("still referenced after unload" in m for m in messages), messages
    assert leak is not None


async def test_clean_unload_does_not_warn(tmp_path, caplog):
    lm = _manager(tmp_path)
    await lm.load()

    with caplog.at_level(logging.WARNING):
        await lm.unload()
        await asyncio.sleep(0.1)

    assert not [r for r in caplog.records if "still referenced" in r.getMessage()]


async def test_unloads_within_the_window_share_one_collection(tmp_path, monkeypatch):
    calls = []
    real_collect = gc.collect
    monkeypatch.setattr(
        lifecycle_module.gc, "collect", lambda *a: calls.append(1) or real_collect(*a)
    )
    managers = [_manager(tmp_path, f"p{i}") for i in range(3)]
    for lm in managers:
        await lm.load()

    for lm in managers:
        await lm.unload()
    await asyncio.sleep(0.1)

    assert len(calls) == 1


async def test_disabled_by_config(tmp_path):
    lm = _manager(tmp_path, gc_after_unload=False)
    await lm.load()

    await lm.unload()

    assert lifecycle_module._release_watcher._pending == []
    assert lifecycle_module._release_watcher._handle is None


async def test_pooled_ephemeral_instances_are_not_watched(tmp_path):
    lm = _manager(tmp_path, pooled=True)
    await lm.load()

    await lm.unload()

    assert lifecycle_module._release_watcher._pending == []


def test_gc_after_unload_defaults_to_enabled():
    from xcore.configurations.loader import ConfigLoader
    from xcore.configurations.sections import PluginConfig

    assert PluginConfig().gc_after_unload is True
    assert ConfigLoader._parse_plugins({}).gc_after_unload is True
    assert (
        ConfigLoader._parse_plugins({"gc_after_unload": False}).gc_after_unload is False
    )
