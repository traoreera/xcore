"""
mongodb.py — Adaptateur MongoDB via Motor (asyncio).
"""
from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ....configurations.sections import DatabaseConfig

logger = logging.getLogger("xcore.services.database.mongodb")


class MongoDBAdapter:
    """
    Adaptateur MongoDB asynchrone via Motor.

    Usage:
        collection = adapter.collection("users")
        await collection.insert_one({"name": "alice"})
        docs = await collection.find({"name": "alice"}).to_list(100)
    """

    def __init__(self, name: str, cfg: "DatabaseConfig") -> None:
        self.name     = name
        self.url      = cfg.url
        self._db_name = cfg.database or "xcore"
        self._max_connections = cfg.max_connections or 100
        self._client = None
        self._db     = None

    async def connect(self) -> None:
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
        except ImportError as e:
            raise ImportError("motor non installé — pip install motor") from e

        self._client = AsyncIOMotorClient(
            self.url,
            maxPoolSize=self._max_connections,
            serverSelectionTimeoutMS=5000,
        )
        self._db = self._client[self._db_name]
        # Vérification connexion
        await self._client.admin.command("ping")
        logger.info(f"[{self.name}] MongoDB connecté → {self._db_name}")

    async def disconnect(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
            self._db     = None

    def collection(self, name: str):
        if self._db is None:
            raise RuntimeError(f"[{self.name}] MongoDB non initialisé")
        return self._db[name]

    def database(self):
        if self._db is None:
            raise RuntimeError(f"[{self.name}] MongoDB non initialisé")
        return self._db

    async def ping(self) -> tuple[bool, str]:
        try:
            await self._client.admin.command("ping")
            return True, "ok"
        except Exception as e:
            return False, str(e)
