from sqlalchemy.orm import Session

from ..models import Author
from ..schemas import AuthorCreate, AuthorRead, AuthorUpdate


def get_author(db: Session, author_id: int):
    return db.query(Author).filter(Author.id == author_id).first()


def add_author(db: Session, author: AuthorCreate):
    db_author = Author(**author.dict())
    db.add(db_author)
    db.commit()
    db.refresh(db_author)
    return db_author


def update_author(db: Session, author_id: int, author: AuthorUpdate):
    db_author = get_author(db, author_id)
    for key, value in author.dict().items():
        setattr(db_author, key, value)
    db.commit()
    db.refresh(db_author)
    return db_author


def delete_author(db: Session, author_id: int):
    db_author = get_author(db, author_id)
    db.delete(db_author)
    db.commit()
    return


def get_authors(db: Session):
    return db.query(Author).all()
