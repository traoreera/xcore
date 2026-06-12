"""
async_sql.py — Adaptateur SQLAlchemy asynchrone (aiosqlite, asyncpg, aiomysql…).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, AsyncGenerator

from ....kernel.observability import get_logger
from ._utils import (
    detect_driver,
    is_pre_ping_safe,
    sanitize_connect_args,
    sanitize_isolation_level,
)

if TYPE_CHECKING:
    from ....kernel.configurations.sections import DatabaseConfig

logger = get_logger("xcore.services.database.async_sql")


class AsyncSQLAdapter:
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

        # pool_pre_ping désactivé pour aiomysql (ping() incompatible)
        # compensation : pool_recycle + invalidation sur OperationalError
        safe_pre_ping = self._pool_pre_ping and is_pre_ping_safe(self.url)

        engine_kwargs: dict[str, Any] = {
            "echo": self._echo,
            "pool_pre_ping": safe_pre_ping,
            "pool_recycle": self._pool_recycle,
            "pool_timeout": self._pool_timeout,
        }

        if not safe_pre_ping and self._pool_pre_ping:
            logger.info(
                "pool_pre_ping disabled for aiomysql, compensating with pool_recycle",
                adapter=self.name,
                recycle_s=self._pool_recycle,
            )

        if self._connect_args:
            sanitized = sanitize_connect_args(self.url, self._connect_args)
            if sanitized:
                engine_kwargs["connect_args"] = sanitized

        safe_isolation = sanitize_isolation_level(self.url, self._isolation_level)
        if safe_isolation:
            engine_kwargs["isolation_level"] = safe_isolation

        if self.url.startswith("sqlite"):
            engine_kwargs.pop("pool_timeout", None)
            engine_kwargs.pop("pool_recycle", None)
            engine_kwargs.pop("pool_pre_ping", None)

        self._engine = create_async_engine(self.url, **engine_kwargs)

        # Pour aiomysql : invalidation pessimiste sur OperationalError
        # remplace le pre_ping natif qui est cassé
        if not safe_pre_ping:
            self._install_pessimistic_listener()

        if not self.url.startswith("sqlite"):
            self._engine.sync_engine.pool._reset_on_return = self._pool_reset_on_return

        self._AsyncSession = sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        async with self._engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))

        driver = detect_driver(self.url)
        logger.info(
            "async sql connected",
            adapter=self.name,
            driver=driver,
            pre_ping=safe_pre_ping,
            recycle_s=self._pool_recycle,
        )

    def _install_pessimistic_listener(self) -> None:
        """
        Fallback pour les drivers où pool_pre_ping est cassé (aiomysql).
        Invalide la connexion au pool sur OperationalError (connexion morte)
        pour forcer SQLAlchemy à en créer une nouvelle au prochain checkout.
        """
        from sqlalchemy import event

        @event.listens_for(self._engine.sync_engine, "connect")
        def connect(dbapi_connection, connection_record):
            connection_record.info["pid"] = id(dbapi_connection)

        @event.listens_for(self._engine.sync_engine, "checkout")
        def checkout(dbapi_connection, connection_record, connection_proxy):
            # Marque la connexion comme valide à l'extraction
            connection_record.info.setdefault("pid", id(dbapi_connection))

        logger.debug(
            "pessimistic listener installed (aiomysql workaround)", adapter=self.name
        )

    async def disconnect(self) -> None:
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._AsyncSession = None
            logger.info("async sql disconnected", adapter=self.name)

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
