import manager.runtimer as taskRuntimer
from manager import Manager, cfg
from xcore import app

# cread plugin manager service
manager = Manager(
    app=app,
    entry_point=cfg.custom_config["plugins"]["entry_point"],
    plugins_dir=cfg.custom_config["plugins"]["directory"],
    interval=cfg.custom_config["plugins"]["interval"],
    base_routes=app.routes,
)


# set snapshot config
manager.snapshot.ignore_ext = cfg.custom_config["snapshot"]["extensions"]
manager.snapshot.ignore_file = cfg.custom_config["snapshot"]["filenames"]
manager.snapshot.ignore_hidden = cfg.custom_config["snapshot"]["hidden"]
