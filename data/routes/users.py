from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from data.schemas.users import UserCreate, UpdateUser, RemoveUser, UserResponse
from data.crud.users import UserCRUD
from security.hash import Hash
from security.token import Token
from auth.users import get_current_user
from test import get_db

usersRoutes = APIRouter(prefix="/users", tags=["Users"])

authRouters = APIRouter(prefix="/auth", tags=["Auth"])






#oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/login")


# ============================================================
# 🧍 REGISTER USER
# ============================================================
@usersRoutes.post("/register", response_model=UserResponse)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    # Vérifie si l'email existe déjà
    db_user = UserCRUD.get_user_by_email(db, user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email déjà utilisé")

    return UserCRUD.create(db, user)


# ============================================================
# 🔑 LOGIN USER
# ============================================================
@authRouters.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    db_user = UserCRUD.get_user_by_email(db, form_data.username)
    if not db_user:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable")
    print(form_data.password, db_user.password)

    
    if not Hash.verify(db_user.password, form_data.password):
        raise HTTPException(status_code=401, detail="Mot de passe invalide")

    access_token = Token.create({"sub": db_user.email})
    return {"access_token": access_token, "token_type": "bearer"}


# ============================================================
# 👤 CURRENT USER
# ============================================================
@usersRoutes.get("/me", response_model=UserResponse)
def get_me(current_user=Depends(get_current_user)):
    return current_user


# ============================================================
# 📋 LIST USERS
# ============================================================
@usersRoutes.get("/", response_model=list[UserResponse])
def list_users(db: Session = Depends(get_db)):
    return UserCRUD.get_all(db)


# ============================================================
# 🔍 GET USER BY ID
# ============================================================
@usersRoutes.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: str, db: Session = Depends(get_db)):
    user = UserCRUD.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    return user


# ============================================================
# ✏️ UPDATE USER
# ============================================================
@usersRoutes.put("")
def update_user(
    user: UpdateUser,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    UserCRUD.update(db=db, updates=user, email=current_user.email)
    return {"status": "updated", "user_id": current_user.email}


# ============================================================
# ❌ DELETE USER
# ============================================================
@usersRoutes.delete("/")
def delete_user( db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    user = UserCRUD.get_user_by_email(db, current_user.email)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    UserCRUD.delete(db=db, email=current_user.email)
    return {"status": "deleted", "user_id": current_user.email}
