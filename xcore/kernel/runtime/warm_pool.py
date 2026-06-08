"""
xcore/kernel/runtime/warm_pool.py

Pool d'instances pré-chargées pour les plugins Ephemeral.

Principe :
  - pool_size instances sont bootées au démarrage et maintenues prêtes.
  - Un appel acquire() prend une instance disponible (immédiat) ou boot à froid.
  - release() remet l'instance dans le pool si la taille max n'est pas atteinte,
    sinon la décharge proprement.
  - Un worker asyncio surveille les instances idle > max_idle_seconds et les décharge.
  - max_concurrent limite le nombre total d'instances simultanées (pool + cold).
    Au-delà, acquire() attend qu'une instance se libère (backpressure).

Thread-safety : toutes les opérations passent par asyncio.Lock + asyncio.Semaphore.
Aucune mutation sans le lock — safe pour les appels concurrents.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .lifecycle import LifecycleManager

logger = logging.getLogger("xcore.runtime.warm_pool")


class _PoolEntry:
    """Wrapper autour d'une instance LifecycleManager avec timestamp idle."""

    __slots__ = ("manager", "idle_since")

    def __init__(self, manager: "LifecycleManager") -> None:
        self.manager = manager
        self.idle_since = time.monotonic()

    def touch(self) -> None:
        """Remet le timer idle à zéro (appelé au release)."""
        self.idle_since = time.monotonic()

    @property
    def idle_seconds(self) -> float:
        return time.monotonic() - self.idle_since


