"""
async_sql.py — Adaptateur SQLAlchemy asynchrone (aiosqlite, asyncpg…).
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, TYPE_CHECKING

if TYPE_CHECKING:
    from ....configurations.sections import DatabaseConfig

logger = logging.getLogger("xcore.services.database.async_sql")


class AsyncSQLAdapter:
    """
    Adaptateur SQLAlchemy async.

    Usage:
        async with adapter.session() as session:
            result = await session.execute(text("SELECT * FROM users"))
    """

    def __init__(self, name: str, cfg: "DatabaseConfig") -> None:
        self.name = name
        self.url  = cfg.url
        self._echo = cfg.echo
        self._engine = None
        self._AsyncSession = None

    async def connect(self) -> None:
        try:
            from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
            from sqlalchemy.orm import sessionmaker
        except ImportError as e:
            raise ImportError(
                "sqlalchemy[asyncio] non installé — pip install sqlalchemy[asyncio]"
            ) from e

        self._engine = create_async_engine(self.url, echo=self._echo)
        self._AsyncSession = sessionmaker(
            bind=self._engine, class_=AsyncSession, expire_on_commit=False
        )
        async with self._engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))

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
                yield sess
                await sess.commit()
            except Exception:
                await sess.rollback()
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
