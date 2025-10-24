from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from . import Hash, models, schemas


def register_user(db: Session, user: schemas.UserCreate):
    if db.query(models.User).filter(models.User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed = Hash.hash(user.password)
    db_user = models.User(email=user.email, password_hash=hashed)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def authenticate_user(db: Session, email: str, password: str):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not Hash.verify(user.password_hash, password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return user
