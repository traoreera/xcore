from fastapi import HTTPException
from sqlalchemy.orm import Session

from auth import models as auth_models
from security.hash import Hash

from . import models, schemas

# ============================================================
# ROLES MANAGEMENT
# ============================================================


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


def delete_role(db: Session, role_id: str):
    role = db.query(models.Role).get(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    db.delete(role)
    db.commit()
    return {"ok": True, "deleted": role_id}


def attribute_role_to_user(db: Session, user_id: str, role_id: str):
    user = db.query(auth_models.User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    role = db.query(models.Role).get(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    if role in user.roles:
        raise HTTPException(status_code=409, detail="User already has this role")

    user.roles.append(role)
    db.commit()
    db.refresh(user)

    return {"ok": True, "user_id": user.id, "role_id": role.id}


# ============================================================
# ROOT ADMIN INITIALIZATION
# ============================================================


def init_root_admin(db: Session):
    ROOT_EMAIL = "root@system.local"
    ROOT_PASSWORD = "Root@123"
    ROOT_ROLE = "superadmin"

    # 1. Vérifie si le rôle superadmin existe
    role = db.query(models.Role).filter(models.Role.name == ROOT_ROLE).first()
    if not role:
        role = models.Role(
            name=ROOT_ROLE, description="Root administrator with full privileges"
        )
        db.add(role)
        db.commit()
        db.refresh(role)

    # 2. Vérifie si le compte root existe
    user = (
        db.query(auth_models.User).filter(auth_models.User.email == ROOT_EMAIL).first()
    )
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

    return user


# ============================================================
# PERMISSIONS MANAGEMENT
# ============================================================


def create_permission(db: Session, permission: schemas.PermissionCreate):
    if (
        db.query(models.Permission)
        .filter(models.Permission.name == permission.name)
        .first()
    ):
        raise HTTPException(status_code=400, detail="Permission already exists")
    if not (db.query(models.Role).get(permission.role_id)):
        raise HTTPException(status_code=400, detail="Role not found")

    db_permission = models.Permission(
        name=permission.name,
        description=permission.description,
        role_id=permission.role_id,
    )
    db.add(db_permission)
    db.commit()
    db.refresh(db_permission)
    return db_permission


def list_permissions(db: Session):
    return db.query(models.Permission).all()


def delete_permission(db: Session, permission_id: str):
    permission = db.query(models.Permission).get(permission_id)
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    db.delete(permission)
    db.commit()
    return {"ok": True, "deleted": permission_id}


def affect_role_to_permission(db: Session, role_id: str, permission_id: str):
    role = db.query(models.Role).get(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    permission = db.query(models.Permission).get(permission_id)
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")

    if permission in role.permissions:
        raise HTTPException(
            status_code=409, detail="Permission already assigned to this role"
        )

    role.permissions.append(permission)
    db.commit()

    return {"ok": True, "role_id": role_id, "permission_id": permission_id}
