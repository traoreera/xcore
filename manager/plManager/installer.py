import json
import pathlib
import subprocess
import sys

import toml

from . import logger


class Installer:
    """Gère l'installation et la configuration des environnements plugins."""

    def __init__(self):
        pass

    def install_plugin_env(self, plugin_path: pathlib.Path) -> dict:
        plugin_config_file = plugin_path / "plugin.json"
        pyproject_file = plugin_path / "pyproject.toml"
        requirements_file = plugin_path / "requirements.txt"

        config = {}
        if plugin_config_file.exists():
            config = json.loads(plugin_config_file.read_text())
            logger.info(f"🔧 Config chargée pour {plugin_path.name}")
        else:
            logger.warning(f"⚠️ plugin.json manquant pour {plugin_path.name}")

        if pyproject_file.exists():
            try:
                logger.info(f"📦 Installation des dépendances pour {plugin_path.name}")
                subprocess.run(
                    [
                        "poetry",
                        "install",
                        "--directory",
                        str(plugin_path),
                        "--no-interaction",
                        "--no-root",
                    ],
                    check=True,
                    text=True,
                    capture_output=True,
                )
                env_path = subprocess.run(
                    [
                        "poetry",
                        "env",
                        "info",
                        "--path",
                        "--directory",
                        str(plugin_path),
                    ],
                    check=True,
                    text=True,
                    capture_output=True,
                ).stdout.strip()

                site_packages = (
                    pathlib.Path(env_path)
                    / "lib"
                    / f"python{sys.version_info.major}.{sys.version_info.minor}"
                    / "site-packages"
                )
                if site_packages.exists():
                    sys.path.insert(0, str(site_packages))
                    logger.debug(f"✅ Ajout de {site_packages} au sys.path")

            except subprocess.CalledProcessError as e:
                logger.error(
                    f"❌ Erreur d’installation pour {plugin_path.name}: {e.stdout}"
                )

        if pyproject_file.exists():
            try:
                data = toml.load(pyproject_file)
                deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
                deps.pop("python", None)
                with open(requirements_file, "w") as f:
                    for k, v in deps.items():
                        if isinstance(v, dict):
                            f.write(f"{k}{v.get('version', '')}\n")
                        else:
                            f.write(f"{k}{v}\n")
                logger.info(f"📄 requirements.txt généré pour {plugin_path.name}")
            except Exception as e:
                logger.error(f"❌ Impossible de générer requirements.txt : {e}")

        return config
