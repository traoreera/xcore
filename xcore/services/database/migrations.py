"""
migrations.py — Wrapper Alembic pour les migrations de schéma.

Usage dans un plugin Trusted :
    from xcore.services.database.migrations import MigrationRunner

    runner = MigrationRunner(
        db_url=cfg.url,
        migrations_dir="./migrations",
    )
    runner.init()      # génère la première révision (ignoré si déjà existante)
    runner.upgrade()   # applique toutes les migrations en attente
    runner.status()    # liste les migrations appliquées / en attente
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine  # type: ignore

from ...kernel.observability import get_logger

logger = get_logger("xcore.services.database.migrations")


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
            from alembic.config import Config  # type: ignore
        except ImportError as e:
            raise ImportError("alembic non installé — pip install alembic") from e

        cfg = Config()
        cfg.set_main_option("sqlalchemy.url", self.db_url)
        cfg.set_main_option("script_location", str(self.migrations_dir))
        return cfg

    def _is_async(self) -> bool:
        """Détecte si l'URL utilise un driver async."""
        async_markers = (
            "+asyncpg",
            "+aiosqlite",
            "+aiomysql",
            "+asyncmy",
        )
        return any(marker in self.db_url for marker in async_markers)

    async def init(self, autogenerate: bool = True, message: str = "init") -> None:
        """
        Génère la première révision de migration.
        Ignoré silencieusement si des révisions existent déjà.

        Args:
            autogenerate: Si True, Alembic détecte automatiquement les changements
                          de schéma depuis les modèles SQLAlchemy.
            message:      Message/label de la révision (ex: "init", "create_users").
        """
        from alembic import command  # type: ignore

        if not self.migrations_dir.exists():
            raise MigrationError(
                f"The migrations directory '{self.migrations_dir}' does not exist. "
                "Run `alembic init <directory>` first to initialize the structure."
            )

        # Vérifie si des révisions existent déjà
        versions_dir = self.migrations_dir / "versions"
        if versions_dir.exists():
            existing = [
                f
                for f in versions_dir.iterdir()
                if f.suffix == ".py" and f.name != "__init__.py"
            ]
            if existing:
                logger.info(
                    "migrations already exist, skipping init",
                    count=len(existing),
                )
                return

        kwargs = dict(message=message, autogenerate=autogenerate)

        if self._is_async():
            engine = create_async_engine(self.db_url)
            async with engine.begin() as conn:

                def do_init(sync_conn):
                    cfg = self._get_config()
                    cfg.attributes["connection"] = sync_conn
                    command.revision(config=cfg, **kwargs)

                await conn.run_sync(do_init)

            await engine.dispose()
            logger.info(
                "first revision generated (async)",
                message=message,
                autogenerate=autogenerate,
            )
            return

        command.revision(config=self._get_config(), **kwargs)
        logger.info(
            "first revision generated (sync)",
            message=message,
            autogenerate=autogenerate,
        )

    async def upgrade(self, revision: str = "head") -> None:
        """Applique toutes les migrations en attente jusqu'à `revision`."""
        from alembic import command  # type: ignore

        if self._is_async():
            engine = create_async_engine(self.db_url)
            async with engine.begin() as conn:
                logger.info("async migration starting", revision=revision)

                def do_upgrade(sync_conn):
                    cfg = self._get_config()
                    cfg.attributes["connection"] = sync_conn
                    command.upgrade(config=cfg, revision=revision)

                await conn.run_sync(do_upgrade)
            await engine.dispose()
            logger.info("async migration completed", revision=revision)
            return

        logger.info("sync migration upgrade", revision=revision)
        command.upgrade(self._get_config(), revision)

    async def downgrade(self, revision: str = "-1") -> None:
        """Annule la dernière migration (ou jusqu'à `revision`)."""
        from alembic import command  # type: ignore

        if self._is_async():
            engine = create_async_engine(self.db_url)
            async with engine.begin() as conn:

                def do_downgrade(sync_conn):
                    cfg = self._get_config()
                    cfg.attributes["connection"] = sync_conn
                    command.downgrade(config=cfg, revision=revision)

                await conn.run_sync(do_downgrade)
            await engine.dispose()
            logger.info("async migration downgrade completed", revision=revision)
            return

        logger.info("sync migration downgrade", revision=revision)
        command.downgrade(self._get_config(), revision)

    async def revision(self, **kwargs) -> None:
        """Crée une nouvelle révision de migration."""
        from alembic import command  # type: ignore

        if self._is_async():
            engine = create_async_engine(self.db_url)
            async with engine.begin() as conn:

                def do_revision(sync_conn):
                    cfg = self._get_config()
                    cfg.attributes["connection"] = sync_conn
                    command.revision(config=cfg, **kwargs)

                await conn.run_sync(do_revision)

            await engine.dispose()
            return

        command.revision(config=self._get_config(), **kwargs)

    async def revison(self, **kwargs) -> None:
        """Ancien nom — utiliser revision() à la place."""
        import warnings

        warnings.warn(
            "revison() is deprecated, use revision() instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return await self.revision(**kwargs)

    async def status(self, **kwargs) -> None:
        """Affiche les migrations appliquées et en attente."""
        from alembic import command  # type: ignore

        if self._is_async():
            engine = create_async_engine(self.db_url)
            async with engine.begin() as conn:

                def do_status(sync_conn):
                    cfg = self._get_config()
                    cfg.attributes["connection"] = sync_conn
                    command.status(config=cfg, **kwargs)

                await conn.run_sync(do_status)

            await engine.dispose()
            return

        command.status(config=self._get_config(), **kwargs)
