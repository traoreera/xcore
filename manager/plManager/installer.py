import pathlib
import subprocess
import sys

import toml

from manager.tools.error import Error

from . import logger


class Installer:
    """Gère l'installation et la configuration des environnements plugins."""

    def __init__(self):

        super(Installer, self).__init__()

    def __call__(self, path: pathlib.Path):
        logger.info("Installation des plugins")
        return Installer.__install_plugin_env(path)

    @Error.exception_handler  # TODO:try to install requirement with other file
    @staticmethod
    def __install_plugin_env(plugin_path: pathlib.Path) -> dict:
        pyproject_file = plugin_path / "pyproject.toml"

        if pyproject_file.exists():
            try:
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
                    logger.debug(f"Ajout de {site_packages} au sys.path")

            except subprocess.CalledProcessError as e:
                logger.error(f"Erreur d’installation pour {plugin_path.name}")
                logger.exception(e.stdout)
