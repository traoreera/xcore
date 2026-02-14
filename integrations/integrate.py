import integrations.runtimer as taskRuntimer
from xcore.hooks.hooks import Event
from integrations import Manager, cfg
from xcore.appcfg import xhooks
from app import app

# Create plugin manager service
manager = Manager(
    app=app,
    entry_point=cfg.custom_config["plugins"]["entry_point"],
    plugins_dir="xcore_modules",
    interval=cfg.custom_config["plugins"]["interval"],
    base_routes=app.routes,
)


# Set snapshot config
manager.snapshot.ignore_ext = cfg.custom_config["snapshot"]["extensions"]
manager.snapshot.ignore_file = cfg.custom_config["snapshot"]["filenames"]
manager.snapshot.ignore_hidden = cfg.custom_config["snapshot"]["hidden"]


@xhooks.on("xcore.startup")
async def startup_event(event: Event) -> None:
    """Handle application startup."""
    manager.run_plugins()
    taskRuntimer.on_startup()
    # manager.base_routes = app.routes  # Capture les routes de base après le chargement des plugins

    return  # Explicit return for clarity


@xhooks.on("xcore.shutdown")
async def shutdown_event(event: Event) -> None:
    """Handle application shutdown."""
    manager.stop_watching()
    taskRuntimer.on_shutdown()
    manager.close_db()

    return  # Explicit return for clarity