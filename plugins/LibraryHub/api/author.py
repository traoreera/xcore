from fastapi import Depends
from sqlalchemy.orm import Session

from .. import router
from ..core.database import get_db
from ..service import authors


class AuthorController:

    @router.get("/authors")
    @staticmethod
    def get_authors(db: Session = Depends(get_db)):
        return authors.get_authors(db)
