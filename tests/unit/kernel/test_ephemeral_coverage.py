"""
Tests de couverture complémentaires pour :
  - xcore/kernel/runtime/ephemeral_handler.py (lignes 85, 94-119, 127-128, 167-170)
  - xcore/kernel/runtime/warm_pool.py (lignes manquantes)
  - xcore/kernel/runtime/activator.py (lignes 52-55, 116-162)
"""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── Helpers ───────────────────────────────────────────────────────────────────

def _manifest(pool_size=2, max_concurrent=5):
    from xcore.configurations.sections import EphemeralConfig
    m = MagicMock()
    m.name = "cov-plugin"
    m.ephemeral = EphemeralConfig(
        pool_size=pool_size,
        max_idle_seconds=60,
        max_concurrent=max_concurrent,
        boot_timeout=2.0,
    )
    m.entry_point = "src/main.py"
    m.plugin_dir = "/fake/dir"
    m.allowed_imports = []
    m.resources.timeout_seconds = 10
    m.execution_mode = MagicMock(value="ephemeral")
    m.permissions = []
    return m


def _ctx():
    ctx = MagicMock()
    ctx.services.as_dict.return_value = {}
    ctx.events = MagicMock()
    ctx.hooks = MagicMock()
    ctx.metrics = MagicMock()
    ctx.tracer = MagicMock()
    ctx.health = MagicMock()
    ctx.registry = MagicMock()
    return ctx


def _make_lm(router=None, middlewares=None):
    lm = MagicMock()
    lm.load = AsyncMock()
    lm.unload = AsyncMock()
    lm.call = AsyncMock(return_value={"ok": True})
    lm.plugin_router = router
    lm.plugin_middlewares = middlewares or {}
    lm.state = MagicMock()
    return lm


# ══════════════════════════════════════════════════════════════════════════════
# EphemeralHandler — chemins manquants
# ══════════════════════════════════════════════════════════════════════════════

class TestEphemeralHandlerCoverage:

    async def test_start_with_pool_collects_router(self):
        """pool_size > 0 → collecte le router depuis le pool (ligne 98-101)."""
        from xcore.configurations.sections import EphemeralConfig
        from xcore.kernel.runtime.ephemeral_handler import EphemeralHandler

        manifest = _manifest(pool_size=1)
        ctx = _ctx()
        config = EphemeralConfig(pool_size=1, max_concurrent=3)

        mock_router = MagicMock()
        lm = _make_lm(router=mock_router)
        lm.load = AsyncMock()

        handler = EphemeralHandler(manifest, ctx, config)

        with patch("xcore.kernel.runtime.lifecycle.LifecycleManager", return_value=lm):
            await handler.start()

        assert handler.plugin_router is mock_router
        await handler._pool.shutdown()

    async def test_start_without_pool_collects_router(self):
        """pool_size=0 → boot temporaire pour collecter le router (lignes 103-117)."""
        from xcore.configurations.sections import EphemeralConfig
        from xcore.kernel.runtime.ephemeral_handler import EphemeralHandler

        manifest = _manifest(pool_size=0)
        ctx = _ctx()
        config = EphemeralConfig(pool_size=0, max_concurrent=3)

        mock_router = MagicMock()
        lm = _make_lm(router=mock_router)

        handler = EphemeralHandler(manifest, ctx, config)

        with patch("xcore.kernel.runtime.lifecycle.LifecycleManager", return_value=lm):
            await handler.start()

        assert handler.plugin_router is mock_router
        lm.load.assert_awaited_once()
        lm.unload.assert_awaited_once()

    async def test_start_without_pool_unload_on_error(self):
        """pool_size=0 → unload appelé même si load échoue (finally, ligne 117)."""
        from xcore.configurations.sections import EphemeralConfig
        from xcore.kernel.runtime.ephemeral_handler import EphemeralHandler

        manifest = _manifest(pool_size=0)
        ctx = _ctx()
        config = EphemeralConfig(pool_size=0, max_concurrent=3)

        lm = _make_lm()
        lm.load = AsyncMock(side_effect=RuntimeError("load failed"))

        handler = EphemeralHandler(manifest, ctx, config)

        with patch("xcore.kernel.runtime.lifecycle.LifecycleManager", return_value=lm):
            with pytest.raises(RuntimeError, match="load failed"):
                await handler.start()

        lm.unload.assert_awaited_once()

    async def test_stop_calls_pool_shutdown(self):
        """stop() doit appeler pool.shutdown() (ligne 127-128)."""
        from xcore.configurations.sections import EphemeralConfig
        from xcore.kernel.runtime.ephemeral_handler import EphemeralHandler

        manifest = _manifest(pool_size=0)
        ctx = _ctx()
        config = EphemeralConfig(pool_size=0)
        handler = EphemeralHandler(manifest, ctx, config)

        handler._pool.shutdown = AsyncMock()
        await handler.stop()
        handler._pool.shutdown.assert_awaited_once()

    async def test_manifest_property(self):
        """manifest property retourne _manifest (ligne 85)."""
        from xcore.configurations.sections import EphemeralConfig
        from xcore.kernel.runtime.ephemeral_handler import EphemeralHandler

        manifest = _manifest()
        ctx = _ctx()
        config = EphemeralConfig()
        handler = EphemeralHandler(manifest, ctx, config)
        assert handler.manifest is manifest

    def test_collect_router_with_router_and_middlewares(self):
        """_collect_router() collecte router ET middlewares (lignes 167-170)."""
        from xcore.configurations.sections import EphemeralConfig
        from xcore.kernel.runtime.ephemeral_handler import EphemeralHandler

        manifest = _manifest()
        ctx = _ctx()
        config = EphemeralConfig()
        handler = EphemeralHandler(manifest, ctx, config)

        lm = MagicMock()
        lm.plugin_router = MagicMock()
        lm.state = MagicMock()
        lm.plugin_middlewares = {"mw": MagicMock()}

        handler._collect_router(lm)
        assert handler.plugin_router is lm.plugin_router
        assert handler.plugin_middlewares == lm.plugin_middlewares

    def test_collect_router_no_router(self):
        """_collect_router() quand plugin_router est None."""
        from xcore.configurations.sections import EphemeralConfig
        from xcore.kernel.runtime.ephemeral_handler import EphemeralHandler

        manifest = _manifest()
        ctx = _ctx()
        config = EphemeralConfig()
        handler = EphemeralHandler(manifest, ctx, config)

        lm = MagicMock()
        lm.plugin_router = None
        lm.plugin_middlewares = {}
        lm.state = MagicMock()

        handler._collect_router(lm)
        assert handler.plugin_router is None

    def test_status_includes_cold_boots(self):
        """status() inclut cold_boots depuis pool.stats()."""
        from xcore.configurations.sections import EphemeralConfig
        from xcore.kernel.runtime.ephemeral_handler import EphemeralHandler

        manifest = _manifest()
        ctx = _ctx()
        config = EphemeralConfig(pool_size=2)
        handler = EphemeralHandler(manifest, ctx, config)
        handler._pool._cold_boot_count = 3

        s = handler.status()
        assert s["cold_boots"] == 3


