from sqlalchemy.orm import declarative_base, registry
from .schemas.users import UserCreate, RemoveUser,UpdateUser

Base: registry = declarative_base()


__all__ = ['Base', 'UserCreate']