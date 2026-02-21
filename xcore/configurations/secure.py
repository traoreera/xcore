from typing import TypedDict

from .base import BaseCfg, Configure


class PasswordType(TypedDict):
    algorithms: list[str]
    scheme: str
    category: str


class SecureTypes(TypedDict):
    password: PasswordType
    dotenv: str


class Secure(BaseCfg):
    def __init__(self, conf: Configure):
        super().__init__(conf, "secure")
        self.default_migration: SecureTypes = {
            "password": {
                "algorithms": ["bcrypt"],
                "scheme": "bcrypt",
                "category": "password",
            },
            "dotenv": "./security/.env",
        }
        if isinstance(self.conf, Configure) and self.conf is not None:
            self.custom_config: SecureTypes = self.conf
        else:
            self.custom_config = self.default_migration
