import manager.runtimer as taskRuntimer
from manager import Manager, cfg
from xcore import app

# cread plugin manager service
manager = Manager(
    app=app,
    entry_point=cfg.get("plugins", "entry_point"),
    plugins_dir=cfg.get("plugins", "directory"),
    interval=cfg.get("plugins", "interval"),
    base_routes=app.routes,
)


# set snapshot config
manager.snapshot.ignore_ext = cfg.get("snapshot", "extensions")
manager.snapshot.ignore_file = cfg.get("snapshot", "filenames")
manager.snapshot.ignore_hidden = cfg.get("snapshot", "hidden")
