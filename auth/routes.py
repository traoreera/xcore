from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from database.db import get_db
from security.token import Token

from . import authCache, dependencies, schemas, service

authRouter = APIRouter(prefix="/auth", tags=["Auth"])


@authRouter.post("/register", response_model=schemas.UserRead)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    return service.register_user(db, user)


@authRouter.post("/login", response_model=schemas.Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    user = service.authenticate_user(db, form_data.username, form_data.password)
    token = Token.create(data={"sub": user.email})
    return schemas.Token(access_token=token, token_type="bearer")


@authRouter.get("/me", response_model=schemas.UserRead)
@authCache.cached
def get_me(current_user=Depends(dependencies.get_current_user)):
    return schemas.UserRead(
        id=current_user.id, email=current_user.email, is_active=current_user.is_active
    )
