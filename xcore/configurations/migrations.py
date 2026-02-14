from typing import TypedDict

from .base import BaseCfg, Configure
from .deps import Logger


class AutoMigrationTypes(TypedDict):
    models: list[str]
    plugins: list[str]


class Backup(TypedDict):
    auto_backup_before_migration: bool
    backup_directory: str
    max_backup_files: int
    backup_name_format: str


class ExclusionTypes(TypedDict):
    exclude_directories: list[str]
    include_file_patterns: str
    exclude_file_patterns: list[str]


class MigrationTypes(TypedDict):
    url: str
    auto_discover_models: bool
    alembic_config: str
    automigration: AutoMigrationTypes
    explusion_patern: ExclusionTypes
    backup: Backup
    logger: Logger

    def responseModel(self):

        return {
            "url": self.url,
            "auto_discover_models": self.auto_discover_models,
            "alembic_config": self.alembic_config,
            "automigration": self.automigration,
            "explusion_patern": self.explusion_patern,
            "backup": self.backup,
            "logger": self.logger,
        }


class Migration(BaseCfg):
    def __init__(self, conf: Configure):
        super().__init__(conf, "migration")
        self.default_migration: MigrationTypes = {
            "url": "sqlite:///test.db",
            "alembic_config": "alembic.ini",
            "auto_discover_models": True,
            "automigration": {
                "models": ["./auth", "./manager/models/", "./admin/", "./otpProvider"],
                "plugins": ["./plugins"],
            },
            "explusion_patern": {
                "exclude_directories": [
                    "__pycache__",
                    ".git",
                    "node_modules",
                    "venv",
                    ".pytest_cache",
                ],
                "include_file_patterns": "*.py",
                "exclude_file_patterns": ["__init__.py", "test_*.py", "*_test.py"],
            },
            "backup": {
                "auto_backup_before_migration": True,
                "backup_directory": "backups",
                "max_backup_files": 10,
                "backup_name_format": "backup_{timestamp}.db",
            },
            "logger": {"console": True, "file": "migration.log"},
        }

        if isinstance(self.conf, Configure) and self.conf is not None:
            self.custom_config: MigrationTypes = self.conf

        else:
            self.custom_config = self.default_migration
