"""
sql.py — Adaptateur SQLAlchemy synchrone — optimisé production.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Generator

from ....kernel.observability import get_logger
from ._utils import sanitize_connect_args, sanitize_isolation_level

if TYPE_CHECKING:
    from ....configurations.sections import DatabaseConfig

logger = get_logger("xcore.services.database.sql")


class SQLAdapter:
    """
    Adaptateur SQLAlchemy sync pour SQLite, PostgreSQL, MySQL.

    Paramètres pool configurables depuis xcore.yaml :
        pool_pre_ping        → teste la connexion avant usage
        pool_recycle         → renouvelle avant wait_timeout serveur
        pool_timeout         → timeout d'acquisition depuis le pool
        pool_reset_on_return → comportement au retour au pool
        connect_args         → timeouts driver-level
        isolation_level      → niveau d'isolation transactionnel
        execution_options    → options SQLAlchemy par connexion

    Usage:
        with adapter.session() as session:
            users = session.execute(text("SELECT * FROM users")).fetchall()
    """

    def __init__(self, name: str, cfg: "DatabaseConfig") -> None:
        self.name = name
        self.url = cfg.url
        self._pool_size = cfg.pool_size
        self._max_overflow = cfg.max_overflow
        self._echo = cfg.echo
        self._pool_pre_ping = getattr(cfg, "pool_pre_ping", True)
        self._pool_recycle = getattr(cfg, "pool_recycle", 1800)
        self._pool_timeout = getattr(cfg, "pool_timeout", 30)
        self._pool_reset_on_return = getattr(cfg, "pool_reset_on_return", "rollback")
        self._connect_args = getattr(cfg, "connect_args", {})
        self._isolation_level = getattr(cfg, "isolation_level", None)
        self._execution_options = getattr(cfg, "execution_options", {})
        self._engine = None
        self._Session = None

    async def connect(self) -> None:
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
        except ImportError as e:
            raise ImportError("sqlalchemy non installé — pip install sqlalchemy") from e

        engine_kwargs: dict[str, Any] = {
            "echo": self._echo,
            "pool_pre_ping": self._pool_pre_ping,
            "pool_recycle": self._pool_recycle,
            "pool_reset_on_return": self._pool_reset_on_return,
        }

        is_sqlite = self.url.startswith("sqlite")
        if not is_sqlite:
            engine_kwargs["pool_size"] = self._pool_size
            engine_kwargs["max_overflow"] = self._max_overflow
            engine_kwargs["pool_timeout"] = self._pool_timeout

        if self._connect_args:
            sanitized = sanitize_connect_args(self.url, self._connect_args)
            if sanitized:
                engine_kwargs["connect_args"] = sanitized

        safe_isolation = sanitize_isolation_level(self.url, self._isolation_level)
        if safe_isolation:
            engine_kwargs["isolation_level"] = safe_isolation

        self._engine = create_engine(self.url, **engine_kwargs)

        if self._execution_options:
            self._engine = self._engine.execution_options(**self._execution_options)

        self._Session = sessionmaker(bind=self._engine)

        with self._engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))

        logger.info(
            "sql connected",
            adapter=self.name,
            pre_ping=self._pool_pre_ping,
            recycle_s=self._pool_recycle,
        )

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
            try:
                sess.rollback()
            except Exception as rollback_err:
                logger.warning(
                    "rollback failed", adapter=self.name, error=str(rollback_err)
                )
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
