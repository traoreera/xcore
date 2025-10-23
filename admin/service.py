from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from . import models, schemas
from sqlalchemy.orm import Session
from auth import models as auth_models, Hash
from . import models as admin_models

def create_role(db: Session, role: schemas.RoleCreate):
    if db.query(models.Role).filter(models.Role.name == role.name).first():
        raise HTTPException(status_code=400, detail="Role already exists")

    db_role = models.Role(name=role.name, description=role.description)
    db.add(db_role)
    db.commit()
    db.refresh(db_role)
    return db_role

def list_roles(db: Session):
    return db.query(models.Role).all()

def delete_role(db: Session, role_id: int):
    role = db.query(models.Role).get(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    db.delete(role)
    db.commit()




def init_root_admin(db: Session):
    ROOT_EMAIL = "root@system.local"
    ROOT_PASSWORD = "password"
    ROOT_ROLE = "superadmin"

    # 1. Vérifie si le rôle superadmin existe
    role = db.query(admin_models.Role).filter(admin_models.Role.name == ROOT_ROLE).first()
    if not role:
        role = admin_models.Role(name=ROOT_ROLE, description="Root administrator with full privileges")
        db.add(role)
        db.commit()
        db.refresh(role)

    # 2. Vérifie si le compte root existe
    user = db.query(auth_models.User).filter(auth_models.User.email == ROOT_EMAIL).first()
    if not user:
        hashed = Hash.hash(ROOT_PASSWORD)
        user = auth_models.User(email=ROOT_EMAIL, password_hash=hashed, is_active=True)
        user.roles.append(role)
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"✅ Root admin created: {ROOT_EMAIL} / {ROOT_PASSWORD}")
    else:
        print("ℹ️ Root admin already exists.")
