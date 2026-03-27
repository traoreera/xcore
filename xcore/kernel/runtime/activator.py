"""
activator.py — Stratégies d'activation des plugins.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .loader import PluginLoader
    from ..api.contract import PluginHandler

logger = logging.getLogger("xcore.runtime.activator")


class PluginActivator(ABC):
    """Interface de base pour les stratégies d'activation."""

    @abstractmethod
    async def activate(self, manifest: Any, loader: "PluginLoader") -> "PluginHandler":
        """Active un plugin et retourne son gestionnaire."""
        ...


class TrustedActivator(PluginActivator):
    """Active un plugin Trusted dans le processus courant."""

    async def activate(self, manifest: Any, loader: "PluginLoader") -> "PluginHandler":
        from .lifecycle import LifecycleManager, LoadError
        from ..security.signature import SignatureError, verify_plugin
        from ..security.validation import ASTScanner

        if loader._config.strict_trusted or manifest.execution_mode.value == "trusted":
            try:
                verify_plugin(manifest, loader._config.secret_key)
            except SignatureError as e:
                raise LoadError(str(e)) from e

        scanner = ASTScanner()
        scan = scanner.scan(manifest.plugin_dir, whitelist=manifest.allowed_imports)
        if not scan.passed:
            logger.warning(f"[{manifest.name}] Scan AST (non bloquant) : {scan}")

        lm = LifecycleManager(
            manifest,
            services=loader._services,
            events=loader._events,
            hooks=loader._hooks,
            registry=loader._registry,
            caller=loader._caller,
        )
        await lm.start()
        return lm


class SandboxedActivator(PluginActivator):
    """Active un plugin Sandboxed dans un subprocess isolé."""

    async def activate(self, manifest: Any, loader: "PluginLoader") -> "PluginHandler":
        from ..security.validation import ASTScanner
        from ..sandbox.process_manager import SandboxProcessManager

        scanner = ASTScanner()
        scan = scanner.scan(manifest.plugin_dir, whitelist=manifest.allowed_imports)
        if not scan.passed:
            raise ValueError(f"[{manifest.name}] Scan AST échoué : {scan}")

        mgr = SandboxProcessManager(manifest)
        await mgr.start()
        return mgr