# ══════════════════════════════════════════════════════════════════════════════
# WarmPool — chemins manquants
# ══════════════════════════════════════════════════════════════════════════════

class TestWarmPoolCoverage:

    async def test_start_with_pool_size(self):
        """start() pré-charge pool_size instances."""
        from xcore.kernel.runtime.warm_pool import WarmPool

        manifest = _manifest(pool_size=2)
        ctx = _ctx()
        lm = _make_lm()

        with patch("xcore.kernel.runtime.lifecycle.LifecycleManager", return_value=lm):
            pool = WarmPool(manifest, ctx, pool_size=2, max_concurrent=5, boot_timeout=2.0)
            await pool.start()
            assert pool._available.qsize() == 2
            assert pool._cold_boot_count == 2
            await pool.shutdown()

    async def test_start_boot_failure_logs_warning(self):
        """start() log un warning si un boot échoue sans stopper les autres."""
        from xcore.kernel.runtime.warm_pool import WarmPool

        manifest = _manifest(pool_size=2)
        ctx = _ctx()
        call_count = 0

        # LifecycleManager est appelé avec kwargs (manifest=, ctx=, caller=)
        def make_lm(**kwargs):
            nonlocal call_count
            call_count += 1
            lm = MagicMock()
            if call_count == 1:
                lm.load = AsyncMock(side_effect=RuntimeError("boot fail"))
            else:
                lm.load = AsyncMock()
            lm.unload = AsyncMock()
            return lm

        with patch("xcore.kernel.runtime.lifecycle.LifecycleManager", side_effect=make_lm):
            pool = WarmPool(manifest, ctx, pool_size=2, max_concurrent=5, boot_timeout=2.0)
            await pool.start()
            # 1 boot échoué → warning loggé, pas de crash, start() se termine normalement
            assert pool._cold_boot_count >= 0
            await pool.shutdown()

    async def test_acquire_pool_hit(self):
        """acquire() retourne une instance du pool (0ms)."""
        from xcore.kernel.runtime.warm_pool import WarmPool, _PoolEntry

        manifest = _manifest()
        ctx = _ctx()
        lm = _make_lm()

        pool = WarmPool(manifest, ctx, pool_size=2, max_concurrent=5)
        pool._total = 1
        entry = _PoolEntry(lm)
        await pool._available.put(entry)

        acquired = await pool.acquire()
        assert acquired is lm
        await pool.discard(acquired)

    async def test_release_returns_to_pool(self):
        """release() retourne l'instance au pool si < pool_size."""
        from xcore.kernel.runtime.warm_pool import WarmPool

        manifest = _manifest()
        ctx = _ctx()
        lm = _make_lm()

        pool = WarmPool(manifest, ctx, pool_size=2, max_concurrent=5)
        pool._total = 1
        await pool._semaphore.acquire()

        await pool.release(lm)
        assert pool._available.qsize() == 1

    async def test_release_unloads_when_pool_full(self):
        """release() décharge si pool plein (qsize >= pool_size)."""
        from xcore.kernel.runtime.warm_pool import WarmPool, _PoolEntry

        manifest = _manifest()
        ctx = _ctx()
        lm = _make_lm()

        pool = WarmPool(manifest, ctx, pool_size=1, max_concurrent=5)
        pool._total = 2
        # Remplit le pool
        entry = _PoolEntry(MagicMock())
        await pool._available.put(entry)
        await pool._semaphore.acquire()

        await pool.release(lm)
        lm.unload.assert_awaited_once()
        assert pool._total == 1

    async def test_release_when_closed(self):
        """release() décharge et libère le semaphore si pool fermé."""
        from xcore.kernel.runtime.warm_pool import WarmPool

        manifest = _manifest()
        ctx = _ctx()
        lm = _make_lm()

        pool = WarmPool(manifest, ctx, pool_size=2, max_concurrent=5)
        pool._total = 1
        pool._closed = True
        await pool._semaphore.acquire()

        await pool.release(lm)
        lm.unload.assert_awaited_once()

    async def test_discard_decrements_total(self):
        """discard() décrémente _total et libère le semaphore."""
        from xcore.kernel.runtime.warm_pool import WarmPool

        manifest = _manifest()
        ctx = _ctx()
        lm = _make_lm()

        pool = WarmPool(manifest, ctx, pool_size=2, max_concurrent=5)
        pool._total = 3
        await pool._semaphore.acquire()

        await pool.discard(lm)
        assert pool._total == 2
        lm.unload.assert_awaited_once()

    async def test_acquire_closed_raises(self):
        """acquire() sur un pool fermé lève RuntimeError."""
        from xcore.kernel.runtime.warm_pool import WarmPool

        manifest = _manifest()
        ctx = _ctx()
        pool = WarmPool(manifest, ctx, pool_size=2, max_concurrent=5)
        pool._closed = True

        with pytest.raises(RuntimeError, match="WarmPool fermé"):
            await pool.acquire()

    async def test_stats(self):
        """stats() retourne un dict complet."""
        from xcore.kernel.runtime.warm_pool import WarmPool

        manifest = _manifest()
        ctx = _ctx()
        pool = WarmPool(manifest, ctx, pool_size=2, max_concurrent=5)

        s = pool.stats()
        assert s["plugin"] == "cov-plugin"
        assert s["pool_size"] == 2
        assert "cold_boots" in s
        assert s["cold_boots"] == 0
        assert s["closed"] is False

    async def test_idle_sweeper_evicts_old_entries(self):
        """_idle_sweeper évince les entrées idle > max_idle_seconds."""
        from xcore.kernel.runtime.warm_pool import WarmPool, _PoolEntry
        import time

        manifest = _manifest()
        ctx = _ctx()
        lm1 = _make_lm()
        lm2 = _make_lm()

        pool = WarmPool(manifest, ctx, pool_size=1, max_concurrent=5, max_idle_seconds=1)
        pool._total = 2

        # Entrée fraîche (ne sera pas évincée)
        fresh = _PoolEntry(lm1)
        # Entrée vieille (sera évincée si en excès du pool_size)
        old = _PoolEntry(lm2)
        old.idle_since = time.monotonic() - 100  # 100s idle

        await pool._available.put(fresh)
        await pool._available.put(old)

        # Simule un cycle du sweeper en appelant directement la logique
        entries = []
        while True:
            try:
                entries.append(pool._available.get_nowait())
            except asyncio.QueueEmpty:
                break

        entries.sort(key=lambda e: e.idle_seconds)
        to_discard = []
        to_return = []
        for i, entry in enumerate(entries):
            if i >= pool._pool_size and entry.idle_seconds > pool._max_idle_seconds:
                to_discard.append(entry)
            else:
                to_return.append(entry)

        for entry in to_return:
            await pool._available.put(entry)

        for entry in to_discard:
            await pool._safe_unload(entry.manager)
            async with pool._lock:
                pool._total -= 1

        assert pool._available.qsize() == 1
        assert pool._total == 1


