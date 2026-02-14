"""
trusted/runner.py
──────────────────
Chargement in-process des plugins Trusted.
Applique : timeout par appel, filesystem check, injection de services.
"""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import sys
import time
from pathlib import Path
from typing import Any

from ..contracts.plugin_manifest import PluginManifest, FilesystemConfig
from ..contracts.base_plugin import BasePlugin, TrustedBase

logger = logging.getLogger("plManager.trusted")


class TrustedLoadError(Exception):
    pass


class FilesystemViolation(Exception):
    pass


# ══════════════════════════════════════════════
# Vérification filesystem
# ══════════════════════════════════════════════

def check_filesystem_access(
    path: str | Path,
    plugin_dir: Path,
    fs_config: FilesystemConfig,
    plugin_name: str,
) -> None:
    """
    Vérifie qu'un chemin respecte les règles filesystem du manifest.
    Utilisé par les plugins Trusted qui accèdent au filesystem.
    Lève FilesystemViolation si la règle est violée.

    Note : ["*"] dans allowed_paths = accès total (mode Trusted par défaut).
    """
    if "*" in fs_config.allowed_paths:
        # Trusted avec accès complet — vérifie quand même les denied
        if not fs_config.denied_paths:
            return
        resolved = Path(path).resolve()
        for denied in fs_config.denied_paths:
            denied_abs = (plugin_dir / denied).resolve()
            if str(resolved).startswith(str(denied_abs)):
                raise FilesystemViolation(
                    f"Plugin '{plugin_name}' : accès refusé à {path} "
                    f"(chemin dans denied_paths : {denied})"
                )
        return

    resolved = Path(path).resolve()

    # Vérifie les chemins autorisés
    for allowed in fs_config.allowed_paths:
        allowed_abs = (plugin_dir / allowed).resolve()
        if str(resolved).startswith(str(allowed_abs)):
            # Dans allowed — vérifie quand même denied
            for denied in fs_config.denied_paths:
                denied_abs = (plugin_dir / denied).resolve()
                if str(resolved).startswith(str(denied_abs)):
                    raise FilesystemViolation(
                        f"Plugin '{plugin_name}' : accès refusé à {path} "
                        f"(chemin dans denied_paths : {denied})"
                    )
            return

    raise FilesystemViolation(
        f"Plugin '{plugin_name}' : accès refusé à {path}. "
        f"Chemins autorisés : {fs_config.allowed_paths}"
    )


# ══════════════════════════════════════════════
# Runner
# ══════════════════════════════════════════════

class TrustedRunner:

    def __init__(
        self,
        manifest: PluginManifest,
        services: dict[str, Any] | None = None,
    ) -> None:
        self.manifest    = manifest
        self.services    = services or {}
        self._instance:  BasePlugin | None = None
        self._module:    Any               = None
        self._loaded_at: float | None      = None

    # ──────────────────────────────────────────
    # Chargement
    # ──────────────────────────────────────────

    async def load(self) -> None:
        logger.info(f"[{self.manifest.name}] Chargement Trusted en mémoire...")

        entry = self.manifest.plugin_dir / self.manifest.entry_point
        if not entry.exists():
            raise TrustedLoadError(f"Entry point introuvable : {entry}")

        module_name  = f"trusted_plugins.{self.manifest.name}"
        self._module = self._import_from_path(module_name, entry)

        if not hasattr(self._module, "Plugin"):
            raise TrustedLoadError(
                f"[{self.manifest.name}] Classe Plugin() manquante dans {entry}"
            )

        plugin_class = self._module.Plugin

        if isinstance(plugin_class, type) and issubclass(plugin_class, TrustedBase):
            self._instance = plugin_class(services=self.services)
        else:
            self._instance = plugin_class()

        if not isinstance(self._instance, BasePlugin):
            raise TrustedLoadError(
                f"[{self.manifest.name}] Plugin ne respecte pas le contrat BasePlugin"
            )

        if hasattr(self._instance, "on_load"):
            await self._instance.on_load()

        self._loaded_at = time.monotonic()
        logger.info(
            f"[{self.manifest.name}] ✅ Trusted chargé | "
            f"timeout={self.manifest.resources.timeout_seconds}s | "
            f"fs={'full' if '*' in self.manifest.filesystem.allowed_paths else self.manifest.filesystem.allowed_paths}"
        )

    @staticmethod
    def _import_from_path(module_name: str, path: Path) -> Any:
        if module_name in sys.modules:
            del sys.modules[module_name]
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise TrustedLoadError(f"Impossible de créer le spec pour {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    # ──────────────────────────────────────────
    # Appel avec timeout
    # ──────────────────────────────────────────

    async def call(self, action: str, payload: dict) -> dict:
        if self._instance is None:
            raise TrustedLoadError(
                f"Plugin {self.manifest.name} non chargé"
            )

        timeout = self.manifest.resources.timeout_seconds

        try:
            result = await asyncio.wait_for(
                self._instance.handle(action, payload),
                timeout=timeout if timeout > 0 else None,
            )
        except asyncio.TimeoutError:
            logger.error(
                f"[{self.manifest.name}] Timeout ({timeout}s) sur action '{action}'"
            )
            return {
                "status": "error",
                "msg":    f"Timeout après {timeout}s",
                "code":   "timeout",
            }

        if not isinstance(result, dict):
            result = {"status": "ok", "result": result}
        return result

    # ──────────────────────────────────────────
    # Vérification filesystem (appelable par le plugin via services)
    # ──────────────────────────────────────────

    def check_path(self, path: str | Path) -> None:
        """
        Expose la vérification filesystem aux plugins Trusted via services.
        Usage dans un plugin Trusted :
            self.get_service("check_path")("/some/path")
        """
        check_filesystem_access(
            path,
            self.manifest.plugin_dir,
            self.manifest.filesystem,
            self.manifest.name,
        )

    # ──────────────────────────────────────────
    # Cycle de vie
    # ──────────────────────────────────────────

    async def reload(self) -> None:
        logger.info(f"[{self.manifest.name}] Rechargement à chaud...")
        if hasattr(self._instance, "on_reload"):
            await self._instance.on_reload()
        await self.unload()
        await self.load()

    async def unload(self) -> None:
        if self._instance and hasattr(self._instance, "on_unload"):
            await self._instance.on_unload()
        module_name = f"trusted_plugins.{self.manifest.name}"
        sys.modules.pop(module_name, None)
        self._instance = None
        self._module   = None
        logger.info(f"[{self.manifest.name}] Trusted déchargé")

    # ──────────────────────────────────────────
    # Status
    # ──────────────────────────────────────────

    @property
    def uptime(self) -> float | None:
        return None if self._loaded_at is None else time.monotonic() - self._loaded_at

    def status(self) -> dict:
        return {
            "name":   self.manifest.name,
            "mode":   "trusted",
            "loaded": self._instance is not None,
            "uptime": round(self.uptime, 1) if self.uptime else None,
            "limits": {
                "timeout_s":     self.manifest.resources.timeout_seconds,
                "max_memory_mb": self.manifest.resources.max_memory_mb,
                "max_disk_mb":   self.manifest.resources.max_disk_mb,
                "rate_limit": {
                    "calls":          self.manifest.resources.rate_limit.calls,
                    "period_seconds": self.manifest.resources.rate_limit.period_seconds,
                },
                "filesystem": {
                    "allowed": self.manifest.filesystem.allowed_paths,
                    "denied":  self.manifest.filesystem.denied_paths,
                },
            },
        }