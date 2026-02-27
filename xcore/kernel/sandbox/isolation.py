"""
isolation.py — Isolation des ressources disque et mémoire pour les subprocess Sandboxed.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("xcore.sandbox.isolation")


class DiskQuotaExceeded(Exception):
    pass


class DiskWatcher:
    """Surveille le quota disque d'un plugin sandboxed."""

    def __init__(self, data_dir: Path, max_disk_mb: int) -> None:
        self._data_dir = data_dir
        self._max_bytes = max_disk_mb * 1024 * 1024
        self._max_disk_mb = max_disk_mb

    def current_size_bytes(self) -> int:
        if not self._data_dir.exists():
            return 0
        return sum(f.stat().st_size for f in self._data_dir.rglob("*") if f.is_file())

    def current_size_mb(self) -> float:
        return round(self.current_size_bytes() / (1024 * 1024), 3)

    def check(self, plugin_name: str) -> None:
        if self._max_bytes == 0:
            return
        if self.current_size_bytes() > self._max_bytes:
            raise DiskQuotaExceeded(
                f"Plugin '{plugin_name}' : quota disque dépassé "
                f"({self.current_size_mb():.1f}MB / {self._max_disk_mb}MB max)"
            )

    def stats(self) -> dict:
        used = self.current_size_bytes()
        return {
            "used_mb": self.current_size_mb(),
            "max_mb": self._max_disk_mb,
            "used_pct": (
                round(used / self._max_bytes * 100, 1) if self._max_bytes else 0
            ),
            "ok": used <= self._max_bytes if self._max_bytes else True,
        }


class MemoryLimiter:
    """Applique RLIMIT_AS dans un subprocess (doit être appelé DANS le subprocess)."""

    @staticmethod
    def apply(max_mb: int) -> None:
        if max_mb <= 0:
            return
        import sys

        if sys.platform == "win32":
            logger.warning("Limite mémoire non supportée sous Windows")
            return
        try:
            import resource

            limit = max_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
        except Exception as e:
            logger.warning(f"Impossible d'appliquer la limite mémoire : {e}")
