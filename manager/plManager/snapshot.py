import hashlib
import os
from pathlib import Path
from typing import Dict, Set

from manager.tools.error import Error

from ..conf import cfg
from . import logger


class Snapshot:
    """
    Capture et compare l’état d’un dossier de plugins.
    Utilisé par le Plugin Manager pour détecter les changements
    et déclencher le rechargement dynamique.
    """

    def __init__(
        self,
        ignore_hidden: bool | None = None,
        ignore_ext: Set[str] | None = None,
        ignore_file: Set[str] | None = None,
    ):
        self.ignore_hidden = ignore_hidden or cfg.custom_config["snapshot"]["hidden"]
        self.ignore_ext = ignore_ext or cfg.custom_config["snapshot"]["extensions"]
        self.ignore_file = ignore_file or cfg.custom_config["snapshot"]["filenames"]

    # ------------------------------------------------------------
    def _hash_file(self, path: Path) -> str:
        """Retourne un hash SHA256 pour un fichier."""
        try:
            hasher = hashlib.sha256()
            with open(path, "rb") as f:
                while chunk := f.read(8192):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            logger.warning(f"⚠️ Impossible de hacher {path}: {e}")
            return "ERROR"

    # ------------------------------------------------------------

    def _should_ignore(self, path: Path) -> bool:
        """Détermine si un fichier ou dossier doit être ignoré."""
        if self.ignore_hidden and path.name.startswith("."):
            return True
        if path.suffix in self.ignore_ext:
            return True
        if path.name in self.ignore_file:
            return True
        return False

    # ------------------------------------------------------------

    def create(self, directory: str | Path) -> Dict[str, str]:
        """Crée un snapshot du contenu d’un dossier."""
        directory = Path(directory)
        snapshot = {}

        if not directory.exists():
            logger.warning(f"⚠️ Dossier inexistant: {directory}")
            return snapshot

        for root, _, files in os.walk(directory):
            for file in files:
                path = Path(root) / file
                if self._should_ignore(path):
                    continue
                try:
                    snapshot[str(path)] = self._hash_file(path)
                except Exception as e:
                    logger.error(f"Erreur analyse {path}: {e}")
        return snapshot

    # ------------------------------------------------------------

    def diff(self, old: Dict[str, str], new: Dict[str, str]) -> Dict[str, Set[str]]:
        """Compare deux snapshots et retourne les changements détectés."""
        old_keys, new_keys = set(old.keys()), set(new.keys())

        added = new_keys - old_keys
        removed = old_keys - new_keys
        modified = {f for f in old_keys & new_keys if old[f] != new[f]}

        diff = {"added": added, "removed": removed, "modified": modified}

        if added or removed or modified:
            logger.info(
                f"🌀 Changement détecté → {len(added)} ajout(s), {len(removed)} suppression(s), {len(modified)} modif(s)"
            )

        return diff

    # ------------------------------------------------------------

    def has_changed(self, old: Dict[str, str], new: Dict[str, str]) -> bool:
        """Renvoie True si le snapshot a changé."""
        d = self.diff(old, new)
        return bool(d["added"] or d["removed"] or d["modified"])

    def __call__(self, directory: str | Path) -> Dict[str, Set[str]]:
        return self.diff(self.create(directory), self.create(directory))
