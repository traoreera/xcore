
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from integrations.crud.plugin import PluginsCrud
from integrations.db import get_db
from integrations.schemas.plugins import Delete, PluginResponse, Update

plugin = APIRouter(prefix="/system/plugins", tags=["system"])


try:
    import psutil
except ImportError:
    psutil = None


@plugin.get("/", response_model=list[PluginResponse])
# user=Depends(dependencies.require_admin)
async def list_plugins(db: Session = Depends(get_db)):
    return PluginsCrud(db).get_alls()


@plugin.patch("/enable", response_model=bool)
def enable_plugin(name: str, db: Session = Depends(get_db)):

    return PluginsCrud(db).status(name, True)


@plugin.patch("/disable")
def disable_plugin(name: str, db: Session = Depends(get_db)):
    return PluginsCrud(db).status(name, False)


@plugin.delete("/delete")
def delete_plugin(plug: Delete, db: Session = Depends(get_db)):
    return PluginsCrud(db).delete(plug)


@plugin.patch("/update")
def update_plugin(plug: Delete, data: Update, db: Session = Depends(get_db)):
    return PluginsCrud(db).update(plug, data)


@plugin.post("/reload")
def reload_plugins(db: Session = Depends(get_db)):
    from xcore.manage import manager

    manager.run_plugins(reload_app=True)
    return {"msg": "Plugins reloaded successfully"}
