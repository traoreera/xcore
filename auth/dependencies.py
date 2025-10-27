from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from database.db import get_db
from security.token import Token

from . import authCache, models

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
):

    user = Token.verify(
        token,
        HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ),
    )

    if user:
        user = db.query(models.User).filter(models.User.email == user["sub"]).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
