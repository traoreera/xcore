from xcore.manager import Manager
from app import app, manager

from xcore.sandbox.sandbox.worker import _main


@app.on_event("startup")
async def startup_event():
    await manager.start()
    await _main()


@app.on_event("shutdown")
async def shutdown_event():
    await manager.stop()
