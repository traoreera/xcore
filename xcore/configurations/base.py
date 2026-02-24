import json
from typing import Any, Dict, Optional

from rich import print_json


class Configure:
    """Charge et manipule un fichier JSON de configuration."""

    def __init__(self, default: str = "config.json") -> None:
        self.file = default

        with open(default, "r") as f:
            self.cfg = json.load(f)

    def __call__(self, conf: str) -> Optional[Dict[str, Any]]:
        if conf == "All":
            return self.cfg
        return self.cfg.get(conf)


class BaseCfg:
    """Classe de base pour gérer un module de configuration."""

    def __init__(self, conf: Configure, section: str):
        self.section = section
        self.conf: Optional[Dict] = conf(section)
        self.all = conf("All")
        self.file = conf.file

    def get_section(self) -> Optional[Dict]:
        return self.conf

    def getter(self, key: str):
        if self.conf is None:
            return None
        return self.conf.get(key)

    def adder(self, key: str, value: Any) -> None:
        if self.conf is None:
            self.conf = {}
        self.conf[key] = value

    def remover(self, key: str) -> None:
        if self.conf and key in self.conf:
            del self.conf[key]

    def saver(self):
        if self.all is None or self.conf is None:
            return
        self.all[self.section].update(self.conf)
        with open(self.file, "w") as f:
            json.dump(self.all, f, indent=4)

    def printer(self):
        if self.conf:
            print_json(data=self.conf)
