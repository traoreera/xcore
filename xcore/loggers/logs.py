import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler

# ==========================================================
# Configuration Models
# ==========================================================
from xcore.integration.config.schemas import LoggingConfig

# ==========================================================
# Logs System
# ==========================================================


class Logs:
    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
        "RESET": "\033[0m",
    }

    ICONS = {
        "DEBUG": "[DEB]",
        "INFO": "[INF]",
        "WARNING": "[WARN]",
        "ERROR": "[ERR]",
        "CRITICAL": "[CRIT]",
    }

    def __init__(self, name: str, config: LoggingConfig):
        self.name = name
        self.config = config
        self.logger = logging.getLogger(name)
        self._configure()

    # --------------------------------------------------
    # Core configuration
    # --------------------------------------------------

    def _configure(self):
        level = getattr(logging, self.config.level.upper(), logging.INFO)

        self.logger.setLevel(level)
        self.logger.handlers.clear()
        self.logger.propagate = False

        if self.config.handlers.console.enabled:
            self._add_console_handler(level)

        if self.config.handlers.file.enabled:
            self._add_file_handler(level)

    def _add_console_handler(self, level: int):
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        handler.setFormatter(self._ColoredFormatter())
        self.logger.addHandler(handler)

    def _add_file_handler(self, level: int):
        file_conf = self.config.handlers.file

        os.makedirs(os.path.dirname(file_conf.path), exist_ok=True)

        handler = RotatingFileHandler(
            file_conf.path,
            maxBytes=file_conf.max_bytes,
            backupCount=file_conf.backup_count,
            encoding="utf-8",
        )

        handler.setLevel(level)
        formatter = logging.Formatter(self.config.format)
        handler.setFormatter(formatter)

        self.logger.addHandler(handler)

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def get(self) -> logging.Logger:
        return self.logger

    # --------------------------------------------------
    # Colored Formatter
    # --------------------------------------------------

    class _ColoredFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            color = Logs.COLORS.get(record.levelname, Logs.COLORS["RESET"])
            reset = Logs.COLORS["RESET"]
            icon = Logs.ICONS.get(record.levelname, "")

            formatted_time = datetime.fromtimestamp(record.created).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            message = f"{icon} {formatted_time} - {record.name} - {record.getMessage()}"

            if record.exc_info:
                message += f"\n{self.formatException(record.exc_info)}"

            return f"{color}{message}{reset}"