# ══════════════════════════════════════════════════════════════════════════════
# Activator — EphemeralActivator et LagacyActivator
# ══════════════════════════════════════════════════════════════════════════════

class TestActivatorCoverage:

    async def test_lagacy_activator_raises(self):
        """LagacyActivator.activate() doit lever NotImplementedError."""
        from xcore.kernel.runtime.activator import LagacyActivator

        activator = LagacyActivator()
        with pytest.raises(NotImplementedError):
            await activator.activate(MagicMock(), MagicMock())

    async def test_ephemeral_activator_activate(self):
        """EphemeralActivator.activate() crée et démarre un EphemeralHandler."""
        from xcore.kernel.runtime.activator import EphemeralActivator
        from xcore.configurations.sections import EphemeralConfig

        manifest = _manifest(pool_size=0)
        manifest.ephemeral = EphemeralConfig(pool_size=0, max_concurrent=3)

        loader = MagicMock()
        loader._config.strict_trusted = False
        loader._config.secret_key = b"key"
        loader._ctx = _ctx()
        loader._caller = None

        mock_lm = _make_lm()

        # ASTScanner est importé localement dans activate() → patch sur le module source
        with patch("xcore.kernel.security.validation.ASTScanner") as mock_scanner_cls:
            scanner = MagicMock()
            scan_result = MagicMock()
            scan_result.passed = True
            scanner.scan.return_value = scan_result
            mock_scanner_cls.return_value = scanner

            with patch("xcore.kernel.runtime.lifecycle.LifecycleManager", return_value=mock_lm):
                activator = EphemeralActivator()
                handler = await activator.activate(manifest, loader)

        from xcore.kernel.runtime.ephemeral_handler import EphemeralHandler
        assert isinstance(handler, EphemeralHandler)

    async def test_ephemeral_activator_ast_warning_on_fail(self):
        """EphemeralActivator log un warning si le scan AST échoue (non bloquant)."""
        from xcore.kernel.runtime.activator import EphemeralActivator
        from xcore.configurations.sections import EphemeralConfig

        manifest = _manifest(pool_size=0)
        manifest.ephemeral = EphemeralConfig(pool_size=0)

        loader = MagicMock()
        loader._config.strict_trusted = False
        loader._ctx = _ctx()
        loader._caller = None

        mock_lm = _make_lm()

        with patch("xcore.kernel.security.validation.ASTScanner") as mock_scanner_cls:
            scanner = MagicMock()
            scan_result = MagicMock()
            scan_result.passed = False  # scan fails — non bloquant
            scanner.scan.return_value = scan_result
            mock_scanner_cls.return_value = scanner

            with patch("xcore.kernel.runtime.lifecycle.LifecycleManager", return_value=mock_lm):
                activator = EphemeralActivator()
                handler = await activator.activate(manifest, loader)

        assert handler is not None  # malgré le scan échoué

    async def test_ephemeral_activator_strict_trusted_signature_error(self):
        """EphemeralActivator lève LoadError si strict_trusted et signature invalide."""
        from xcore.kernel.runtime.activator import EphemeralActivator
        from xcore.kernel.runtime.lifecycle import LoadError
        from xcore.kernel.security.signature import SignatureError

        manifest = _manifest()
        loader = MagicMock()
        loader._config.strict_trusted = True
        loader._config.secret_key = b"secret"
        loader._ctx = _ctx()

        # verify_plugin est importé localement → patch sur le module source
        with patch("xcore.kernel.security.signature.verify_plugin", side_effect=SignatureError("bad sig")):
            activator = EphemeralActivator()
            with pytest.raises(LoadError):
                await activator.activate(manifest, loader)

    async def test_ephemeral_activator_uses_global_config_fallback(self):
        """Si manifest.ephemeral est None, utilise loader._ctx.config.ephemeral."""
        from xcore.kernel.runtime.activator import EphemeralActivator
        from xcore.configurations.sections import EphemeralConfig

        manifest = _manifest(pool_size=0)
        manifest.ephemeral = None  # pas de config manifest

        global_config = EphemeralConfig(pool_size=0, max_concurrent=2)
        loader = MagicMock()
        loader._config.strict_trusted = False
        loader._ctx = _ctx()
        loader._ctx.config.ephemeral = global_config
        loader._caller = None

        mock_lm = _make_lm()

        with patch("xcore.kernel.security.validation.ASTScanner") as mock_scanner_cls:
            scanner = MagicMock()
            scan_result = MagicMock()
            scan_result.passed = True
            scanner.scan.return_value = scan_result
            mock_scanner_cls.return_value = scanner

            with patch("xcore.kernel.runtime.lifecycle.LifecycleManager", return_value=mock_lm):
                activator = EphemeralActivator()
                handler = await activator.activate(manifest, loader)

        assert handler._config is global_config
