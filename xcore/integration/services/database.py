"""
Database Manager — gère plusieurs connexions BDD depuis la config YAML.
Supporte SQLite, PostgreSQL, MySQL (SQLAlchemy), MongoDB, Redis.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, contextmanager
from typing import Any, Dict, Iterator, Optional

from sqlalchemy.pool import NullPool, StaticPool

from ..config.loader import DatabaseConfig, IntegrationConfig

logger = logging.getLogger("integrations.database")


# ─────────────────────────────────────────────────────────────
# Adaptateurs par type de BDD
# ─────────────────────────────────────────────────────────────


class SQLAdapter:
    """SQLAlchemy — SQLite / PostgreSQL / MySQL"""

    def __init__(self, cfg: DatabaseConfig):
        self.cfg = cfg
        self._engine = None
        self._session_factory = None

    def init(self):
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker

            self._engine = create_engine(
                self.cfg.url,
                pool_size=self.cfg.pool_size,
                max_overflow=self.cfg.max_overflow,
                echo=self.cfg.echo,
            )
            self._session_factory = sessionmaker(
                bind=self._engine, autocommit=False, autoflush=False
            )
            logger.info(f"[DB:{self.cfg.name}] Connexion SQL établie ({self.cfg.type})")
        except ImportError:
            logger.error("SQLAlchemy non installé. Exécutez: pip install sqlalchemy")
            raise

    @contextmanager
    def session(self):
        if not self._session_factory:
            self.init()
        db = self._session_factory()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @property
    def engine(self):
        if not self._engine:
            self.init()
        return self._engine

    def create_all(self, base):
        """Crée toutes les tables depuis les modèles SQLAlchemy."""
        base.metadata.create_all(self._engine)

    def close(self):
        if self._engine:
            self._engine.dispose()
            logger.info(f"[DB:{self.cfg.name}] Connexion SQL fermée")


class AsyncSQLAdapter:
    """SQLAlchemy async — PostgreSQL (asyncpg) / MySQL (aiomysql)"""

    def __init__(self, cfg: DatabaseConfig):
        self.cfg = cfg
        self._engine = None
        self._session_factory = None

    async def init(self):
        if self._engine:
            return
        try:
            from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
            from sqlalchemy.orm import sessionmaker

            if "sqlite" in self.cfg.url:
                self._engine = create_async_engine(
                    self.cfg.url,
                    poolclass=NullPool,
                    echo=self.cfg.echo,
                )
            self._engine = create_async_engine(
                self.cfg.url,
                pool_size=self.cfg.pool_size,
                max_overflow=self.cfg.max_overflow,
                echo=self.cfg.echo,
            )
            self._session_factory = sessionmaker(
                bind=self._engine, class_=AsyncSession, expire_on_commit=False
            )
            logger.info(f"[DB:{self.cfg.name}] Connexion async SQL établie")
        except ImportError:
            logger.error("sqlalchemy[asyncio] non installé.")
            raise

    @property
    def engine(self):
        """Retourne l'engine async. Doit être appelé après init()."""
        if not self._engine:
            raise RuntimeError(
                f"[DB:{self.cfg.name}] Engine non initialisé. "
                "Appelez await db_manager.init_all() d'abord."
            )
        return self._engine

    @asynccontextmanager
    async def session(self):
        if not self._session_factory:
            await self.init()
        async with self._session_factory() as db:
            try:
                yield db
                await db.commit()
            except Exception:
                await db.rollback()
                raise

    async def close(self):
        if self._engine:
            await self._engine.dispose()
            logger.info(f"[DB:{self.cfg.name}] Connexion async SQL fermée")


class RedisAdapter:
    """Redis — cache, queues, pub/sub"""

    def __init__(self, cfg: DatabaseConfig):
        self.cfg = cfg
        self._client = None

    def init(self):
        try:
            import redis

            self._client = redis.from_url(
                self.cfg.url,
                max_connections=self.cfg.max_connections or 20,
                decode_responses=True,
            )
            self._client.ping()
            logger.info(f"[DB:{self.cfg.name}] Connexion Redis établie")
        except ImportError:
            logger.error("redis-py non installé. Exécutez: pip install redis")
            raise

    @property
    def client(self):
        if not self._client:
            self.init()
        return self._client

    def close(self):
        if self._client:
            self._client.connection_pool.disconnect()
            logger.info(f"[DB:{self.cfg.name}] Connexion Redis fermée")


