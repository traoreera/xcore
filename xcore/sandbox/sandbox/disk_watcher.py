"""
sandbox/disk_watcher.py
────────────────────────
Surveillance du quota disque pour les plugins Sandboxed.
Vérifie la taille de data/ avant et après chaque écriture.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("plManager.disk")


class DiskQuotaExceeded(Exception):
    """Levée quand le plugin dépasse son quota disque."""


class DiskWatcher:
    """
    Surveille la taille du répertoire data/ d'un plugin.
    Utilisé dans deux contextes :
        1. Appelé avant une écriture (check préventif)
        2. Vérifié périodiquement par le supervisor
    """

    def __init__(self, data_dir: Path, max_disk_mb: int) -> None:
        self._data_dir    = data_dir
        self._max_bytes   = max_disk_mb * 1024 * 1024
        self._max_disk_mb = max_disk_mb

    def current_size_bytes(self) -> int:
        """Calcule la taille totale de data/ en octets."""
        if not self._data_dir.exists():
            return 0
        return sum(
            f.stat().st_size
            for f in self._data_dir.rglob("*")
            if f.is_file()
        )

    def current_size_mb(self) -> float:
        return round(self.current_size_bytes() / (1024 * 1024), 3)

    def check(self, plugin_name: str) -> None:
        """
        Vérifie que le quota n'est pas dépassé.
        Lève DiskQuotaExceeded si c'est le cas.
        Silencieux si max_disk_mb == 0 (illimité).
        """
        if self._max_bytes == 0:
            return

        current = self.current_size_bytes()
        if current > self._max_bytes:
            raise DiskQuotaExceeded(
                f"Plugin '{plugin_name}' : quota disque dépassé "
                f"({self.current_size_mb():.1f} Mo / {self._max_disk_mb} Mo max). "
                f"Libère de l'espace dans data/."
            )

    def check_write(self, plugin_name: str, estimated_bytes: int = 0) -> None:
        """
        Vérifie qu'une écriture supplémentaire ne dépassera pas le quota.
        estimated_bytes : taille estimée de ce qui va être écrit.
        """
        if self._max_bytes == 0:
            return

        projected = self.current_size_bytes() + estimated_bytes
        if projected > self._max_bytes:
            raise DiskQuotaExceeded(
                f"Plugin '{plugin_name}' : écriture refusée — "
                f"quota disque atteint ({self._max_disk_mb} Mo max)."
            )

    def stats(self) -> dict:
        used = self.current_size_bytes()
        return {
            "used_mb":  self.current_size_mb(),
            "max_mb":   self._max_disk_mb,
            "used_pct": round(used / self._max_bytes * 100, 1) if self._max_bytes else 0,
            "ok":       used <= self._max_bytes if self._max_bytes else True,
        }