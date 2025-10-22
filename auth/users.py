from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from security.token import Token
from data.models import User
from test import get_db  # ta session SQLAlchemy (à adapter selon ton arbo)
from data.schemas.users import UserInDB

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> UserInDB:
    """Décoder le JWT et retourner l’utilisateur courant."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Impossible d’authentifier l’utilisateur",
        headers={"WWW-Authenticate": "Bearer"},
    )

    
    email = Token.verify(token, credentials_exception=credentials_exception)
    if not email:
        raise credentials_exception
    

    user = db.query(User).filter(User.email == email['sub']).first()
    if user is None:
        raise credentials_exception

    return UserInDB.model_validate(user)
