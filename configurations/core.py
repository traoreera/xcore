from typing import TypedDict

from .base import BaseCfg, Configure
from .deps import Logger


class Datatypes(TypedDict):
    url: str
    echo: bool


class RedisConfig(TypedDict):
    host: str
    port: int
    db: int
    TTL: int


class Xcore(TypedDict):
    logs: Logger
    data: Datatypes
    extensions: list[str]
    requirements: list[str]
    midleware: Datatypes


class Xcorecfg(BaseCfg):
    def __init__(self, conf: Configure):
        super().__init__(conf, "xcore")
        self.default_migration: Xcore = {
            "logs": {"console": True, "file": "app.log"},
            "data": {"url": "sqlite:///test.db", "echo": False},
            "extensions": [
                "auth",
                "data",
                "manager",
                "logger",
                "security",
                "tools",
                "xcore",
            ],
            "requirements": ["config.json", "config.py"],
            "midleware": {
                "ACCESS_RULES": {
                "/admin/roles": {
                    "roles": [
                        "admin",
                        "superadmin"
                    ]
                },
                "/admin/permissions": {
                    "permissions": [
                        "manage_permissions"
                    ],
                    "roles": [
                        "admin"
                    ],
                    "method": [
                        "DELETE"
                    ]
                },
                "/users": {
                    "roles": [
                        "superadmin"
                    ],
                    "method": "DELETE"
                },
                "/settings": {
                    "roles": [
                        "admin"
                    ],
                    "permissions": [
                        "manage_settings"
                    ]
                },
                "/reports*": {
                    "permissions": [
                        "view_reports"
                    ]
                }
            }
            }
        }

        if isinstance(self.conf, Configure) and self.conf is not None:
            self.custom_config: Xcore = self.conf
        else:
            self.custom_config = self.default_migration

    
    def cfgAcessMidlware(self):
        return self.custom_config['midleware']

    def __getattribute__(self, __name):
        return super().__getattribute__(__name)
