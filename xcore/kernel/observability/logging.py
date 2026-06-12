"""
Logging xcore — logger structuré avec sortie texte ou JSON.

Usage :
    from xcore.kernel.observability import get_logger

    logger = get_logger("xcore.services.scheduler")

    # Simple log
    logger.info("scheduler started")

    # Structured log (fields added to JSON or appended to message in text mode)
    logger.info("scheduler started", timezone="Europe/Paris", backend="redis")
    logger.error("connection failed", service="db", error=str(e))
    logger.debug("job skipped", job_id="acme.cleanup", reason="already running")

Text format:
    2026-05-29 14:08:03 [INFO ] xcore.scheduler — scheduler started  backend=redis timezone=Europe/Paris

JSON format:
    {"ts":"2026-05-29T14:08:03.688","level":"INFO","logger":"xcore.scheduler",
     "msg":"scheduler started","backend":"redis","timezone":"Europe/Paris"}
"""

from __future__ import annotations

import json
import logging
import logging.handlers
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...configurations.sections import LoggingConfig

# ── Formateurs ────────────────────────────────────────────────────────────────


class _TextFormatter(logging.Formatter):
    """Format lisible en console avec les champs structurés en fin de ligne."""

    LEVEL_WIDTH = 8  # "CRITICAL" est le plus long

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        level = f"{record.levelname:<{self.LEVEL_WIDTH}}"
        ctx: dict = getattr(record, "xcore_ctx", {})
        fields = "  " + "  ".join(f"{k}={v}" for k, v in ctx.items()) if ctx else ""

        base = f"{ts} [{level}] {record.name} — {record.getMessage()}{fields}"

        if record.exc_info:
            base = f"{base}\n{self.formatException(record.exc_info)}"
        return base


class _JsonFormatter(logging.Formatter):
    """Format JSON une ligne par entrée — compatible avec les agrégateurs de logs."""

    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        ctx: dict = getattr(record, "xcore_ctx", {})
        data.update(ctx)

        if record.exc_info:
            data["trace"] = self.formatException(record.exc_info)

        return json.dumps(data, ensure_ascii=False, default=str)


# ── Logger structuré ──────────────────────────────────────────────────────────


class XcoreLogger:
    """
    Wrapper autour de logging.Logger qui accepte des champs structurés en kwargs.

        logger.info("scheduler started", timezone="Europe/Paris", backend="redis")

    Les kwargs sont transmis au formateur via LogRecord.xcore_ctx et rendus soit
    en ligne (mode texte) soit en champs JSON (mode json).
    """

    __slots__ = ("_log",)

    def __init__(self, logger: logging.Logger) -> None:
        self._log = logger

    @property
    def name(self) -> str:
        return self._log.name

    def _emit(
        self,
        level: int,
        msg: str,
        *args: Any,
        exc_info: bool = False,
        **fields: Any,
    ) -> None:
        if not self._log.isEnabledFor(level):
            return
        extra = {"xcore_ctx": fields} if fields else {}
        self._log.log(level, msg, *args, exc_info=exc_info, extra=extra)

    def debug(self, msg: str, *args: Any, **fields: Any) -> None:
        self._emit(logging.DEBUG, msg, *args, **fields)

    def info(self, msg: str, *args: Any, **fields: Any) -> None:
        self._emit(logging.INFO, msg, *args, **fields)

    def warning(self, msg: str, *args: Any, **fields: Any) -> None:
        self._emit(logging.WARNING, msg, *args, **fields)

    def error(self, msg: str, *args: Any, **fields: Any) -> None:
        self._emit(logging.ERROR, msg, *args, **fields)

    def exception(self, msg: str, *args: Any, **fields: Any) -> None:
        self._emit(logging.ERROR, msg, *args, exc_info=True, **fields)

    def critical(self, msg: str, *args: Any, **fields: Any) -> None:
        self._emit(logging.CRITICAL, msg, *args, **fields)

    def setLevel(self, level: int | str) -> None:
        self._log.setLevel(level)

    def isEnabledFor(self, level: int) -> bool:
        return self._log.isEnabledFor(level)


# ── Configuration ─────────────────────────────────────────────────────────────


def configure_logging(cfg: "LoggingConfig") -> None:
    """Configure le logger racine xcore selon la configuration."""
    level = getattr(logging, cfg.level.upper(), logging.INFO)
    root = logging.getLogger("xcore")
    root.setLevel(level)

    formatter: logging.Formatter
    if getattr(cfg, "output", "text") == "json":
        formatter = _JsonFormatter()
    else:
        formatter = _TextFormatter()

    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        root.addHandler(handler)
    else:
        for h in root.handlers:
            h.setFormatter(formatter)

    if cfg.file:
        p = Path(cfg.file)
        p.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(
            p, maxBytes=cfg.max_bytes, backupCount=cfg.backup_count
        )
        fh.setFormatter(formatter)
        root.addHandler(fh)


def get_logger(name: str) -> XcoreLogger:
    """Retourne un XcoreLogger pour le module donné."""
    full_name = name if name.startswith("xcore") else f"xcore.{name}"
    return XcoreLogger(logging.getLogger(full_name))
