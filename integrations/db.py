from sqlalchemy import create_engine
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import declarative_base, registry, sessionmaker

from .conf import Database
from .plManager import logger

Base: registry = declarative_base()


def get_db():
    try:
        engine = create_engine(Database.URL, echo=False, pool_timeout=10)
    except ProgrammingError:
        engine = None

    if engine:
        Base.metadata.create_all(engine)
        logger.info("Using first database for application")
        Session = sessionmaker(bind=engine, autoflush=False)
        session = Session()
        try:
            yield session
        finally:
            session.close()
    else:
        return None


logger.info("🗃️  Module de session de base de données chargé avec succès")
