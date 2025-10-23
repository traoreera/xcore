import asyncio
import importlib
import pathlib
import pkgutil
import sys
from typing import Any, Dict, List

from manager.schemas.plugins import Plugin
from manager.tools.error import Error

from . import logging
from .installer import Installer
from .repository import Repository
from .validator import Validator

# ============================================================================


class Loader(Repository):
    """Chargeur et exécuteur asynchrone des plugins"""

    def __init__(
        self,
        directory: str = "plugins",
        entry_point: str = "run",
        logger: logging.Logger | None = None,
        app: Any = None,
    ) -> None:
        super().__init__(logger=logger or logger)
        self.plugin_dir = pathlib.Path(directory)
        self.entry_point = entry_point
        self.active_plugins = self.get_all_active()
        self.validator = Validator()
        self.app = app

    # ------------------------------------------------------
    # 🔄 PURGE CACHE
    # ------------------------------------------------------

    def _purge_module_cache(self, base_name: str, dry_run: bool = False) -> None:
        """Nettoie sys.modules pour permettre un rechargement propre"""
        relative_name = f"{self.plugin_dir}.{base_name}"
        to_remove = [
            m
            for m in list(sys.modules)
            if m.startswith(f"{self.plugin_dir.name}.{base_name}")
            and not m.startswith(f"{relative_name}.models")
        ]

        if dry_run:
            self.logger.info(f"[DryRun] Modules qui seraient purgés: {to_remove}")
            return

        for m in to_remove:
            del sys.modules[m]
        if to_remove:
            self.logger.debug(f"🧹 {len(to_remove)} modules purgés pour {base_name}")

    # ------------------------------------------------------
    # 🔍 DISCOVERY
    # ------------------------------------------------------

    def _discover_plugins(self) -> List[Dict[str, str]]:
        if not self.plugin_dir.exists():
            self.logger.warning(f"⚠️ Dossier introuvable: {self.plugin_dir}")
            return []

        discovered = []
        for _, name, _ in pkgutil.iter_modules([str(self.plugin_dir)]):
            discovered.append(
                {
                    "name": name,
                    "module": f"{self.plugin_dir.name}.{name}.{self.entry_point}",
                    "path": str(self.plugin_dir / name),
                }
            )
        return discovered

    # ------------------------------------------------------
    # 🔌 CHARGEMENT
    # ------------------------------------------------------

    @Error.exception_handler
    def load_plugins(self) -> List[Any]:
        """Importe et initialise les plugins valides"""
        loaded_plugins = []

        for plugin in self._discover_plugins():
            self._purge_module_cache(plugin["name"])
            mod = importlib.import_module(plugin["module"])

            if not any(p["name"] == plugin["name"] for p in self.active_plugins):
                self.add(
                    plugin=Plugin(
                        name=plugin["name"],
                        version=getattr(mod, "PLUGIN_INFO", {}).get(
                            "version", "unknown"
                        ),
                        author=getattr(mod, "PLUGIN_INFO", {}).get("author", "unknown"),
                        Api_prefix=getattr(mod, "PLUGIN_INFO", {}).get(
                            "Api_prefix", "/app/" + plugin["name"]
                        ),
                        tag_for_identified=f"{getattr(mod, "PLUGIN_INFO", {}).get("tag_for_identified", [])}",
                    )
                )
                loaded_plugins.append(mod)
                continue

            if not Validator()(mod):
                continue

            response = Installer()(path=pathlib.Path(plugin["path"]))
            loaded_plugins.append(mod)

        return loaded_plugins

    # TODO: gere les taches asynchrones ultérieurement
    # ------------------------------------------------------
    # ⚡ EXECUTION ASYNCHRONE
    # ------------------------------------------------------

    @Error.exception_handler
    async def _run_plugin_async(self, mod: Any, app: Any = None) -> None:
        """Exécute la tâche du plugin en async si supporté"""

        instance = mod.Plugin()
        if asyncio.iscoroutinefunction(instance.concured):
            mod.router.to_app(app)
            await instance.concured()
        else:
            # exécution synchrone dans un thread séparé
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, instance.concured)
        self.logger.info(f" Plugin {mod.__name__} exécuté")

    async def run_async_plugins(self, app: Any = None):
        """Exécute tous les plugins actifs en parallèle"""
        plugins = self.load_plugins()
        tasks = [self._run_plugin_async(mod, app) for mod in plugins]

        if not tasks:
            self.logger.warning("Aucun plugin actif à exécuter.")
            return

        await asyncio.gather(*tasks)
        self.logger.info("🚀 Tous les plugins exécutés.")

    @Error.exception_handler
    def close_db(
        self,
    ):

        self.db.close_db()
