from typing import TypedDict

from .base import BaseCfg, Configure
from .deps import Logger


class PluginsPEs(TypedDict):
    name: str
    path: str


class PluginsConfig(BaseCfg):

    def __init__(self, conf: Configure):
        super().__init__(conf, "plugins")

        self.default = {}

        if isinstance(self.conf, Configure) and self.conf.plugins is not None:
            self.custom = self.conf.plugins
        else:
            self.custom = self.default

    def __getattribute__(self, __name):
        return super().__getattribute__(__name)
