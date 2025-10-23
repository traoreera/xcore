from sqlalchemy import create_engine
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import declarative_base, registry, sessionmaker


from .import Base

def get_db():
    try:
        engine = create_engine("sqlite:///./test.db", echo=True)
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
