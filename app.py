"""
app.py — Intégration FastAPI + Integration + Manager
─────────────────────────────────────────────────────
Ordre correct :
  1. integration.init()              → services prêts (db, email, otp...)
  2. core_services rempli            → db, engine, base disponibles
  3. manager.update_services(...)    → injecté dans PluginManager avant start()
  4. manager.start()                 → plugins chargés avec les vrais services
"""

from contextlib import asynccontextmanager

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


@asynccontextmanager
async def lifespan(app: FastAPI):

    # 1. Init des services (db, email, otp...)
    await integration.init()

    # 2. Récupération de la DB après init
    ddb: SQLAdapter = integration.db.get("default")

    core_services = {
        "db": ddb.session,
        "base": Base,
        "engine": ddb.engine,
        "Hooks": _plugin_hooks,
        "Event": Event,
    }

    # 3. Injection dans PluginManager AVANT start()
    manager: Manager = app.state.manager
    manager.update_services(core_services)
    

    # 4. Hook startup
    await xhooks.emit("xcore.startup")
    # 5. Démarrage des plugins
    report = await manager.start()
    print(f"✅ Plugins chargés : {report['loaded']}")
    if report["failed"]:
        print(f"❌ Échecs          : {report['failed']}")

    yield

    await manager.stop()
    await integration.shutdown()
    await xhooks.emit("xcore.shutdown")


app = FastAPI(title="Mon API", lifespan=lifespan)

manager = Manager(
    app=app,
    base_routes=list(app.routes),
    plugins_dir="plugins",
    secret_key=b"ejkfnwefnkejw",
    services={},  # vide ici — rempli dans lifespan via update_services()
    interval=2,
    strict_trusted=True,
)

app.state.manager = manager
app.state.integration = integration


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/services/status")
async def services_status():
    return integration.status()


@app.get("/plugins/status")
async def plugins_status():
    return app.state.manager.status()
