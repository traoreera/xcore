from configurations import core
from hooks import HookManager
from loggers.logger_config import get_logger

xcfg = core.Xcorecfg(conf=core.Configure())

# Global hook manager instance
xhooks = HookManager()

logger = get_logger(
    module_name="xcore",
    log_file=xcfg.custom_config["logs"]["file"],
    console=xcfg.custom_config["logs"]["console"],
)


xhooks.add_pre_interceptor("xcore.startup", logger.info, priority=50)
xhooks.add_pre_interceptor("xcore.shutdown", logger.info, priority=50)
