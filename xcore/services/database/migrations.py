"""
migrations.py — Wrapper Alembic pour les migrations de schéma.

Usage dans un plugin Trusted :
    from xcore.services.database.migrations import MigrationRunner

    runner = MigrationRunner(
        db_url=cfg.url,
        migrations_dir="./migrations",
    )
    runner.upgrade()   # applique toutes les migrations en attente
    runner.status()    # liste les migrations appliquées / en attente
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine  # type:ignore

logger = logging.getLogger("xcore.services.database.migrations")


class MigrationError(Exception):
    pass


class MigrationRunner:
    def __init__(
        self, db_url: str, migrations_dir: str | Path = "./migrations"
    ) -> None:
        self.db_url = db_url
        self.migrations_dir = Path(migrations_dir).resolve()

    def _get_config(self):
        try:
            from alembic.config import Config  # type:ignore
        except ImportError as e:
            raise ImportError(
                "alembic non installé — pip install alembic") from e

        cfg = Config()
        cfg.set_main_option("sqlalchemy.url", self.db_url)
        cfg.set_main_option("script_location", str(self.migrations_dir))
        return cfg

    async def upgrade(self, revision: str = "head") -> None:
        from alembic import command

        if "+asyncpg" in self.db_url or "+aiosqlite" in self.db_url:
            engine = create_async_engine(self.db_url)
            async with engine.begin() as conn:
                logger.info("Migration asynchrone demare")

                def do_upgrade(sync_conn):
                    cfg = self._get_config()
                    cfg.attributes["connection"] = sync_conn
                    command.upgrade(config=cfg, revision=revision)

                await conn.run_sync(do_upgrade)
            await engine.dispose()
            logger.info("Migration faite avec sucess")
            return

        else:
            # Mode synchrone classique
            logger.info(f"Migration sync upgrade → {revision}")
            command.upgrade(self._get_config(), revision)

    async def downgrade(self, revision: str = "-1") -> None:
        from alembic import command  # type:ignore

        if "+asyncpg" in self.db_url or "+aiosqlite" in self.db_url:
            engine = create_async_engine(self.db_url)
            async with engine.begin() as conn:

                def do_downgrade(conn):
                    cfg = self._get_config()
                    cfg.attributes["connection"] = conn
                    command.downgrade(config=cfg, revision=revision)

                await conn.run_sync(do_downgrade)
            await engine.dispose()

            return

        logger.info(f"Migration downgrade → {revision}")
        command.downgrade(self._get_config(), revision)

    async def revison(self, **kwargs):
        from alembic import command  # type:ignore

        if "+asyncpg" in self.db_url or "+aiosqlite" in self.db_url:
            engine = create_async_engine(self.db_url)
            async with engine.begin() as conn:

                def do_revision(conn):
                    cfg = self._get_config()
                    cfg.attributes["connection"] = conn
                    command.revision(config=cfg, **kwargs)

                await conn.run_sync(do_revision)

            await engine.dispose()
            return

        command.revision(config=self._get_config(), **kwargs)

    async def status(self, **kwargs):
        from alembic import command  # type:ignore

        if "+asyncpg" in self.db_url or "+aiosqlite" in self.db_url:
            engine = create_async_engine(self.db_url)
            async with engine.begin() as conn:

                def do_revision(conn):
                    cfg = self._get_config()
                    cfg.attributes["connection"] = conn
                    command.status(config=cfg, **kwargs)

                await conn.run_sync(do_revision)

            await engine.dispose()
            return

        command.revision(config=self._get_config(), **kwargs)
