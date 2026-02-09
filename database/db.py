from sqlalchemy import create_engine
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import sessionmaker

from . import Base, xcfg


def get_db():
    try:
        engine = create_engine(
            xcfg.custom_config["data"]["url"],
            echo=xcfg.custom_config["data"]["echo"],
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
