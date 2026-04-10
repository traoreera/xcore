"""
— Xcore logging configuration.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...configurations.sections import LoggingConfig


def configure_logging(cfg: "LoggingConfig") -> None:
    """Configure logging."""
    level = getattr(logging, cfg.level.upper(), logging.INFO)
    root = logging.getLogger("xcore")
    root.setLevel(level)

    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(cfg.format))
        root.addHandler(handler)

    if cfg.file:
        p = Path(cfg.file)
        p.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(
            p, maxBytes=cfg.max_bytes, backupCount=cfg.backup_count
        )
        fh.setFormatter(logging.Formatter(cfg.format))
        root.addHandler(fh)


def get_logger(name: str) -> logging.Logger:
    """RETURN LOGGER FOR XCORE MODULE."""
    return logging.getLogger(name if name.startswith("xcore") else f"xcore.{name}")
