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

logger = logging.getLogger("xcore.services.database.migrations")


class MigrationError(Exception): pass


class MigrationRunner:
    def __init__(self, db_url: str, migrations_dir: str | Path = "./migrations") -> None:
        self.db_url          = db_url
        self.migrations_dir  = Path(migrations_dir).resolve()

    def _get_config(self):
        try:
            from alembic.config import Config
        except ImportError as e:
            raise ImportError("alembic non installé — pip install alembic") from e

        cfg = Config()
        cfg.set_main_option("sqlalchemy.url", self.db_url)
        cfg.set_main_option("script_location", str(self.migrations_dir))
        return cfg

    def upgrade(self, revision: str = "head") -> None:
        from alembic import command
        logger.info(f"Migration upgrade → {revision}")
        command.upgrade(self._get_config(), revision)

    def downgrade(self, revision: str = "-1") -> None:
        from alembic import command
        logger.info(f"Migration downgrade → {revision}")
        command.downgrade(self._get_config(), revision)

    def current(self) -> str | None:
        from alembic import command
        from io import StringIO
        buf = StringIO()
        from alembic.config import Config
        cfg = self._get_config()
        cfg.stdout = buf
        command.current(cfg)
        return buf.getvalue().strip() or None

    def history(self) -> str:
        from alembic import command
        from io import StringIO
        buf = StringIO()
        cfg = self._get_config()
        cfg.stdout = buf
        command.history(cfg)
        return buf.getvalue()
