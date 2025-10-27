from sqlalchemy.orm import declarative_base, registry

from dependencies import xcfg

Base: registry = declarative_base()


__all__ = [
    "Base",
]
