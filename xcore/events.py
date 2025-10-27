from admin.service import init_root_admin
from xcore import app
from xcore.manage import manager, taskRuntimer


@app.on_event("startup")
async def startup_event():

    from database.db import get_db

    init_root_admin(next(get_db()))

    manager.run_plugins()
    taskRuntimer.on_startup()


@app.on_event("shutdown")
async def shutdown_event():
    manager.stop_watching()
    taskRuntimer.on_shutdown()
    manager.close_db()
