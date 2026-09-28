"""
state_store.py — Table de vérité persistante pour l'état actif/inactif des plugins.

Contrairement au registre en mémoire (PluginRegistry), cet état survit aux
redémarrages : un plugin désactivé via `PluginSupervisor.disable()` reste
désactivé après un restart du process, car `PluginLoader.load_all()` le
consulte avant de charger quoi que ce soit.

Stockage : un unique fichier JSON, écrit de façon atomique (fichier temporaire
+ remplacement) pour éviter toute corruption en cas de crash pendant l'écriture.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from ..kernel.observability import get_logger

logger = get_logger("xcore.registry.state_store")


class PluginStateStore:
    """
    Table de vérité `nom_plugin -> {enabled, reason, updated_at}`.

    Usage:
        store = PluginStateStore(Path("plugins").parent / ".xcore" / "plugins_state.json")
        store.is_enabled("shop")            # True par défaut si jamais togglé
        store.set_enabled("shop", False, reason="maintenance")
        store.all()
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._data: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            self._data = json.loads(self._path.read_text(encoding="utf-8")) or {}
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(
                "plugin state file unreadable, starting empty",
                path=str(self._path),
                error=str(e),
            )
            self._data = {}

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._path.with_suffix(f"{self._path.suffix}.tmp")
        tmp_path.write_text(
            json.dumps(self._data, indent=2, sort_keys=True), encoding="utf-8"
        )
        os.replace(tmp_path, self._path)

    def is_enabled(self, name: str, default: bool = True) -> bool:
        entry = self._data.get(name)
        return default if entry is None else bool(entry.get("enabled", default))

    def set_enabled(self, name: str, enabled: bool, reason: str | None = None) -> None:
        self._data[name] = {
            "enabled": enabled,
            "reason": reason,
            "updated_at": time.time(),
        }
        self._persist()
        logger.info(
            "plugin state persisted", plugin=name, enabled=enabled, reason=reason
        )

    def all(self) -> dict[str, dict[str, Any]]:
        return dict(self._data)