class WarmPool:
    """
    Pool d'instances Ephemeral pour un plugin donné.

    Usage (géré par EphemeralActivator — ne pas appeler directement) :
        pool = WarmPool(manifest, ctx, config)
        await pool.start()                    # pré-charge pool_size instances

        async with pool.instance() as mgr:    # context manager recommandé
            result = await mgr.call(action, payload)

        await pool.shutdown()                 # décharge toutes les instances
    """

    def __init__(
        self,
        manifest: Any,
        ctx: Any,
        pool_size: int = 0,
        max_idle_seconds: int = 60,
        max_concurrent: int = 10,
        boot_timeout: float = 5.0,
        caller: Any = None,
    ) -> None:
        self._manifest = manifest
        self._ctx = ctx
        self._pool_size = pool_size
        self._max_idle_seconds = max_idle_seconds
        self._boot_timeout = boot_timeout
        self._caller = caller

        # Pool FIFO d'instances prêtes
        self._available: asyncio.Queue[_PoolEntry] = asyncio.Queue()

        # Semaphore : limite le nombre d'instances simultanément EN VOL (hors pool).
        # Les instances pré-chauffées dans _available ne consomment pas de slot —
        # un slot est consommé à acquire() et rendu à release().
        self._semaphore = asyncio.Semaphore(max(max_concurrent, pool_size))

        # Lock pour les opérations qui modifient _total
        self._lock = asyncio.Lock()

        # Compteur d'instances actuellement en existence (prêtes + en vol)
        self._total = 0

        # Compteur de cold boots (pour métriques)
        self._cold_boot_count = 0

        self._idle_task: asyncio.Task | None = None
        self._closed = False

    # ── Démarrage ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Pré-charge pool_size instances. Appelé par EphemeralActivator au boot."""
        if self._pool_size <= 0:
            logger.debug("[%s] warm pool désactivé (pool_size=0)", self._manifest.name)
            return

        boots = [self._boot_one() for _ in range(self._pool_size)]
        results = await asyncio.gather(*boots, return_exceptions=True)

        ok = sum(1 for r in results if not isinstance(r, Exception))
        for r in results:
            if isinstance(r, Exception):
                logger.warning(
                    "[%s] warm pool : échec boot initial : %s",
                    self._manifest.name,
                    r,
                )

        logger.info(
            "[%s] warm pool prêt — %d/%d instance(s)",
            self._manifest.name,
            ok,
            self._pool_size,
        )

        # Démarrage du worker de nettoyage idle
        self._idle_task = asyncio.create_task(
            self._idle_sweeper(),
            name=f"ephemeral-idle-{self._manifest.name}",
        )

    # ── Acquisition / release ─────────────────────────────────────────────────

    async def acquire(self) -> "LifecycleManager":
        """
        Retourne une instance prête.
        - Si le pool a une instance disponible → immédiat (0 ms).
        - Sinon → cold boot (3–6 ms d'après le bench).
        - Si max_concurrent atteint → attend (backpressure).

        Le semaphore est acquis avant la tentative de pool-hit pour que
        release() puisse toujours le libérer sans asymétrie.
        """
        if self._closed:
            raise RuntimeError(f"[{self._manifest.name}] WarmPool fermé")

        # Acquiert un slot de concurrence AVANT de tenter le pool ou le cold boot.
        # Garantit que release() peut toujours appeler semaphore.release() de façon symétrique.
        await self._semaphore.acquire()

        # Tente de prendre depuis le pool sans bloquer
        try:
            entry = self._available.get_nowait()
            logger.debug("[%s] warm pool hit", self._manifest.name)
            return entry.manager
        except asyncio.QueueEmpty:
            pass

        # Cold boot
        try:
            mgr = await self._cold_boot()
            return mgr
        except Exception:
            self._semaphore.release()
            raise

    async def release(self, mgr: "LifecycleManager") -> None:
        """
        Remet l'instance dans le pool si la taille max n'est pas atteinte.
        Sinon la décharge proprement.
        Libère toujours le slot de concurrence (symétrique avec acquire).
        """
        if self._closed:
            await self._safe_unload(mgr)
            self._semaphore.release()
            return

        if self._available.qsize() < self._pool_size:
            entry = _PoolEntry(mgr)
            entry.touch()
            await self._available.put(entry)
            self._semaphore.release()
            logger.debug("[%s] warm pool release → retour au pool", self._manifest.name)
        else:
            # Pool plein → décharge
            await self._safe_unload(mgr)
            async with self._lock:
                self._total -= 1
            self._semaphore.release()
            logger.debug(
                "[%s] warm pool release → décharge (pool plein)", self._manifest.name
            )

    async def discard(self, mgr: "LifecycleManager") -> None:
        """
        Retire une instance corrompue du pool sans la remettre en circulation.
        À utiliser dans les handlers d'erreur à la place de release().
        Libère le slot de concurrence comme release().
        """
        await self._safe_unload(mgr)
        async with self._lock:
            self._total = max(0, self._total - 1)
        self._semaphore.release()

    # ── Context manager ───────────────────────────────────────────────────────

    class _InstanceCtx:
        def __init__(self, pool: "WarmPool") -> None:
            self._pool = pool
            self._mgr: "LifecycleManager | None" = None

        async def __aenter__(self) -> "LifecycleManager":
            self._mgr = await self._pool.acquire()
            return self._mgr

        async def __aexit__(self, *_) -> None:
            if self._mgr is not None:
                await self._pool.release(self._mgr)

    def instance(self) -> "_InstanceCtx":
        """
        Utilisation recommandée :
            async with pool.instance() as mgr:
                result = await mgr.call(action, payload)
        """
        return self._InstanceCtx(self)

    # ── Internes ──────────────────────────────────────────────────────────────

    async def _boot_one(self) -> "LifecycleManager":
        """Boot une instance et la place dans le pool.

        Les instances pré-chauffées sont dans _available et ne consomment pas
        de slot de semaphore — le slot est consommé à acquire() quand elles
        sortent du pool vers un appelant.
        """
        mgr = await self._cold_boot()
        entry = _PoolEntry(mgr)
        await self._available.put(entry)
        return mgr

    async def _cold_boot(self) -> "LifecycleManager":
        """Instancie et charge un nouveau LifecycleManager."""
        from .lifecycle import LifecycleManager, LoadError

        async with self._lock:
            self._total += 1

        lm = LifecycleManager(
            manifest=self._manifest,
            ctx=self._ctx,
            caller=self._caller,
        )
        try:
            await asyncio.wait_for(lm.load(), timeout=self._boot_timeout)
        except asyncio.TimeoutError as e:
            async with self._lock:
                self._total -= 1
            raise LoadError(
                f"[{self._manifest.name}] Ephemeral boot timeout ({self._boot_timeout}s)"
            ) from e
        except Exception:
            async with self._lock:
                self._total -= 1
            raise

        self._cold_boot_count += 1
        logger.debug("[%s] cold boot OK (total=%d)", self._manifest.name, self._total)
        return lm

    async def _safe_unload(self, mgr: "LifecycleManager") -> None:
        """Décharge proprement une instance sans propager les erreurs."""
        try:
            await mgr.unload()
        except Exception as e:
            logger.warning(
                "[%s] erreur déchargement instance : %s",
                self._manifest.name,
                e,
            )

    # ── Worker de nettoyage idle ──────────────────────────────────────────────

    async def _idle_sweeper(self) -> None:
        """
        Toutes les 10s, décharge les instances idle > max_idle_seconds.
        Conserve toujours les pool_size instances les plus récentes (idle le plus bas).
        """
        while not self._closed:
            await asyncio.sleep(10)

            # Draine toute la queue
            entries: list[_PoolEntry] = []
            while True:
                try:
                    entries.append(self._available.get_nowait())
                except asyncio.QueueEmpty:
                    break

            if not entries:
                continue

            # Trie les plus fraîches en premier (idle_seconds croissant)
            entries.sort(key=lambda e: e.idle_seconds)

            to_discard: list[_PoolEntry] = []
            to_return: list[_PoolEntry] = []
            for i, entry in enumerate(entries):
                # Garde toujours les pool_size instances les plus fraîches
                # Évince uniquement les entrées excédentaires et effectivement idle
                if i >= self._pool_size and entry.idle_seconds > self._max_idle_seconds:
                    to_discard.append(entry)
                else:
                    to_return.append(entry)

            for entry in to_return:
                await self._available.put(entry)

            for entry in to_discard:
                await self._safe_unload(entry.manager)
                async with self._lock:
                    self._total -= 1
                logger.debug(
                    "[%s] idle sweep : instance déchargée (idle=%.0fs)",
                    self._manifest.name,
                    entry.idle_seconds,
                )

            if to_discard:
                logger.info(
                    "[%s] idle sweep : %d instance(s) déchargée(s)",
                    self._manifest.name,
                    len(to_discard),
                )

    # ── Shutdown ──────────────────────────────────────────────────────────────

    async def shutdown(self) -> None:
        """Décharge toutes les instances du pool proprement."""
        self._closed = True

        if self._idle_task and not self._idle_task.done():
            self._idle_task.cancel()
            try:
                await self._idle_task
            except asyncio.CancelledError:
                pass

        count = 0
        while True:
            try:
                entry = self._available.get_nowait()
                await self._safe_unload(entry.manager)
                count += 1
            except asyncio.QueueEmpty:
                break

        async with self._lock:
            self._total = 0

        logger.info(
            "[%s] warm pool arrêté (%d instance(s) déchargée(s))",
            self._manifest.name,
            count,
        )

    # ── Stats ─────────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        return {
            "plugin": self._manifest.name,
            "pool_size": self._pool_size,
            "available": self._available.qsize(),
            "total_alive": self._total,
            "cold_boots": self._cold_boot_count,
            "max_idle_s": self._max_idle_seconds,
            "closed": self._closed,
        }
