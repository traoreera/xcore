from fastapi import APIRouter, Depends, HTTPException

from admin import dependencies

manager_admin = APIRouter(prefix="/system/manager", tags=["system"])


@manager_admin.get("/status")
def get_manager_status(user=Depends(dependencies.require_admin)):
    from xcore.manage import manager

    discovered = manager.return_name()
    active = manager.loader.get_all_active()

    return {
        "plugins_dir": manager.plugins_dir,
        "entry_point": manager.entry_point,
        "watch_interval": manager.interval,
        "watch_running": manager.running,
        "discovered_count": len(discovered),
        "active_count": len(active),
        "discovered_plugins": discovered,
        "active_plugins": active,
    }


@manager_admin.get("/plugins/discovered")
def list_discovered_plugins(user=Depends(dependencies.require_admin)):
    from xcore.manage import manager

    plugins = manager.return_name()
    return {"count": len(plugins), "plugins": plugins}


@manager_admin.get("/plugins/active")
def list_active_plugins(user=Depends(dependencies.require_admin)):
    from xcore.manage import manager

    plugins = manager.loader.get_all_active()
    return {"count": len(plugins), "plugins": plugins}


@manager_admin.post("/plugins/run")
def run_plugins(user=Depends(dependencies.require_superuser)):
    from xcore.manage import manager

    manager.run_plugins(reload_app=False)
    return {"ok": True, "action": "run_plugins"}


@manager_admin.post("/plugins/reload")
def reload_plugins(user=Depends(dependencies.require_superuser)):
    from xcore.manage import manager

    manager.run_plugins(reload_app=True)
    return {"ok": True, "action": "reload_plugins"}


@manager_admin.patch("/plugins/{name}/enable")
def enable_plugin(name: str, user=Depends(dependencies.require_superuser)):
    from xcore.manage import manager

    updated = manager.loader.enable(name)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Plugin '{name}' introuvable.")
    manager.run_plugins(reload_app=True)
    return {"ok": True, "name": name, "enabled": True}


@manager_admin.patch("/plugins/{name}/disable")
def disable_plugin(name: str, user=Depends(dependencies.require_superuser)):
    from xcore.manage import manager

    updated = manager.loader.disable(name)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Plugin '{name}' introuvable.")
    manager.run_plugins(reload_app=True)
    return {"ok": True, "name": name, "enabled": False}
