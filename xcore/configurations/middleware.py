from typing import TypedDict

from .base import BaseCfg, Configure


class MidlwareTypes(TypedDict):
    origins: list[str]
