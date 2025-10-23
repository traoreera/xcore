from sqlalchemy.orm import declarative_base, registry

Base: registry = declarative_base()


__all__ = ['Base', ]