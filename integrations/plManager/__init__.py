from loggers import get_logger

from ..conf import cfg

try:
    logger = get_logger(
        module_name="Manager",
        log_file=cfg.custom_config["log"]["file"],
        console=cfg.custom_config["log"]["console"],
    )

except ImportError:
    import logging

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)


if __name__ == "__main__":
    logger.info("Manager started")
