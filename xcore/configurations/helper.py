from __future__ import annotations

import logging
import os
import re
from typing import Any

_ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")

logger = logging.getLogger("xcore.config")


def _resolve(value: Any) -> Any:
    """Remplace ${VAR} dans toute la structure YAML."""
    if isinstance(value, str):

        def _sub(m: re.Match) -> str:
            var = m.group(1)
            resolved = os.environ.get(var)
            if resolved is None:
                logger.warning(f"Variable d'environnement non définie : ${{{var}}}")
                return ""
            return resolved

        return _ENV_PATTERN.sub(_sub, value)
    if isinstance(value, dict):
        return {k: _resolve(v) for k, v in value.items()}
    return [_resolve(v) for v in value] if isinstance(value, list) else value
