"""
sql.py — Adaptateur SQLAlchemy synchrone.
Fournit un accès via Session (SQLAlchemy ORM) et execute() brut.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Generator, TYPE_CHECKING

if TYPE_CHECKING:
    from ....configurations.sections import DatabaseConfig

logger = logging.getLogger("xcore.services.database.sql")


class SQLAdapter:
    """
    Adaptateur SQLAlchemy sync pour SQLite, PostgreSQL, MySQL.

    Usage:
        with adapter.session() as session:
            users = session.execute(text("SELECT * FROM users")).fetchall()

        result = adapter.execute("SELECT 1")
    """

    def __init__(self, name: str, cfg: "DatabaseConfig") -> None:
        self.name = name
        self.url  = cfg.url
        self._pool_size    = cfg.pool_size
        self._max_overflow = cfg.max_overflow
        self._echo         = cfg.echo
        self._engine = None
        self._Session = None

    async def connect(self) -> None:
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
        except ImportError as e:
            raise ImportError("sqlalchemy non installé — pip install sqlalchemy") from e

        self._engine = create_engine(
            self.url,
            pool_size=self._pool_size,
            max_overflow=self._max_overflow,
            echo=self._echo,
        )
        self._Session = sessionmaker(bind=self._engine)
        # Test de connexion
        with self._engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))

    async def disconnect(self) -> None:
        if self._engine:
            self._engine.dispose()
            self._engine = None

    @contextmanager
    def session(self) -> Generator:
        if self._Session is None:
            raise RuntimeError(f"[{self.name}] Base non initialisée")
        sess = self._Session()
        try:
            yield sess
            sess.commit()
        except Exception:
            sess.rollback()
            raise
        finally:
            sess.close()

    def execute(self, sql: str, params: dict | None = None) -> Any:
        if self._engine is None:
            raise RuntimeError(f"[{self.name}] Base non initialisée")
        from sqlalchemy import text
        with self._engine.connect() as conn:
            return conn.execute(text(sql), params or {})

    async def ping(self) -> tuple[bool, str]:
        try:
            self.execute("SELECT 1")
            return True, "ok"
        except Exception as e:
            return False, str(e)
