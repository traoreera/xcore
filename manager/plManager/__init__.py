from manager.conf import cfg

try:
    from loggers.logger_config import get_logger, logging

    get_logger("Manager").info("Starting plManager")
    logger = get_logger(
        "Manager",
        log_file=cfg.get("log", "file"),
        console=cfg.get("log", "console"),
    )

except ImportError:
    import logging

    logger = logging.getLogger()


__all__ = ["get_logger", "logger"]
