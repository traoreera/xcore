"""
manager.py — Gestionnaire multi-BDD.

Route vers l'adaptateur approprié selon le type déclaré dans la config :
  sqlite / postgresql / mysql  → SQLAdapter (SQLAlchemy sync)
  sqlite+aio / postgresql+aio  → AsyncSQLAdapter (SQLAlchemy async)
  mongodb                      → MongoDBAdapter (Motor)
  redis                        → RedisAdapter
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...configurations.sections import DatabaseConfig

from ..base import BaseService, ServiceStatus

logger = logging.getLogger("xcore.services.database")

_TYPE_MAP = {
    "sqlite": "sql",
    "postgresql": "sql",
    "mysql": "sql",
    "sqlite+aio": "async_sql",
    "postgresql+aio": "async_sql",
    "sqlasync": "async_sql",
    "mongodb": "mongodb",
    "redis": "redis",
}


class DatabaseManager(BaseService):
    name = "database"

    def __init__(self, configs: dict[str, "DatabaseConfig"]) -> None:
        super().__init__()
        self._configs = configs
        self.adapters: dict[str, Any] = {}

    async def init(self) -> None:
        self._status = ServiceStatus.INITIALIZING
        for name, cfg in self._configs.items():
            adapter = self._build_adapter(name, cfg)
            try:
                await adapter.connect()
                self.adapters[name] = adapter
                logger.info(f"[database:{name}] ✅ {cfg.type} → {cfg.url[:40]}…")
            except Exception as e:
                logger.error(f"[database:{name}] ❌ connexion échouée : {e}")
                # Ne bloque pas les autres connexions
        self._status = ServiceStatus.READY

    def _build_adapter(self, name: str, cfg: "DatabaseConfig"):
        kind = _TYPE_MAP.get(cfg.type.lower())
        if kind == "sql":
            from .adapters.sql import SQLAdapter

            return SQLAdapter(name, cfg)
        if kind == "async_sql":
            from .adapters.async_sql import AsyncSQLAdapter

            return AsyncSQLAdapter(name, cfg)
        if kind == "mongodb":
            from .adapters.mongodb import MongoDBAdapter

            return MongoDBAdapter(name, cfg)
        if kind == "redis":
            from .adapters.redis import RedisAdapter

            return RedisAdapter(name, cfg)
        raise ValueError(
            f"Type BDD inconnu : '{cfg.type}'. " f"Valeurs : {sorted(_TYPE_MAP.keys())}"
        )

    async def shutdown(self) -> None:
        for name, adapter in self.adapters.items():
            try:
                await adapter.disconnect()
                logger.info(f"[database:{name}] déconnecté")
            except Exception as e:
                logger.error(f"[database:{name}] erreur déconnexion : {e}")
        self.adapters.clear()
        self._status = ServiceStatus.STOPPED

    async def health_check(self) -> tuple[bool, str]:
        if not self.adapters:
            return True, "No databases configured"
        results = []
        for name, adapter in self.adapters.items():
            ok, msg = await adapter.ping()
            results.append(f"{name}:{'ok' if ok else msg}")
        all_ok = all("ok" in r for r in results)
        return all_ok, " | ".join(results)

    def status(self) -> dict:
        return {
            "name": self.name,
            "status": self._status.value,
            "connections": {
                name: getattr(a, "url", "?")[:40] for name, a in self.adapters.items()
            },
        }
