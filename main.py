from fastapi import FastAPI,Depends
import manager.runtimer as taskRuntimer
from config import Configure, XCore
from loggers.logger_config import get_logger
from manager import AppType, Manager, cfg
from manager.routes.task import task
from admin.routes import adminrouter
from admin.service import init_root_admin
from auth.routes import authRouter
from database.db import get_db


app = FastAPI(title="Core API with Plugin System", version="1.0.0")


xcfg = XCore(conf=Configure(file="./config.json"))


# base router
app.include_router(task)
app.include_router(authRouter)
app.include_router(adminrouter)



logger = get_logger(
    "Xcore", log_file=xcfg.get("log", "file"), console=xcfg.get("log", "console")
)



manager = Manager(
    app=app,
    entry_point=cfg.get("plugins", "entry_point"),
    plugins_dir=cfg.get("plugins", "directory"),
    interval=cfg.get("plugins", "interval"),
    app_type=AppType.FASTAPI,
    base_routes=app.routes,
)


manager.snapshot.ignore_ext = cfg.get("snapshot", "extensions")
manager.snapshot.ignore_file = cfg.get("snapshot", "filenames")
manager.snapshot.ignore_hidden = cfg.get("snapshot", "hidden")


@app.on_event("startup")
async def startup_event():
    init_root_admin(next(get_db()))
    manager.run_plugins()
    taskRuntimer.on_startup()


@app.on_event("shutdown")
async def shutdown_event():
    manager.stop_watching()
    taskRuntimer.on_shutdown()
    manager.close_db()
