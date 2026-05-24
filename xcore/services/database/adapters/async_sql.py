"""
async_sql.py — Adaptateur SQLAlchemy asynchrone (aiosqlite, asyncpg, aiomysql…).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, AsyncGenerator

if TYPE_CHECKING:
    from ....configurations.sections import DatabaseConfig

logger = logging.getLogger("xcore.services.database.async_sql")


class AsyncSQLAdapter:
    """
    Adaptateur SQLAlchemy async — optimisé production.

    Paramètres pool configurables depuis xcore.yaml :
        pool_pre_ping        → détecte les connexions mortes avant usage (crucial MySQL)
        pool_recycle         → renouvelle avant le wait_timeout serveur
        pool_timeout         → timeout d'acquisition depuis le pool
        pool_reset_on_return → comportement au retour au pool (rollback/commit/none)
        connect_args         → timeouts driver-level (connect_timeout, read_timeout…)
        isolation_level      → niveau d'isolation transactionnel
        execution_options    → options SQLAlchemy par session

    Usage:
        async with adapter.session() as session:
            result = await session.execute(text("SELECT * FROM users"))
    """

    def __init__(self, name: str, cfg: "DatabaseConfig") -> None:
        self.name = name
        self.url = cfg.url
        self._echo = cfg.echo
        self._pool_pre_ping = getattr(cfg, "pool_pre_ping", True)
        self._pool_recycle = getattr(cfg, "pool_recycle", 1800)
        self._pool_timeout = getattr(cfg, "pool_timeout", 30)
        self._pool_reset_on_return = getattr(cfg, "pool_reset_on_return", "rollback")
        self._connect_args = getattr(cfg, "connect_args", {})
        self._isolation_level = getattr(cfg, "isolation_level", None)
        self._execution_options = getattr(cfg, "execution_options", {})
        self._engine = None
        self._AsyncSession = None

    async def connect(self) -> None:
        try:
            from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
            from sqlalchemy.orm import sessionmaker
        except ImportError as e:
            raise ImportError(
                "sqlalchemy[asyncio] non installé — pip install sqlalchemy[asyncio]"
            ) from e

        engine_kwargs: dict[str, Any] = {
            "echo": self._echo,
            "pool_pre_ping": self._pool_pre_ping,
            "pool_recycle": self._pool_recycle,
            "pool_timeout": self._pool_timeout,
        }

        # connect_args : timeouts driver-level
        if self._connect_args:
            engine_kwargs["connect_args"] = self._connect_args

        # isolation_level au niveau moteur si spécifié
        if self._isolation_level:
            engine_kwargs["isolation_level"] = self._isolation_level

        # SQLite n'a pas de pool configurable (utilise StaticPool)
        if self.url.startswith("sqlite"):
            engine_kwargs.pop("pool_timeout", None)
            engine_kwargs.pop("pool_recycle", None)

        self._engine = create_async_engine(self.url, **engine_kwargs)

        # pool_reset_on_return sur le pool sous-jacent
        if not self.url.startswith("sqlite"):
            self._engine.sync_engine.pool._reset_on_return = self._pool_reset_on_return

        session_kwargs: dict[str, Any] = {
            "bind": self._engine,
            "class_": AsyncSession,
            "expire_on_commit": False,
        }
        if self._execution_options:
            session_kwargs["sync_session_class"] = None  # laisse SQLAlchemy gérer

        self._AsyncSession = sessionmaker(**session_kwargs)

        # Vérification de la connexion au démarrage
        async with self._engine.connect() as conn:
            if self._execution_options:
                await conn.execution_options(**self._execution_options)
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))

        logger.info(
            f"[{self.name}] AsyncSQL connecté "
            f"(pre_ping={self._pool_pre_ping}, recycle={self._pool_recycle}s, "
            f"reset={self._pool_reset_on_return})"
        )

    async def disconnect(self) -> None:
        if self._engine:
            await self._engine.dispose()
            self._engine = None

    @asynccontextmanager
    async def session(self) -> AsyncGenerator:
        if self._AsyncSession is None:
            raise RuntimeError(f"[{self.name}] Base non initialisée")
        async with self._AsyncSession() as sess:
            try:
                if self._execution_options:
                    await sess.connection(execution_options=self._execution_options)
                yield sess
                await sess.commit()
            except Exception:
                # Le rollback peut échouer si la connexion est morte (MySQL wait_timeout).
                # On l'absorbe pour laisser remonter l'exception originale proprement.
                try:
                    await sess.rollback()
                except Exception as rollback_err:
                    logger.warning(
                        f"[{self.name}] Rollback échoué (connexion morte ?) : "
                        f"{rollback_err}"
                    )
                raise

    async def execute(self, sql: str, params: dict | None = None) -> Any:
        if self._engine is None:
            raise RuntimeError(f"[{self.name}] Base non initialisée")
        from sqlalchemy import text

        async with self._engine.connect() as conn:
            return await conn.execute(text(sql), params or {})

    async def ping(self) -> tuple[bool, str]:
        try:
            await self.execute("SELECT 1")
            return True, "ok"
        except Exception as e:
            return False, str(e)

    @property
    def engine(self) -> Any:
        if self._engine is None:
            raise RuntimeError(f"[{self.name}] Base non initialisée")
        return self._engine
