from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import List, Optional
from security import Hash, Token
from data.models import User
from data.schemas.users import (
    UserCreate,
    UserResponse,
    UserPublic,
    UpdateUser,
    RemoveUser,
    UserInDB,
    UserListResponse,
)

# ==========================================================
# CRUD UTILISATEUR — Clean, sécurisé, production-ready
# ==========================================================


class UserCRUD:
    """Classe de gestion des opérations CRUD sur les utilisateurs."""

    @staticmethod
    def create(db: Session, user_data: UserCreate) -> UserResponse:
        """Créer un nouvel utilisateur."""
        existing_user = db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Un utilisateur avec cet email existe déjà.",
            )

        hashed_pwd = Hash.hash(user_data.password)
        db_user = User(
            id=user_data.id,
            username=user_data.username,
            email=user_data.email,
            password=hashed_pwd,
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)

        return db_user.responseModel()

    # ------------------------------------------------------
    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[UserInDB]:
        """Récupérer un utilisateur par email."""
        user = db.query(User).filter(User.email == email).first()
        return UserInDB.model_validate(user) if user else None

    # ------------------------------------------------------
    @staticmethod
    def get_user_by_id(db: Session, user_id: str) -> Optional[UserPublic]:
        """Récupérer un utilisateur par ID."""
        user = db.query(User).filter(User.id == user_id).first()
        return UserPublic.model_validate(user) if user else None

    # ------------------------------------------------------
    @staticmethod
    def get_all_users(db: Session, skip: int = 0, limit: int = 50) -> UserListResponse:
        """Lister les utilisateurs avec pagination."""
        users = db.query(User).offset(skip).limit(limit).all()
        total = db.query(User).count()
        return UserListResponse(total=total, items=[UserPublic.model_validate(u) for u in users])

    # ------------------------------------------------------
    @staticmethod
    def update(db: Session, email: str, updates: UpdateUser) -> UserResponse:
        """Mettre à jour un utilisateur (partiellement)."""
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

        data = updates.dict()
        if "password" in data:
            data["password"] = Hash.hash(data.pop("password"))

        for key, value in data.items():
            setattr(user, key, value)

        db.commit()
        db.refresh(user)

        return UserResponse.model_validate(user)

    # ------------------------------------------------------
    @staticmethod
    def delete(db: Session, email: str) -> bool:
        """Supprimer un utilisateur."""
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

        db.delete(user)
        db.commit()
        return True

    # ------------------------------------------------------
    @staticmethod
    def authenticate(db: Session, email: str, password: str) -> dict:
        """Vérifie les identifiants et génère un token JWT."""
        user = db.query(User).filter(User.email == email).first()
        if not user or not Hash.verify(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Identifiants invalides.",
            )

        token = Token.create({"sub": user.email})
        return {"access_token": token, "token_type": "bearer"}


    @staticmethod
    def get_all(db: Session) -> List[UserPublic]:
        users = db.query(User).all()
        return [UserPublic.model_validate(u) for u in users]