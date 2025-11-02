from configurations import core
from loggers.logger_config import get_logger

xcfg = core.Xcorecfg(conf=core.Configure())

logger = get_logger(
    module_name="xcore",
    log_file=xcfg.custom_config["logs"]["file"],
    console=xcfg.custom_config["logs"]["console"],
)
