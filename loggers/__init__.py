"""
Module for creating and configuring loggers

"""

from .logger_config import ColoredFormatter, get_logger

__all__ = [
    "get_logger",
    "ColoredFormatter",
]
__annotations__ = {
    "get_logger": "Callable[[str, str], logging.Logger]",
    "ColoredFormatter": "Callable[[str, str], logging.Formatter]",
}
__doc__ = "Module for creating and configuring loggers"
__version__ = "1.0.0"
__author__ = "Traoreera"
__license__ = "MIT"
__copyright__ = "Copyright (c) 2026 Xcore team Development"
__email__ = "traoreera@gmail.com"
__url__ = "https://github.com/traoreera/xcore"
__package__ = "xcore.loggers"
__name__ = "xcore.loggers"
