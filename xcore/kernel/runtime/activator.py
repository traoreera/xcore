"""
activator.py — Stratégies d'activation des plugins.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from ..observability import get_logger

if TYPE_CHECKING:
    from ..api.contract import PluginHandler
    from .ephemeral_handler import EphemeralHandler
    from .loader import PluginLoader

logger = get_logger(__name__)


class ActivatorRegistry:
    """Registre des activateurs de plugins par mode d'exécution."""

    def __init__(self) -> None:
        self._activators: dict[Any, PluginActivator] = {}

    def register(self, mode: Any, activator: PluginActivator) -> None:
        self._activators[mode] = activator
        logger.debug(f"Activateur enregistré pour le mode : {mode}")

    def get(self, mode: Any) -> PluginActivator | None:
        return self._activators.get(mode)


class PluginActivator(ABC):
    """Interface de base pour les stratégies d'activation."""

    @abstractmethod
    async def activate(self, manifest: Any, loader: "PluginLoader") -> "PluginHandler":
        """Active un plugin et retourne son gestionnaire."""
        ...


class TrustedActivator(PluginActivator):
    """Active un plugin Trusted dans le processus courant."""

    async def activate(self, manifest: Any, loader: "PluginLoader") -> "PluginHandler":
        from ..security.signature import SignatureError, verify_plugin
        from ..security.validation import ASTScanner
        from .lifecycle import LifecycleManager, LoadError

        if loader._config.strict_trusted and manifest.execution_mode.value == "trusted":
            try:
                verify_plugin(manifest, loader._config.secret_key)
            except SignatureError as e:
                raise LoadError(str(e)) from e

        scanner = ASTScanner()
        scan = scanner.scan(
            manifest.plugin_dir,
            whitelist=manifest.allowed_imports,
            entry_point=manifest.entry_point,
        )
        if not scan.passed:
            logger.warning(f"[{manifest.name}] Scan AST (non bloquant) : {scan}")

        lm = LifecycleManager(
            manifest,
            ctx=loader._ctx,
            caller=loader._caller,
        )
        await lm.start()
        return lm


class SandboxedActivator(PluginActivator):
    """Active un plugin Sandboxed dans un subprocess isolé."""

    async def activate(self, manifest: Any, loader: "PluginLoader") -> "PluginHandler":
        from ..sandbox.process_manager import SandboxProcessManager
        from ..security.validation import ASTScanner

        scanner = ASTScanner()
        scan = scanner.scan(
            manifest.plugin_dir,
            whitelist=manifest.allowed_imports,
            entry_point=manifest.entry_point,
        )

        if not scan.passed:
            raise ValueError(f"[{manifest.name}] Scan AST échoué : {scan}")

        mgr = SandboxProcessManager(manifest=manifest, ctx=loader)
        await mgr.start()
        return mgr


class EphemeralActivator(PluginActivator):
    """
    Activateur pour les plugins Ephemeral.

    Crée un EphemeralHandler (warm pool + cycle call-boot-exec-shutdown).
    Le handler est stocké dans _handlers comme n'importe quel autre plugin —
    le supervisor n'a pas besoin de cas particulier.

    La config EphemeralConfig est lue depuis :
      1. manifest.ephemeral   (déclaré dans plugin.yaml sous la clé `ephemeral:`)
      2. ctx.config.ephemeral (défaut global dans xcore.yaml sous `plugins.ephemeral:`)
      3. EphemeralConfig()    (valeurs par défaut si rien n'est configuré)
    """

    async def activate(
        self,
        manifest: Any,
        loader: "PluginLoader",
    ) -> "EphemeralHandler":
        from ...configurations.sections import EphemeralConfig
        from ..security.signature import SignatureError, verify_plugin
        from ..security.validation import ASTScanner
        from .ephemeral_handler import EphemeralHandler
        from .lifecycle import LoadError

        # Vérifie la signature pour les plugins ephemeral quand strict_trusted est activé.
        if loader._config.strict_trusted:
            try:
                verify_plugin(manifest, loader._config.secret_key)
            except SignatureError as e:
                raise LoadError(str(e)) from e

        scanner = ASTScanner()
        scan = scanner.scan(
            manifest.plugin_dir,
            whitelist=manifest.allowed_imports,
            entry_point=manifest.entry_point,
        )
        if not scan.passed:
            logger.warning(f"[{manifest.name}] Scan AST (non bloquant) : {scan}")

        # Résolution de la config : manifest > global > défaut
        eph_raw = getattr(manifest, "ephemeral", None)
        if isinstance(eph_raw, dict):
            config = EphemeralConfig.from_dict(eph_raw)
        elif isinstance(eph_raw, EphemeralConfig):
            config = eph_raw
        else:
            # Fallback sur la config globale plugins.ephemeral
            config = getattr(loader._ctx.config, "ephemeral", EphemeralConfig())

        handler = EphemeralHandler(
            manifest=manifest,
            ctx=loader._ctx,
            config=config,
            caller=loader._caller,
        )
        await handler.start()

        logger.info(
            "plugin éphémère activé",
            plugin=manifest.name,
            pool_size=config.pool_size,
            max_conc=config.max_concurrent,
        )
        return handler


class LagacyActivator(PluginActivator):
    async def activate(
        self,
        manifest: Any,
        loader: "PluginLoader",
    ) -> "PluginHandler":
        raise NotImplementedError(
            "LagacyActivator n'est pas implémenté — utiliser TrustedActivator pour le mode LEGACY"
        )
