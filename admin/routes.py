from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database.db import get_db
from . import service, schemas, dependencies

adminrouter = APIRouter(prefix="/admin", tags=["Admin"])

@adminrouter.post("/roles", response_model=schemas.RoleRead)
def create_role(role: schemas.RoleCreate, db: Session = Depends(get_db), user=Depends(dependencies.require_admin)):
    return service.create_role(db, role)

@adminrouter.get("/roles", response_model=list[schemas.RoleRead])
def list_roles(db: Session = Depends(get_db), user=Depends(dependencies.require_admin)):
    return service.list_roles(db)

@adminrouter.delete("/roles/{role_id}")
def delete_role(role_id: int, db: Session = Depends(get_db), user=Depends(dependencies.require_admin)):
    service.delete_role(db, role_id)
    return {"ok": True, "deleted": role_id}
    