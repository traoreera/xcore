"""
xcore/kernel/runtime/ephemeral_handler.py

Handler runtime pour les plugins Ephemeral.

Implémente l'interface PluginHandler comme LifecycleManager et
SandboxProcessManager — le supervisor n'a pas besoin de savoir
qu'il parle à un plugin Ephemeral.

Deux modes selon la config :
  pool_size = 0  → cold boot pur à chaque appel
  pool_size > 0  → warm pool (instances pré-chargées)

Le manifest est stocké pour que le supervisor puisse l'inspecter
(permissions, rate limit, router HTTP…) sans charger une instance.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...configurations.sections import EphemeralConfig
    from ..context import KernelContext
    from .lifecycle import LifecycleManager

from ..observability import get_logger
from .state_machine import PluginState
from .warm_pool import WarmPool

logger = get_logger("xcore.runtime.ephemeral")


class EphemeralHandler:
    """
    Handler Ephemeral — implémente PluginHandler.

    Chaque appel à call() :
      1. Acquiert une instance (pool ou cold boot)
      2. Exécute handle()
      3. Libère l'instance (retour au pool ou unload)

    L'instance ne survit jamais entre deux appels → zéro état implicite.
    """

    def __init__(
        self,
        manifest: Any,
        ctx: "KernelContext",
        config: "EphemeralConfig",
        caller: Any = None,
    ) -> None:
        self._manifest = manifest
        self._ctx = ctx
        self._config = config
        self._caller = caller

        self._pool = WarmPool(
            manifest=manifest,
            ctx=ctx,
            pool_size=config.pool_size,
            max_idle_seconds=config.max_idle_seconds,
            max_concurrent=config.max_concurrent,
            boot_timeout=config.boot_timeout,
            caller=caller,
        )

        # Métriques légères
        self._calls_total = 0
        self._calls_error = 0
        self._started_at = time.monotonic()

        # Exposition du router HTTP du plugin (collecté lors du premier boot si absent)
        self.plugin_router: Any = None
        self.plugin_middlewares: dict = {}

        # State sentinel — Ephemeral est toujours READY du point de vue du supervisor
        self.state = PluginState.READY

    # ── Accès au manifest (requis par loader.reload()) ────────────────────────

    @property
    def manifest(self) -> Any:
        return self._manifest

    # ── Cycle de vie ──────────────────────────────────────────────────────────

    async def start(self) -> None:
        """
        Démarre le warm pool (pré-charge pool_size instances).
        Si pool_size=0, collecte le router via un boot temporaire.
        """
        await self._pool.start()

        # Collecte le router HTTP depuis une instance temporaire si pool_size=0.
        # Si le pool est actif, on lit depuis la première instance déjà chargée.
        if self._config.pool_size > 0:
            # Peek dans le pool sans dépiler — on prend et on remet
            async with self._pool.instance() as mgr:
                self._collect_router(mgr)
        else:
            # Boot temporaire juste pour la collecte du router.
            # Note : on_load() s'exécute ici — les side-effects (connexions DB, etc.)
            # sont inévitables. Si on_load() échoue, le plugin ne sera pas enregistré.
            from .lifecycle import LifecycleManager

            lm = LifecycleManager(
                manifest=self._manifest,
                ctx=self._ctx,
                caller=self._caller,
            )
            try:
                await lm.load()
                self._collect_router(lm)
            finally:
                await lm.unload()

        logger.info(
            "plugin éphémère prêt",
            plugin=self._manifest.name,
            pool_size=self._config.pool_size,
        )

    async def stop(self) -> None:
        """Arrête le warm pool et décharge toutes les instances."""
        await self._pool.shutdown()
        logger.info("plugin éphémère arrêté", plugin=self._manifest.name)

    # ── Appel ─────────────────────────────────────────────────────────────────

    async def call(self, action: str, payload: dict) -> dict:
        """
        Exécute une action sur une instance Ephemeral.

        Cycle complet :
          acquire (pool hit ou cold boot) → handle() → release (pool ou unload)

        En cas d'erreur dans handle(), l'instance est déchargée via pool.discard()
        plutôt que remise dans le pool (instance potentiellement corrompue).
        """
        self._calls_total += 1

        mgr = await self._pool.acquire()
        try:
            result = await mgr.call(action, payload)
            await self._pool.release(mgr)
            return result
        except Exception as e:
            self._calls_error += 1
            # Instance potentiellement dans un état incohérent → décharge via discard()
            # qui s'occupe du unload, du décrément de _total et du release du semaphore.
            await self._pool.discard(mgr)

            logger.error(
                "erreur appel éphémère",
                plugin=self._manifest.name,
                action=action,
                erreur=str(e),
            )
            raise

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _collect_router(self, mgr: "LifecycleManager") -> None:
        """Collecte le router HTTP et les middlewares depuis une instance."""
        if hasattr(mgr, "plugin_router") and mgr.plugin_router is not None:
            self.plugin_router = mgr.plugin_router
        if hasattr(mgr, "state") and mgr.plugin_middlewares:
            self.plugin_middlewares = mgr.plugin_middlewares

    # ── Interface PluginHandler ───────────────────────────────────────────────

    def status(self) -> dict:
        uptime = time.monotonic() - self._started_at
        pool_stats = self._pool.stats()
        return {
            "name": self._manifest.name,
            "mode": "ephemeral",
            "state": self.state.value,
            "pool": pool_stats,
            "calls_total": self._calls_total,
            "calls_error": self._calls_error,
            "cold_boots": pool_stats["cold_boots"],
            "uptime_s": round(uptime, 1),
        }
