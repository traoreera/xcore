from typing import TypedDict

from .base import BaseCfg, Configure


class Redis(TypedDict):
    host: str
    port: int
    db: int
    TTL: int


class Rediscfg(BaseCfg):
    def __init__(self, conf: Configure):
        super().__init__(conf, "xcore")
        self.default_migration: Redis = {
            "host": "localhost",
            "port": 6379,
            "db": 0,
            "TTL": 60,
        }

        if isinstance(self.conf, Configure) and self.conf is not None:
            self.custom_config: Rediscfg = self.conf
        else:
            self.custom_config = self.default_migration

    def __getattribute__(self, __name):
        return super().__getattribute__(__name)
