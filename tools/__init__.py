from configurations.migrations import Configure, Migration
from loggers.logger_config import get_logger

cfg = Migration(conf=Configure())

logger = get_logger(
    "Migration",
    log_file=cfg.custom_config["logger"]["file"],
    console=cfg.custom_config["logger"]["console"],
)
