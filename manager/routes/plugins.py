
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

import manager.runtimer as runtimer
from admin import dependencies
from manager.crud.plugin import PluginsCrud
from manager.db import get_db
from manager.runtimer import (
    backgroundtask,
    backgroundtask_manager,
    core_task_threads,
    crontab,
)
from manager.schemas.plugins import Delete, Plugin, PluginResponse, Update
from manager.schemas.taskManager import (
    RestartService,
    TaskListResponse,
    TaskResourcesResponse,
    TaskStatusResponse,
)

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
