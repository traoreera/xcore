import json
import re
from datetime import datetime
from typing import Any


def filter_truncate(text: str, length: int = 100, suffix: str = "..."):
    """Truncate text to specified length"""
    if len(text) <= length:
        return text
    return text[:length].rsplit(" ", 1)[0] + suffix


def filter_slugify(text: str):
    """Convert text to URL-friendly slug"""
    return re.sub(r"[-\s]+", "-", re.sub(r"[^\w\s-]", "", text.lower().strip()))


def filter_currency(value: float, symbol: str = "$", decimals: int = 2):
    """Format number as currency"""
    return f"{symbol}{value:,.{decimals}f}"


def filter_timeago(dt: datetime):
    now = datetime.now()
    diff = now - dt
    seconds = diff.total_seconds()

    intervals = (
        (60, "à l'instant", None),  # < 1 min
        (3600, "minute", 60),
        (86400, "heure", 3600),
        (None, "jour", 86400),
    )

    for limit, label, divisor in intervals:
        if limit is None or seconds < limit:
            if divisor is None:
                return "à l'instant"

            value = int(seconds // divisor)
            plural = "s" if value > 1 else ""
            return f"il y a {value} {label}{plural}"


def filter_json_pretty(obj: Any):
    """Pretty print JSON"""
    return json.dumps(obj, indent=2, ensure_ascii=False)
