from config import Configure, XCore
from loggers.logger_config import get_logger

xcfg = XCore(conf=Configure(file="./config.json"))

logger = get_logger(
    "Xcore", log_file=xcfg.get("log", "file"), console=xcfg.get("log", "console")
)
