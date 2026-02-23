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
from xcore.integration.services.database import AsyncSQLAdapter
from xcore.manager import Manager

Base = declarative_base()
_plugin_hooks = HookManager()
integration = Integration("./integration.yaml")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────
    await integration.init()
    await xhooks.emit("xcore.startup")

    yield  # app tourne ici

    # ── Shutdown — ordre garanti dans le même contexte async ──
    await xhooks.emit("xcore.shutdown")

    # dispose() explicite obligatoire pour aiosqlite/asyncpg
    # avant la fin de la boucle event, sinon le GC lève le warning
    try:
        ddb: AsyncSQLAdapter = integration.db.get("default")
        await ddb.engine.dispose()
    except Exception:
        pass

    await integration.shutdown()


app = FastAPI(title="Mon API", lifespan=lifespan)

manager = Manager(
    app=app,
    base_routes=list(app.routes),
    plugins_dir="plugins",
    secret_key=b"ejkfnwefnkejw",
    services={},
    interval=2,
    strict_trusted=True,
)


@xhooks.on("xcore.startup")
async def manager_setup(event: Event):
    ddb: AsyncSQLAdapter = integration.db.get("default")
    core_services = {
        "db": ddb,
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


app.state.manager = manager
app.state.integration = integration
