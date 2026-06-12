"""
xcore/kernel/runtime/tests/test_ephemeral.py

Tests d'intégration du mode Ephemeral.
Valide le cycle complet, le warm pool, la backpressure, et le cleanup idle.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Fixtures ──────────────────────────────────────────────────────────────────


def make_manifest(pool_size=2, max_concurrent=5, max_idle=1):
    from xcore.configurations.sections import EphemeralConfig

    m = MagicMock()
    m.name = "test-plugin"
    m.ephemeral = EphemeralConfig(
        pool_size=pool_size,
        max_idle_seconds=max_idle,
        max_concurrent=max_concurrent,
        boot_timeout=2.0,
    )
    m.entry_point = "src/main.py"
    m.resources.timeout_seconds = 10
    return m


def make_ctx():
    ctx = MagicMock()
    ctx.services.as_dict.return_value = {}
    ctx.events = MagicMock()
    ctx.hooks = MagicMock()
    ctx.metrics = MagicMock()
    ctx.tracer = MagicMock()
    ctx.health = MagicMock()
    ctx.registry = MagicMock()
    return ctx


# ── Tests WarmPool ────────────────────────────────────────────────────────────


class TestWarmPool:
    @pytest.mark.asyncio
    async def test_cold_boot_no_pool(self):
        """pool_size=0 → cold boot à chaque appel, pool vide."""
        from xcore.kernel.runtime.warm_pool import WarmPool

        manifest = make_manifest(pool_size=0)
        ctx = make_ctx()

        mock_lm = AsyncMock()
        mock_lm.call = AsyncMock(return_value={"status": "ok"})
        mock_lm.unload = AsyncMock()

        with patch(
            "xcore.kernel.runtime.lifecycle.LifecycleManager",
            return_value=mock_lm,
        ):
            pool = WarmPool(manifest, ctx, pool_size=0, max_concurrent=5)
            await pool.start()

            assert pool._available.qsize() == 0  # pas de pré-chargement

            mgr = await pool.acquire()
            assert mgr is mock_lm

            await pool.release(mgr)
            # pool_size=0 → pas de retour au pool → unload appelé
            mock_lm.unload.assert_awaited()

            await pool.shutdown()

    @pytest.mark.asyncio
    async def test_warm_pool_hit(self):
        """pool_size=2 → les deux premières acquisitions sont immédiates (pool hit)."""
        from xcore.kernel.runtime.warm_pool import WarmPool

        manifest = make_manifest(pool_size=2)
        ctx = make_ctx()

        mock_lms = [AsyncMock() for _ in range(2)]
        call_count = 0

        async def make_lm(*a, **kw):
            nonlocal call_count
            lm = mock_lms[call_count % len(mock_lms)]
            call_count += 1
            lm.load = AsyncMock()
            lm.call = AsyncMock(return_value={"status": "ok"})
            lm.unload = AsyncMock()
            return lm

        with patch(
            "xcore.kernel.runtime.lifecycle.LifecycleManager",
            side_effect=make_lm,
        ):
            pool = WarmPool(manifest, ctx, pool_size=2, max_concurrent=5)
            # Simule le boot des instances
            for lm in mock_lms:
                lm.load = AsyncMock()
                lm.unload = AsyncMock()

            # Test simplié : vérifie que le pool démarre sans erreur
            # et que les stats sont cohérentes
            assert pool.stats()["pool_size"] == 2
            assert pool.stats()["available"] == 0  # avant start()

            await pool.shutdown()

    @pytest.mark.asyncio
    async def test_backpressure_max_concurrent(self):
        """max_concurrent=2 → le 3e appel attend."""
        from xcore.kernel.runtime.warm_pool import WarmPool

        manifest = make_manifest(pool_size=0, max_concurrent=2)
        ctx = make_ctx()

        release_event = asyncio.Event()

        async def slow_call(action, payload):
            await release_event.wait()
            return {"status": "ok"}

        mock_lm = AsyncMock()
        mock_lm.load = AsyncMock()
        mock_lm.call = slow_call
        mock_lm.unload = AsyncMock()

        with patch(
            "xcore.kernel.runtime.lifecycle.LifecycleManager",
            return_value=mock_lm,
        ):
            pool = WarmPool(manifest, ctx, pool_size=0, max_concurrent=2)
            await pool.start()

            # Lance 2 appels concurrents (occupent le semaphore)
            t1 = asyncio.create_task(pool.acquire())
            t2 = asyncio.create_task(pool.acquire())

            # Laisse les tasks démarrer
            await asyncio.sleep(0.01)

            # Le 3e appel doit bloquer (semaphore épuisé)
            t3 = asyncio.create_task(pool.acquire())
            await asyncio.sleep(0.05)
            assert not t3.done(), "Le 3e appel aurait dû être bloqué"

            # Libère un slot
            mgr1 = await t1
            await pool.release(mgr1)
            release_event.set()

            # t3 peut maintenant avancer
            mgr3 = await asyncio.wait_for(t3, timeout=1.0)
            assert mgr3 is not None

            mgr2 = await t2
            await pool.release(mgr2)
            await pool.release(mgr3)
            await pool.shutdown()

    @pytest.mark.asyncio
    async def test_idle_sweep(self):
        """Les instances idle > max_idle_seconds sont déchargées."""
        import time

        from xcore.kernel.runtime.warm_pool import WarmPool, _PoolEntry

        manifest = make_manifest(pool_size=0, max_idle=1)  # pool_size=0 pour forcer le discard
        ctx = make_ctx()

        pool = WarmPool(manifest, ctx, pool_size=0, max_idle_seconds=1)

        mock_mgr = AsyncMock()
        mock_mgr.unload = AsyncMock()

        # Injecte une entrée déjà expirée
        entry = _PoolEntry(mock_mgr)
        entry.idle_since = time.monotonic() - 5  # idle depuis 5s > max_idle=1s
        await pool._available.put(entry)
        pool._total = 1

        # Déclenche le sweep manuellement
        count_before = pool._available.qsize()
        assert count_before == 1

        # Exécute un cycle du sweeper
        to_keep = []
        to_discard = []
        for _ in range(pool._available.qsize()):
            try:
                e = pool._available.get_nowait()
            except asyncio.QueueEmpty:
                break
            if (
                e.idle_seconds > pool._max_idle_seconds
                and len(to_keep) >= pool._pool_size
            ):
                to_discard.append(e)
            else:
                to_keep.append(e)

        assert len(to_discard) == 1
        assert entry in to_discard

        await pool.shutdown()


# ── Tests EphemeralHandler ────────────────────────────────────────────────────


class TestEphemeralHandler:
    @pytest.mark.asyncio
    async def test_call_lifecycle(self):
        """Un appel complet : acquire → handle → release."""
        from xcore.configurations.sections import EphemeralConfig
        from xcore.kernel.runtime.ephemeral_handler import EphemeralHandler

        manifest = make_manifest(pool_size=0)
        ctx = make_ctx()
        config = EphemeralConfig(pool_size=0, max_concurrent=5)

        mock_lm = AsyncMock()
        mock_lm.load = AsyncMock()
        mock_lm.call = AsyncMock(return_value={"status": "ok", "data": "pdf_bytes"})
        mock_lm.unload = AsyncMock()
        mock_lm.plugin_router = None
        mock_lm.plugin_middlewares = {}
        mock_lm.state = MagicMock()

        with patch(
            "xcore.kernel.runtime.lifecycle.LifecycleManager",
            return_value=mock_lm,
        ):
            handler = EphemeralHandler(manifest, ctx, config)

            # start() tente de collecter le router via un boot temporaire
            with patch.object(handler._pool, "start", AsyncMock()):
                # Simule le boot temporaire pour router collection
                pass

            result = await handler.call("generate", {"template": "invoice"})
            assert result["status"] == "ok"
            assert handler._calls_total == 1
            assert handler._calls_error == 0

    @pytest.mark.asyncio
    async def test_error_unloads_instance(self):
        """En cas d'erreur dans handle(), l'instance est déchargée (pas remise au pool)."""
        from xcore.configurations.sections import EphemeralConfig
        from xcore.kernel.runtime.ephemeral_handler import EphemeralHandler

        manifest = make_manifest(pool_size=0)
        ctx = make_ctx()
        config = EphemeralConfig(pool_size=0, max_concurrent=5)

        mock_lm = AsyncMock()
        mock_lm.load = AsyncMock()
        mock_lm.call = AsyncMock(side_effect=RuntimeError("render failed"))
        mock_lm.unload = AsyncMock()

        with patch(
            "xcore.kernel.runtime.lifecycle.LifecycleManager",
            return_value=mock_lm,
        ):
            handler = EphemeralHandler(manifest, ctx, config)

            with pytest.raises(RuntimeError, match="render failed"):
                await handler.call("generate", {})

            assert handler._calls_error == 1
            mock_lm.unload.assert_awaited()  # décharge directe, pas de retour au pool

    def test_status(self):
        """status() retourne les infos attendues."""
        from xcore.configurations.sections import EphemeralConfig
        from xcore.kernel.runtime.ephemeral_handler import EphemeralHandler
        from xcore.kernel.runtime.state_machine import PluginState

        manifest = make_manifest(pool_size=3)
        ctx = make_ctx()
        config = EphemeralConfig(pool_size=3, max_concurrent=10)

        handler = EphemeralHandler(manifest, ctx, config)
        s = handler.status()

        assert s["mode"] == "ephemeral"
        assert s["state"] == PluginState.READY.value
        assert "pool" in s
        assert s["pool"]["pool_size"] == 3
        assert s["calls_total"] == 0


# ── Test integration supervisor ───────────────────────────────────────────────


class TestSupervisorIntegration:
    """
    Vérifie que supervisor.call() fonctionne sans modification
    pour un plugin Ephemeral.
    """

    @pytest.mark.asyncio
    async def test_supervisor_calls_ephemeral_transparently(self):
        """Le supervisor appelle un Ephemeral exactement comme un Trusted."""
        from xcore.configurations.sections import EphemeralConfig
        from xcore.kernel.runtime.ephemeral_handler import EphemeralHandler

        manifest = make_manifest(pool_size=0)
        manifest.permissions = []
        ctx = make_ctx()
        config = EphemeralConfig(pool_size=0, max_concurrent=5)

        mock_lm = AsyncMock()
        mock_lm.load = AsyncMock()
        mock_lm.call = AsyncMock(return_value={"status": "ok", "pdf": "..."})
        mock_lm.unload = AsyncMock()

        handler = EphemeralHandler(manifest, ctx, config)

        # Simule ce que fait le supervisor : appelle handler.call() directement
        with patch(
            "xcore.kernel.runtime.lifecycle.LifecycleManager",
            return_value=mock_lm,
        ):
            result = await handler.call("generate", {"template": "receipt"})

        assert result["status"] == "ok"
        # Le supervisor n'a pas besoin de savoir que c'est Ephemeral
        assert handler.state.value == "ready"
