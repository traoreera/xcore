from sqlalchemy.orm import declarative_base, registry

from .schemas.users import RemoveUser, UpdateUser, UserCreate

Base: registry = declarative_base()


__all__ = ["Base", "UserCreate"]
