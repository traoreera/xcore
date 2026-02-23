"""
 — PATCHÉ
===========================
Correction du problème de services non disponibles.

Problème :
  erp_core.on_load() fait self._services["core"] = CoreService(...)
  Mais self._services est vide car :
    1. Si Plugin() n'accepte pas `services` → instancié sans le container
    2. Même si le container est passé, on_load() modifie le dict local
       mais mems() qui synchronise vers PluginManager._services n'est
       jamais appelé après on_load().

Correction :
  1. Toujours passer le container `services` au plugin (via _services direct
     si __init__ ne l'accepte pas)
  2. Appeler mems() APRÈS on_load() pour propager les nouveaux services
     vers le container partagé du PluginManager
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


# ══════════════════════════════════════════════
# Vérification filesystem (inchangé)
# ══════════════════════════════════════════════


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


# ══════════════════════════════════════════════
# Runner
# ══════════════════════════════════════════════


class TrustedRunner:
    def __init__(
        self,
        manifest: PluginManifest,
        services: dict[str, Any] | None = None,
    ) -> None:
        self.manifest = manifest
        # ★ Ce dict EST le même objet que PluginManager._services
        # (passé par référence) — toute modification ici est visible
        # immédiatement dans le PluginManager.
        self._services = services if services is not None else {}
        self._instance: BasePlugin | None = None
        self._module: Any = None
        self._loaded_at: float | None = None

    # ──────────────────────────────────────────
    # ★ CORRIGÉ : mems() — synchronise les services exposés par le plugin
    # vers le container partagé du PluginManager
    # ──────────────────────────────────────────

    def mems(self) -> dict:
        """
        Propage les services enregistrés par le plugin dans son propre
        self._services vers le container partagé du PluginManager.

        Appelé par le PluginManager après on_load() pour que les
        dépendances de la vague suivante trouvent les services.

        Exemple :
        ```python
            #erp_core.on_load() fait :
            self._services["core"] = CoreService(...)
            #Puis mems() fait :
            PluginManager._services.update({"core": CoreService(...)})
            #erp_auth peut alors faire :
            core = self.get_service("core")  ✓
        ```
        """
        if self._instance is None:
            return self._services

        # Récupère les services ajoutés par le plugin dans son propre container
        instance_services = getattr(self._instance, "_services", {})

        # Propage uniquement les nouvelles clés vers le container partagé
        # (évite d'écraser des services existants d'autres plugins)
        if new_keys := set(instance_services.keys()) - set(self._services.keys()):
            for key in new_keys:
                self._services[key] = instance_services[key]
            logger.info(
                f"[{self.manifest.name}] 📦 Nouveaux services exposés : {sorted(new_keys)}"
            )

        return self._services

    # ──────────────────────────────────────────
    # ★ CORRIGÉ : load() — injecte toujours le container,
    #   puis appelle mems() après on_load()
    # ──────────────────────────────────────────

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

        # ★ CORRECTION 1 : toujours tenter de passer services
        try:
            sig = inspect.signature(plugin_class.__init__)
            accepts_services = "services" in sig.parameters
        except (ValueError, TypeError):
            accepts_services = False

        if accepts_services:
            self._instance = plugin_class(services=self._services)
        else:
            # Le plugin n'accepte pas services dans __init__
            # → on l'instancie normalement puis on injecte le container
            # directement sur l'attribut _services s'il hérite de TrustedBase
            self._instance = plugin_class()
            if hasattr(self._instance, "_services"):
                # TrustedBase : injecter le container partagé
                # IMPORTANT : on remplace l'attribut pour que ce soit
                # le MÊME objet (pas une copie)
                self._instance._services = self._services

        if not isinstance(self._instance, BasePlugin):
            raise TrustedLoadError(
                f"[{self.manifest.name}] Plugin ne respecte pas BasePlugin"
            )

        # Injection des variables d'environnement
        if hasattr(self._instance, "env_variable"):
            await self._instance.env_variable(self.manifest.env)

        # Hook on_load — c'est ici que le plugin enregistre ses services
        # ex: self._services["core"] = CoreService(...)
        if hasattr(self._instance, "on_load"):
            await self._instance.on_load()

        # ★ CORRECTION 2 : appel de mems() APRÈS on_load()
        # Propage les services ajoutés par on_load() vers le container partagé
        self.mems()

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

    # ──────────────────────────────────────────
    # Appel avec timeout (inchangé)
    # ──────────────────────────────────────────

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

    # ──────────────────────────────────────────
    # Filesystem (inchangé)
    # ──────────────────────────────────────────

    def check_path(self, path: str | Path) -> None:
        check_filesystem_access(
            path,
            self.manifest.plugin_dir,
            self.manifest.filesystem,
            self.manifest.name,
        )

    # ──────────────────────────────────────────
    # ★ CORRIGÉ : reload() — appelle mems() après rechargement
    # ──────────────────────────────────────────

    async def reload(self) -> None:
        logger.info(f"[{self.manifest.name}] Rechargement à chaud...")
        if hasattr(self._instance, "on_reload"):
            await self._instance.on_reload()
        await self.unload()
        await self.load()  # load() appelle déjà <-mems() en fin

    # ──────────────────────────────────────────
    # unload (inchangé)
    # ──────────────────────────────────────────

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

    # ──────────────────────────────────────────
    # Status (inchangé)
    # ──────────────────────────────────────────

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