class MongoAdapter:
    """MongoDB via pymongo"""

    def __init__(self, cfg: DatabaseConfig):
        self.cfg = cfg
        self._client = None

    def init(self):
        try:
            from pymongo import MongoClient

            self._client = MongoClient(self.cfg.url)
            self._client.admin.command("ping")
            logger.info(f"[DB:{self.cfg.name}] Connexion MongoDB établie")
        except ImportError:
            logger.error("pymongo non installé. Exécutez: pip install pymongo")
            raise

    def db(self, name: Optional[str] = None):
        if not self._client:
            self.init()
        return self._client[name or self.cfg.database or "default"]

    def close(self):
        if self._client:
            self._client.close()
            logger.info(f"[DB:{self.cfg.name}] Connexion MongoDB fermée")


# ─────────────────────────────────────────────────────────────
# Manager principal
# ─────────────────────────────────────────────────────────────

_ADAPTER_MAP = {
    "sqlite": SQLAdapter,
    "postgresql": SQLAdapter,
    "mysql": SQLAdapter,
    "redis": RedisAdapter,
    "mongodb": MongoAdapter,
    "sqlasync": AsyncSQLAdapter,
}


class DatabaseManager:
    """
    Gestionnaire multi-BDD. Initialise les connexions depuis la config YAML.

    Usage:
        db_manager = DatabaseManager(config)
        await db_manager.init_all()

        # Session SQL synchrone
        with db_manager.session("default") as db:
            db.query(User).all()

        # Session SQL asynchrone
        async with db_manager.async_session("pg") as db:
            await db.execute(...)

        # Accès à un adaptateur spécifique
        redis = db_manager.get("cache")
        redis.client.set("key", "value")
    """

    def __init__(self, config: IntegrationConfig):
        self._config = config
        self._adapters: Dict[str, Any] = {}

    async def init_all(self):
        """Initialise toutes les connexions configurées."""
        for name, db_cfg in self._config.databases.items():
            adapter_cls = _ADAPTER_MAP.get(db_cfg.type)
            if adapter_cls is None:
                logger.warning(f"[DB] Type inconnu: {db_cfg.type} pour {name}")
                continue
            try:
                adapter = adapter_cls(db_cfg)
                # FIX: asyncio.iscoroutinefunction détecte correctement les méthodes async
                if asyncio.iscoroutinefunction(adapter.init):
                    await adapter.init()
                else:
                    adapter.init()
                self._adapters[name] = adapter
            except Exception as e:
                logger.error(f"[DB:{name}] Échec initialisation: {e}")

    def get(self, name: str = "default") -> Any:
        """Retourne l'adaptateur BDD par nom."""
        if name not in self._adapters:
            raise KeyError(
                f"Base de données '{name}' non trouvée ou non initialisée. "
                f"Disponibles: {list(self._adapters.keys())}"
            )
        return self._adapters[name]

    @contextmanager
    def session(self, name: str = "default") -> Iterator:
        """Context manager pour une session SQL synchrone."""
        adapter = self.get(name)
        if not isinstance(adapter, SQLAdapter):
            raise TypeError(
                f"'{name}' n'est pas une base SQL synchrone. "
                f"Utilisez async_session() pour AsyncSQLAdapter."
            )
        with adapter.session() as db:
            yield db

    @asynccontextmanager
    async def async_session(self, name: str = "default"):
        """Context manager pour une session SQL asynchrone."""
        adapter = self.get(name)
        if not isinstance(adapter, AsyncSQLAdapter):
            raise TypeError(
                f"'{name}' n'est pas une base SQL asynchrone. "
                f"Utilisez session() pour SQLAdapter."
            )
        async with adapter.session() as db:
            yield db

    async def close_all(self):
        """Ferme toutes les connexions. Doit être appelé avec await."""
        for name, adapter in self._adapters.items():
            try:
                if asyncio.iscoroutinefunction(adapter.close):
                    await adapter.close()
                else:
                    adapter.close()
            except Exception as e:
                logger.error(f"[DB:{name}] Erreur fermeture: {e}")
        self._adapters.clear()
        logger.info("Toutes les connexions BDD fermées.")

    def __repr__(self):
        return f"<DatabaseManager dbs={list(self._adapters.keys())}>"
