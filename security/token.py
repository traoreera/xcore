import datetime

from fastapi import HTTPException, status
from jose import JWTError, jwt

from . import TokenConfig


class Token:
    """Gestion centralisée des jetons JWT."""

    @staticmethod
    def create(data: dict) -> str:
        """Crée un JWT signé avec les paramètres du TokenConfig."""
        try:
            to_encode = data.copy()
            expire = datetime.datetime.utcnow() + datetime.timedelta(
                minutes=TokenConfig.ACCESS_TOKEN_EXPIRE_MINUTES
            )
            to_encode.update({"exp": expire})
            token = jwt.encode(
                to_encode, TokenConfig.JWTKEY, algorithm=TokenConfig.ALGORITHM
            )
            return token

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erreur création token: {e}",
            )

    @staticmethod
    def verify(token: str, credentials_exception: HTTPException) -> dict:
        """Vérifie et décode un JWT, renvoie le payload s'il est valide."""

        try:
            payload = jwt.decode(
                token, TokenConfig.JWTKEY, algorithms=[TokenConfig.ALGORITHM]
            )
            email: str = payload.get("sub")
            if email is None:
                raise credentials_exception
            return payload

        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Erreur JWT: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"},
            )
