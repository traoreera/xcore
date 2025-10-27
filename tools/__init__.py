from config import Configure, Migration
from loggers.logger_config import get_logger

cfg = Migration(conf=Configure())

logger = get_logger(
    "Migration", log_file=cfg.get("log", "file"), console=cfg.get("log", "console")
)
