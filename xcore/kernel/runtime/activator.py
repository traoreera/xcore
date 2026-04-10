"""
activator.py — Stratégies d'activation des plugins.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..api.contract import PluginHandler
    from .loader import PluginLoader

logger = logging.getLogger("xcore.runtime.activator")


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

        if loader._config.strict_trusted or manifest.execution_mode.value == "trusted":
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

        mgr = SandboxProcessManager(manifest)
        await mgr.start()
        return mgr
