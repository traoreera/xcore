from admin.service import init_root_admin
from xcore import app
from xcore.hooks import HookManager


hooks = HookManager()


@app.on_event("startup")
async def startup_event():
    return await hooks.emit(event_name="xcore.startup",)

@app.on_event("shutdown")
async def shutdown_event():
    return await hooks.emit(event_name="xcore.shutdown",)
