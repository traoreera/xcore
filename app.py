"""
app.py — Intégration FastAPI + Integration + Manager
─────────────────────────────────────────────────────
Ordre correct :
  1. integration.init()              → services prêts (db, email, otp...)
  2. core_services rempli            → db, engine, base disponibles
  3. manager.update_services(...)    → injecté dans PluginManager avant start()
  4. manager.start()                 → plugins chargés avec les vrais services
"""

from fastapi import FastAPI
from sqlalchemy.orm import declarative_base

from xcore.appcfg import xhooks
from xcore.hooks.hooks import Event, HookManager
from xcore.integration import Integration
from xcore.integration.services.database import SQLAdapter
from xcore.manager import Manager

Base = declarative_base()
_plugin_hooks = HookManager()
integration = Integration("./integration.yaml")


app = FastAPI(title="Mon API")

manager = Manager(
    app=app,
    base_routes=list(app.routes),
    plugins_dir="plugins",
    secret_key=b"ejkfnwefnkejw",
    services={},
    interval=2,
    strict_trusted=True,
)


@app.on_event("startup")
async def event_startup():
    # 1- integration init
    await integration.init()

    # put on depends for all app
    await xhooks.emit("xcore.startup")  # emit starting app event


@app.on_event("shutdown")
async def event_shotdown():

    await xhooks.emit("xcore.shutdown")


@xhooks.on("xcore.startup")
async def manager_setup(event: Event):
    ddb: SQLAdapter = integration.db.get("default")  # get databse provider

    core_services = {
        "db": ddb.session,
        "base": Base,
        "engine": ddb.engine,
        "Event": Event,
        "Hooks": _plugin_hooks,
    }
    manager._services = core_services
    manager.update_services(core_services)

    report = await manager.start()

    print("=>", report)


@xhooks.on("xcore.shutdown")
async def manager_shutdown(event: Event):
    await manager.stop()
    await integration.shutdown()


app.state.manager = manager
app.state.integration = integration
