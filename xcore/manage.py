import manager.runtimer as taskRuntimer
from hooks import Event
from manager import Manager, cfg
from xcore import app
from xcore.events import xhooks

# Create plugin manager service
manager = Manager(
    app=app,
    entry_point=cfg.custom_config["plugins"]["entry_point"],
    plugins_dir=cfg.custom_config["plugins"]["directory"],
    interval=cfg.custom_config["plugins"]["interval"],
    base_routes=app.routes,
)


# Set snapshot config
manager.snapshot.ignore_ext = cfg.custom_config["snapshot"]["extensions"]
manager.snapshot.ignore_file = cfg.custom_config["snapshot"]["filenames"]
manager.snapshot.ignore_hidden = cfg.custom_config["snapshot"]["hidden"]


@xhooks.on("xcore.startup")
async def startup_event(event: Event):
    """Handle application startup."""
    manager.run_plugins()
    taskRuntimer.on_startup()


@xhooks.on("xcore.shutdown")
async def shutdown_event(event: Event):
    """Handle application shutdown."""
    manager.stop_watching()
    taskRuntimer.on_shutdown()
    manager.close_db()
