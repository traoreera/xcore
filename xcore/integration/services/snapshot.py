"""
Snapshot Service — détection de changements dans un dossier.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Dict, Set

from ..config.loader import PluginsConfig

logger = logging.getLogger("integrations.snapshot")


class SnapshotService:
    def __init__(self, config: PluginsConfig):
        snap = config.snapshot
        self.ignore_hidden: bool = snap.get("hidden", True)
        self.ignore_ext: Set[str] = set(snap.get("extensions", [".pyc", ".pyo"]))
        self.ignore_file: Set[str] = set(snap.get("filenames", ["__pycache__"]))

    def _should_ignore(self, path: Path) -> bool:
        if self.ignore_hidden and path.name.startswith("."):
            return True
        if path.suffix in self.ignore_ext:
            return True
        return path.name in self.ignore_file

    def _hash_file(self, path: Path) -> str:
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()

    def create(self, directory: str | Path) -> Dict[str, str]:
        """Crée un snapshot du contenu d'un dossier (chemin → hash)."""
        directory = Path(directory)
        snapshot = {}
        if not directory.exists():
            return snapshot

        for root, _, files in os.walk(directory):
            for file in files:
                path = Path(root) / file
                if self._should_ignore(path):
                    continue
                try:
                    snapshot[str(path)] = self._hash_file(path)
                except Exception as e:
                    logger.debug(f"Impossible de hacher '{path}': {e}")
        return snapshot

    def diff(self, old: Dict[str, str], new: Dict[str, str]) -> Dict[str, Set[str]]:
        old_keys, new_keys = set(old), set(new)
        return {
            "added": new_keys - old_keys,
            "removed": old_keys - new_keys,
            "modified": {f for f in old_keys & new_keys if old[f] != new[f]},
        }

    def has_changed(self, old: Dict[str, str], new: Dict[str, str]) -> bool:
        d = self.diff(old, new)
        return bool(d["added"] or d["removed"] or d["modified"])
