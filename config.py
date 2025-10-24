import json
from typing import Any, Dict, Optional

from rich import print_json


class Configure:
    """Charge et manipule un fichier JSON de configuration."""

    def __init__(self, file: str):
        self.file = file
        with open(self.file, "r") as f:
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

    def get(self, key: str):
        if self.conf is None:
            return None
        return self.conf.get(key)

    def add(self, key: str, value: Any) -> None:
        if self.conf is None:
            self.conf = {}
        self.conf[key] = value

    def remove(self, key: str) -> None:
        if self.conf and key in self.conf:
            del self.conf[key]

    def save(self):
        if self.all is None or self.conf is None:
            return
        self.all[self.section].update(self.conf)
        with open(self.file, "w") as f:
            json.dump(self.all, f, indent=4)

    def print(self):
        if self.conf:
            print_json(data=self.conf)


class CfgManager(BaseCfg):
    def __init__(self, conf: Configure):
        super().__init__(conf, "manager")

    def cfgplugins(self) -> Optional[Dict[str, Any]]:
        return self.conf.get("plugins") if self.conf else None

    def cfgtasks(self) -> Optional[Dict[str, Any]]:
        return self.conf.get("tasks") if self.conf else None

    def cfgsnapshot(self) -> Optional[Dict[str, Any]]:
        return self.conf.get("snapshot") if self.conf else None

    def cfgdotenv(self) -> Optional[Dict[str, Any]]:
        return self.conf.get("dotenv") if self.conf else None

    def cfglog(self) -> Optional[Dict[str, Any]]:
        return self.conf.get("log") if self.conf else None

    def get(self, module: str, key: str):
        mapping = {
            "log": self.cfglog,
            "plugins": self.cfgplugins,
            "tasks": self.cfgtasks,
            "snapshot": self.cfgsnapshot,
        }
        func = mapping.get(module)
        return func().get(key) if func and func() else None

    def dict(self):
        return self.conf


class Secure(BaseCfg):
    def __init__(self, conf: Configure):
        super().__init__(conf, "secure")

    def cfgPassword(self) -> Optional[Dict[str, Any]]:
        return self.conf.get("password") if self.conf else None

    def cfgdotenv(self) -> Optional[Dict[str, Any]]:
        return self.conf.get("dotenv") if self.conf else None

    def get(self, module: str, key: str):
        if module == "password":
            pwd = self.cfgPassword()
            return pwd.get(key) if pwd else None
        return None


class Migration(BaseCfg):
    def __init__(self, conf: Configure):
        super().__init__(conf, "migration")

    def cfgLogger(self) -> Optional[Dict[str, Any]]:
        return self.conf.get("logger") if self.conf else None

    def cfgAutoMigration(self) -> Optional[Dict[str, Any]]:
        return self.conf.get("automigration") if self.conf else None

    def cfgAutoDiscovery(self) -> Optional[Dict[str, Any]]:
        return self.conf.get("model_discovery") if self.conf else None

    def cfgExclusionpatern(self) -> Optional[Dict[str, Any]]:
        return self.conf.get("explusion_patern") if self.conf else None

    def cfgBasepatern(self) -> Optional[Dict[str, Any]]:
        return self.conf.get("base_patern") if self.conf else None

    def cfgbackup(self) -> Optional[Dict[str, Any]]:
        return self.conf.get("backup") if self.conf else None

    def get(self, module: str, key: str):
        mapping = {
            "log": self.cfgLogger,
            "automigration": self.cfgAutoMigration,
            "discovery": self.cfgAutoDiscovery,
            "exclusion_patern": self.cfgExclusionpatern,
            "base_patern": self.cfgBasepatern,
            "backup": self.cfgbackup,
        }
        func = mapping.get(module)
        result = func() if func else self.conf
        return result.get(key) if result else None


class XCore(BaseCfg):

    def __init__(self, conf):
        super().__init__(conf, "xcore")

    def cfgLogger(self) -> Optional[Dict[str, Any]]:
        return self.conf.get("logs") if self.conf else None

    def database(
        self,
    ) -> Optional[Dict[str, Any]]:
        return self.conf.get("data") if self.conf else None

    def get(self, module: str, key: str):
        mapping = {"log": self.cfgLogger, "database": self.database}
        func = mapping.get(module)
        result = func() if func else self.conf
        return result.get(key) if result else None
