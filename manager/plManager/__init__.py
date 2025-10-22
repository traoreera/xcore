from loggers.logger_config import get_logger, logging
from manager.conf import cfg
get_logger("Manager").info("Starting plManager")

logger = get_logger(
    "Manager",
    log_file=cfg.get('log', "file"),
    console=cfg.get('log', "console"),
)