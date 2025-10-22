from loggers.logger_config import get_logger
from config import Configure,Migration


cfg= Migration(conf=Configure(file="./config.json"))

logger = get_logger("Migration", log_file=cfg.get('log', "file"), console=cfg.get('log', "console"))

