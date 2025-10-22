import logging
import os
import sys
from datetime import datetime
from typing import Optional


class ColoredFormatter(logging.Formatter):
    """Formateur coloré pour les logs"""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Vert
        "WARNING": "\033[33m",  # Jaune
        "ERROR": "\033[31m",  # Rouge
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",
    }

    ICONS = {
        "DEBUG": "🔍",
        "INFO": "ℹ️ ",
        "WARNING": "⚠️ ",
        "ERROR": "❌",
        "CRITICAL": "🚨",
    }

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        reset = self.COLORS["RESET"]
        icon = self.ICONS.get(record.levelname, "")

        formatted_time = datetime.fromtimestamp(record.created).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        log_format = f"{color}{icon} [{record.levelname}] {formatted_time} - {record.name} - {record.getMessage()}{reset}"

        if record.exc_info:
            log_format += f"\n{color}{self.formatException(record.exc_info)}{reset}"

        return log_format


def get_log_level() -> int:
    """Récupère le niveau de log depuis la variable d'environnement LOG_LEVEL"""
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    return getattr(logging, level_name, logging.INFO)


def setup_logger(
    name: str, log_file: Optional[str] = None, console: bool = True
) -> logging.Logger:
    """
    Configure un logger avec formatage coloré + fichier
    - console=True  -> console + fichier
    - console=False -> uniquement fichier
    """
    logger = logging.getLogger(name)
    level = get_log_level()
    logger.setLevel(level)

    # Nettoyer les handlers existants
    logger.handlers.clear()

    # Handler console (optionnel)
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(ColoredFormatter())
        logger.addHandler(console_handler)

    # Handler fichier (toujours actif si log_file est fourni)
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(
    module_name: str,
    log_file: Optional[str]='app.log',
    console: bool=True,
) -> logging.Logger:
    """Récupère un logger configuré"""
    log_path = os.path.join("./logs", log_file) if log_file else None
    return setup_logger(module_name, log_file=log_path, console=console)
