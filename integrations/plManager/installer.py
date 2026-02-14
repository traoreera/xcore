import pathlib
import subprocess
import sys

from ..tools.error import Error

from . import logger


class Installer:
    """Gère l'installation et la configuration des environnements plugins."""

    def __call__(self, path: pathlib.Path) -> dict:
        logger.info("Installation des plugins")
        return Installer.__install_plugin_env(path)

    @staticmethod
    def __find_site_packages(env_path: pathlib.Path) -> pathlib.Path | None:
        # Linux/macOS (venv classique)
        linux_site_packages = (
            env_path
            / "lib"
            / f"python{sys.version_info.major}.{sys.version_info.minor}"
            / "site-packages"
        )
        if linux_site_packages.exists():
            return linux_site_packages

        # Windows
        windows_site_packages = env_path / "Lib" / "site-packages"
        if windows_site_packages.exists():
            return windows_site_packages

        # Fallback: si la version Python diffère, on prend le premier match valide
        return next(
            (
                candidate
                for candidate in sorted(
                    (env_path / "lib").glob("python*/site-packages")
                )
                if candidate.exists()
            ),
            None,
        )

    @Error.exception_handler
    @staticmethod
    def __install_plugin_env(plugin_path: pathlib.Path) -> dict:
        pyproject_file = plugin_path / "pyproject.toml"
        if not pyproject_file.exists():
            logger.info(f"Aucun pyproject.toml trouvé pour {plugin_path.name}, ignoré.")
            return {"installed": False, "reason": "missing_pyproject"}

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

        except FileNotFoundError:
            logger.error("Poetry est introuvable. Installe Poetry puis réessaie.")
            return {"installed": False, "reason": "poetry_not_found"}
        except subprocess.CalledProcessError as exc:
            logger.error(f"Erreur d'installation pour {plugin_path.name}")
            if exc.stderr:
                logger.error(exc.stderr.strip())
            elif exc.stdout:
                logger.error(exc.stdout.strip())
            return {"installed": False, "reason": "poetry_command_failed"}

        if not env_path:
            logger.error(
                f"Impossible de récupérer le venv Poetry pour {plugin_path.name}"
            )
            return {"installed": False, "reason": "missing_env_path"}

        site_packages = Installer.__find_site_packages(pathlib.Path(env_path))
        if site_packages is None:
            logger.warning(f"site-packages introuvable pour {plugin_path.name}")
            return {
                "installed": True,
                "env_path": env_path,
                "site_packages_added": False,
            }

        site_packages_str = str(site_packages)
        if site_packages_str not in sys.path:
            sys.path.insert(0, site_packages_str)
            logger.debug(f"Ajout de {site_packages} au sys.path")
        else:
            logger.debug(f"{site_packages} est déjà présent dans sys.path")

        return {
            "installed": True,
            "env_path": env_path,
            "site_packages": site_packages_str,
            "site_packages_added": True,
        }
