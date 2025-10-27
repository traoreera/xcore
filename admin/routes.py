from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.db import get_db

from . import dependencies, schemas, service

adminrouter = APIRouter(prefix="/admin", tags=["Admin"])


@adminrouter.post("/roles", response_model=schemas.RoleRead)
def create_role(
    role: schemas.RoleCreate,
    db: Session = Depends(get_db),
    user=Depends(dependencies.require_admin),
):
    return service.create_role(db, role)


@adminrouter.get("/roles", response_model=list[schemas.RoleRead])
def list_roles(db: Session = Depends(get_db), user=Depends(dependencies.require_admin)):
    return service.list_roles(db)


@adminrouter.delete("/roles/{role_id}")
def delete_role(
    role_id: str,
    db: Session = Depends(get_db),
    user=Depends(dependencies.require_admin),
):
    service.delete_role(db, role_id)
    return {"ok": True, "deleted": role_id}


@adminrouter.post("/users/{user_id}/roles/{role_id}")
def attribute_role_to_user(
    user_id: int,
    role_id: int,
    db: Session = Depends(get_db),
    user=Depends(dependencies.require_admin),
):
    return service.attribute_role_to_user(db, user_id, role_id)


@adminrouter.post("/roles/{role_id}/permissions/{permission_id}")
def afect_role_to_permission(
    role_id: str,
    permission_id: str,
    db: Session = Depends(get_db),
    user=Depends(dependencies.require_admin),
):
    return service.affect_role_to_permission(db, role_id, permission_id)


@adminrouter.get("/permissions", response_model=list[schemas.PermissionRead])
def list_permissions(
    db: Session = Depends(get_db), user=Depends(dependencies.require_admin)
):
    return service.list_permissions(db)


@adminrouter.delete("/permissions/{permission_id}")
def delete_permission(
    permission_id: str,
    db: Session = Depends(get_db),
    user=Depends(dependencies.require_admin),
):
    return service.delete_permission(db, permission_id)


@adminrouter.post("/permissions", response_model=schemas.PermissionRead)
def create_permission(
    permission: schemas.PermissionCreate,
    db: Session = Depends(get_db),
    user=Depends(dependencies.require_admin),
):
    return service.create_permission(db, permission)
