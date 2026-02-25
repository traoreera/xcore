"""
runner.py — TrustedRunner corrigé
"""

from __future__ import annotations

import asyncio
import importlib.util
import inspect
import logging
import sys
import time
from pathlib import Path
from typing import Any

from ..contracts.base_plugin import BasePlugin
from ..contracts.plugin_manifest import FilesystemConfig, PluginManifest

logger = logging.getLogger("plManager.trusted")


class TrustedLoadError(Exception):
    pass


class FilesystemViolation(Exception):
    pass


def check_filesystem_access(
    path: str | Path,
    plugin_dir: Path,
    fs_config: FilesystemConfig,
    plugin_name: str,
) -> None:
    if "*" in fs_config.allowed_paths:
        if not fs_config.denied_paths:
            return
        resolved = Path(path).resolve()
        for denied in fs_config.denied_paths:
            denied_abs = (plugin_dir / denied).resolve()
            if str(resolved).startswith(str(denied_abs)):
                raise FilesystemViolation(
                    f"Plugin '{plugin_name}' : accès refusé à {path}"
                )
        return

    resolved = Path(path).resolve()
    for allowed in fs_config.allowed_paths:
        allowed_abs = (plugin_dir / allowed).resolve()
        if str(resolved).startswith(str(allowed_abs)):
            for denied in fs_config.denied_paths:
                denied_abs = (plugin_dir / denied).resolve()
                if str(resolved).startswith(str(denied_abs)):
                    raise FilesystemViolation(
                        f"Plugin '{plugin_name}' : accès refusé à {path}"
                    )
            return

    raise FilesystemViolation(
        f"Plugin '{plugin_name}' : accès refusé à {path}. "
        f"Chemins autorisés : {fs_config.allowed_paths}"
    )


class TrustedRunner:
    def __init__(
        self,
        manifest: PluginManifest,
        services: dict[str, Any] | None = None,
    ) -> None:
        self.manifest = manifest
        self._services = services if services is not None else {}
        self._instance: BasePlugin | None = None
        self._module: Any = None
        self._loaded_at: float | None = None

    # FIX #3 — mems() ne mettait pas à jour les services existants au reload :
    # L'ancienne logique n'ajoutait que les `new_keys` (différence d'ensembles),
    # donc si un plugin exposait "core" → reload → "core" existait déjà dans le
    # container → jamais mis à jour → objet stale jusqu'à redémarrage complet.
    #
    # Correction : on distingue deux cas :
    #   • Chargement initial  → on ne touche PAS aux clés déjà présentes
    #     (un autre plugin a pu les enregistrer en premier, on respecte l'ordre
    #     topologique).
    #   • Reload              → on force la mise à jour des clés du plugin
    #     rechargé pour que le nouvel objet remplace l'ancien dans le container.
    #
    # Le paramètre `is_reload` permet de distinguer les deux appels depuis load()
    # et reload().
    def mems(self, *, is_reload: bool = False) -> dict:
        """
        Propage les services enregistrés par le plugin vers le container partagé.

        Args:
            is_reload: si True, écrase les clés existantes appartenant à ce plugin
                       (comportement reload). Si False (chargement initial), n'ajoute
                       que les nouvelles clés pour respecter l'ordre topologique.

        Returns:
            Le container partagé mis à jour.
        """
        if self._instance is None:
            return self._services

        instance_services: dict = getattr(self._instance, "_services", {})

        if is_reload:
            # Reload : on met à jour toutes les clés du plugin rechargé.
            # On ne touche pas aux clés étrangères (appartenant à d'autres plugins).
            if updated := {
                k:v for k, v in instance_services.items() if k in self._services or k not in self._services
            }:
                self._services.update(updated)
                logger.info(
                    f"[{self.manifest.name}] 🔄 Services mis à jour (reload) : "
                    f"{sorted(updated.keys())}"
                )
        elif new_keys := set(instance_services.keys()) - set(self._services.keys()):
                    for key in new_keys:
                        self._services[key] = instance_services[key]
                    logger.info(
                        f"[{self.manifest.name}] 📦 Nouveaux services exposés : "
                        f"{sorted(new_keys)}"
                    )

        return self._services

    async def load(self) -> None:
        logger.info(f"[{self.manifest.name}] Chargement Trusted en mémoire...")

        entry = self.manifest.plugin_dir / self.manifest.entry_point
        if not entry.exists():
            raise TrustedLoadError(f"Entry point introuvable : {entry}")

        src_dir = str(self.manifest.plugin_dir / "src")
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)

        module_name = f"plugin_{self.manifest.name}"
        self._module = self._import_from_path(module_name, entry)

        if not hasattr(self._module, "Plugin"):
            raise TrustedLoadError(
                f"[{self.manifest.name}] Classe Plugin() manquante dans {entry}"
            )

        plugin_class = self._module.Plugin

        try:
            sig = inspect.signature(plugin_class.__init__)
            accepts_services = "services" in sig.parameters
        except (ValueError, TypeError):
            accepts_services = False

        if accepts_services:
            self._instance = plugin_class(services=self._services)
        else:
            self._instance = plugin_class()
            if hasattr(self._instance, "_services"):
                self._instance._services = self._services

        if not isinstance(self._instance, BasePlugin):
            raise TrustedLoadError(
                f"[{self.manifest.name}] Plugin ne respecte pas BasePlugin"
            )

        if hasattr(self._instance, "env_variable"):
            await self._instance.env_variable(self.manifest.env)

        if hasattr(self._instance, "on_load"):
            await self._instance.on_load()

        # Chargement initial → is_reload=False
        self.mems(is_reload=False)

        self._loaded_at = time.monotonic()
        logger.info(
            f"[{self.manifest.name}] ✅ Trusted chargé | "
            f"timeout={self.manifest.resources.timeout_seconds}s"
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

    async def call(self, action: str, payload: dict) -> dict:
        if self._instance is None:
            raise TrustedLoadError(f"Plugin {self.manifest.name} non chargé")

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
                "msg": f"Timeout après {timeout}s",
                "code": "timeout",
            }

        if not isinstance(result, dict):
            result = {"status": "ok", "result": result}
        return result

    def check_path(self, path: str | Path) -> None:
        check_filesystem_access(
            path,
            self.manifest.plugin_dir,
            self.manifest.filesystem,
            self.manifest.name,
        )

    async def reload(self) -> None:
        logger.info(f"[{self.manifest.name}] Rechargement à chaud...")
        if hasattr(self._instance, "on_reload"):
            await self._instance.on_reload()
        await self.unload()
        await self.load()
        # load() appelle mems(is_reload=False) mais on est dans un reload :
        # on rappelle avec is_reload=True pour forcer la mise à jour des services.
        self.mems(is_reload=True)

    async def unload(self) -> None:
        if self._instance and hasattr(self._instance, "on_unload"):
            await self._instance.on_unload()

        module_name = f"plugin_{self.manifest.name}"
        sys.modules.pop(module_name, None)

        src_dir = str(self.manifest.plugin_dir / "src")
        if src_dir in sys.path:
            sys.path.remove(src_dir)

        self._instance = None
        self._module = None
        logger.info(f"[{self.manifest.name}] Trusted déchargé")

    @property
    def uptime(self) -> float | None:
        return None if self._loaded_at is None else time.monotonic() - self._loaded_at

    def status(self) -> dict:
        return {
            "name": self.manifest.name,
            "mode": "trusted",
            "loaded": self._instance is not None,
            "uptime": round(self.uptime, 1) if self.uptime else None,
        }