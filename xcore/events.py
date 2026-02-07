from admin.service import init_root_admin
from xcore import app
from xcore.appcfg import logger, xhooks


@app.on_event("startup")
async def startup_event():
    logger.info("Starting up xcore application")
    return await xhooks.emit("xcore.startup")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down xcore application")
    return await xhooks.emit("xcore.shutdown")
