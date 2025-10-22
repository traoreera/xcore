import asyncio
import importlib
import json
import pathlib
import pkgutil
import subprocess  # nosec B404
import sys
from typing import Any, Dict, List

import toml

from manager.schemas.plugins import Plugin

from . import get_logger, logging
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
        super().__init__(logger=logger or get_logger(__name__))
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
    # 📦 INSTALL DEPENDANCES
    # ------------------------------------------------------

    def install_plugin_env(self, plugin_path: pathlib.Path, logger=None) -> dict:
        """
        Installe les dépendances via Poetry, configure sys.path pour importlib,
        lit plugin.json et génère requirements.txt.
        Log complet de la sortie de Poetry pour debug.

        Args:
            plugin_path (pathlib.Path): chemin du dossier plugin
            logger: objet logger optionnel

        Returns:
            dict: contenu de plugin.json
        """
        if logger is None:
            import logging

            logger = logging.getLogger(__name__)

        plugin_config_file = plugin_path / "plugin.json"
        pyproject_file = plugin_path / "pyproject.toml"
        requirements_file = plugin_path / "requirements.txt"

        # -----------------------------
        # 1️⃣ Lecture config plugin
        # -----------------------------
        if plugin_config_file.exists():
            with open(plugin_config_file, "r") as f:
                config = json.load(f)
            logger.info(f"🔧 Plugin config chargé pour {plugin_path.name}")
        else:
            config = {}
            logger.warning(f"⚠️ plugin.json manquant pour {plugin_path.name}")

        # -----------------------------
        # 2️⃣ Installer dépendances via Poetry
        # -----------------------------
        if pyproject_file.exists():
            logger.info(
                f"📦 Installation des dépendances pour {plugin_path.name} via Poetry"
            )
            try:
                result = subprocess.run(
                    [
                        "poetry",
                        "install",
                        "--directory",
                        str(plugin_path),
                        "--no-interaction",
                        "--no-root",
                    ],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )  # osec B603 B607
                logger.info(f"📜 Sortie Poetry:\n{result.stdout}")
                logger.info(f"✅ Dépendances installées pour {plugin_path.name}")

                # Ajouter le site-packages au sys.path
                env_result = subprocess.run(
                    [
                        "poetry",
                        "env",
                        "info",
                        "--path",
                        "--directory",
                        str(plugin_path),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )  # osec B603 B607
                venv_path = pathlib.Path(env_result.stdout.strip())
                site_packages = (
                    venv_path
                    / "lib"
                    / f"python{sys.version_info.major}.{sys.version_info.minor}"
                    / "site-packages"
                )
                if site_packages.exists():
                    sys.path.insert(0, str(site_packages))
                    logger.debug(f"✅ Ajout de {site_packages} au sys.path")
                else:
                    logger.warning(
                        f"⚠️ site-packages introuvable pour {plugin_path.name}"
                    )

            except subprocess.CalledProcessError as e:
                logger.error(
                    f"❌ Erreur lors de l'installation des dépendances pour {plugin_path.name}"
                )
                if e.stdout:
                    logger.error(f"📜 Sortie:\n{e.stdout}")
                if e.stderr:
                    logger.error(f"📜 Erreur:\n{e.stderr}")
            except Exception as e:
                logger.exception(f"❌ Erreur inattendue pour {plugin_path.name}: {e}")

        # -----------------------------
        # 3️⃣ Générer requirements.txt depuis pyproject.toml
        # -----------------------------
        if pyproject_file.exists():
            try:
                pyproject_data = toml.load(pyproject_file)
                deps = (
                    pyproject_data.get("tool", {})
                    .get("poetry", {})
                    .get("dependencies", {})
                )
                # Exclure python
                deps = {k: v for k, v in deps.items() if k.lower() != "python"}
                with open(requirements_file, "w") as f:
                    for k, v in deps.items():
                        if isinstance(v, dict) and "version" in v:
                            f.write(f"{k}{v['version']}\n")
                        elif isinstance(v, str):
                            f.write(f"{k}{v}\n")
                logger.info(f"📄 requirements.txt généré pour {plugin_path.name}")
            except Exception as e:
                logger.error(
                    f"❌ Impossible de générer requirements.txt pour {plugin_path.name}: {e}"
                )

        return config

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

    def load_plugins(self) -> List[Any]:
        """Importe et initialise les plugins valides"""
        loaded_plugins = []

        for plugin in self._discover_plugins():
            self._purge_module_cache(plugin["name"])

            try:
                mod = importlib.import_module(plugin["module"])
            except Exception as e:
                self.logger.error(f"Import échoué {plugin['name']}: {e}")
                continue

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

            if not self.validator.valdiate(mod):
                continue

            response = self.install_plugin_env(
                pathlib.Path(plugin["path"]), logger=self.logger
            )

            loaded_plugins.append(mod)

        return loaded_plugins

    # TODO: gere les taches asynchrones ultérieurement
    # ------------------------------------------------------
    # ⚡ EXECUTION ASYNCHRONE
    # ------------------------------------------------------
    async def _run_plugin_async(self, mod: Any, app: Any = None) -> None:
        """Exécute la tâche du plugin en async si supporté"""
        try:
            instance = mod.Plugin()
            if asyncio.iscoroutinefunction(instance.concured):
                mod.router.to_app(app)
                await instance.concured()
            else:
                # exécution synchrone dans un thread séparé
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, instance.concured)
            self.logger.info(f" Plugin {mod.__name__} exécuté")
        except Exception as e:
            self.logger.exception(f"Erreur exécution plugin {mod.__name__}: {e}")

    async def run_async_plugins(self, app: Any = None):
        """Exécute tous les plugins actifs en parallèle"""
        plugins = self.load_plugins()
        tasks = [self._run_plugin_async(mod, app) for mod in plugins]

        if not tasks:
            self.logger.warning("Aucun plugin actif à exécuter.")
            return

        await asyncio.gather(*tasks)
        self.logger.info("🚀 Tous les plugins exécutés.")

    def close_db(
        self,
    ):

        self.db.close_db()
