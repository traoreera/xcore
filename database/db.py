from sqlalchemy import create_engine
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import declarative_base, registry, sessionmaker

from . import Base, xcfg


def get_db():
    try:
        engine = create_engine(
            xcfg.get("database", "url"), echo=xcfg.get("database", "echo")
        )
    except ProgrammingError:
        engine = None

    if engine:
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine, autoflush=False)
        session = Session()
        try:
            yield session
        finally:
            session.close()
    else:
        return None
