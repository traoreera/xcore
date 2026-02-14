from typing import TypedDict

from .base import BaseCfg, Configure
from .deps import Logger


class PluginsType(TypedDict):
    directory: str
    interval: int
    entry_point: str


class TaskTypse(TypedDict):
    directory: str
    default: str
    auto_restart: bool
    interval: int
    max_retries: int


class SnapshotType(TypedDict):
    extensions: list[str]
    hidden: bool
    filenames: list[str]


class ManagerType(TypedDict):
    dotenv: str
    plugins: PluginsType
    tasks: TaskTypse
    log: Logger
    snapshot: SnapshotType


class ManagerCfg(BaseCfg):
    def __init__(self, conf: Configure):
        super().__init__(conf, "migration")
        self.default_migration: ManagerType = {
            "dotenv": "./manager/.env",
            "plugins": {"directory": "./plugins", "interval": 2, "entry_point": "run"},
            "tasks": {
                "directory": "./backgroundtask",
                "default": "./manager/plTask.py",
                "auto_restart": True,
                "interval": 2,
                "max_retries": 3,
            },
            "log": {"file": "manager.log", "console": True},
            "snapshot": {
                "extensions": [
                    ".log",
                    ".pyc",
                    ".html",
                    "*.lock",
                    "*.toml",
                    "*.json",
                    "*.txt",
                    "*.md",
                ],
                "filenames": [
                    "__pycache__",
                    "__init__.py",
                    ".env",
                    ".git",
                    "poetry.lock",
                    "pyproject.toml",
                    "requirements.txt",
                    "plugin.json",
                    "README.md",
                    "LICENSE",
                    "LICENSE.txt",
                    "CHANGELOG.md",
                    "HISTORY.md",
                    "CONTRIBUTING.md",
                    "CODE_OF_CONDUCT.md",
                ],
                "hidden": True,
            },
        }

        if isinstance(self.conf, Configure) and self.conf is not None:
            self.custom_config: ManagerType = self.conf

        else:
            self.custom_config = self.default_migration
