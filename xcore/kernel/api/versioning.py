"""
versioning.py — Vérification de compatibilité framework/plugin.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_VERSION_RE = re.compile(r"^(\d+)\.(\d+)(?:\.(\d+))?$")


@dataclass(frozen=True)
class APIVersion:
    major: int
    minor: int
    patch: int = 0

    @classmethod
    def parse(cls, v: str) -> "APIVersion":
        m = _VERSION_RE.match(v.strip())
        if not m:
            raise ValueError(f"Version invalide : {v!r}")
        parts = [int(x) for x in m.groups() if x is not None]
        return cls(*parts) if len(parts) == 3 else cls(parts[0], parts[1])

    def __ge__(self, other: "APIVersion") -> bool:
        return (self.major, self.minor, self.patch) >= (
            other.major,
            other.minor,
            other.patch,
        )

    def __le__(self, other: "APIVersion") -> bool:
        return (self.major, self.minor, self.patch) <= (
            other.major,
            other.minor,
            other.patch,
        )

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


def check_compatibility(framework_version_expr: str, core_version: str) -> bool:
    """
    Vérifie la compatibilité selon l'expression du manifeste.
    Exemples : ">=1.0", ">=1.0,<3.0", "==2.0"
    """
    core = APIVersion.parse(core_version)
    for part in framework_version_expr.split(","):
        part = part.strip()
        for op in (">=", "<=", ">", "<", "=="):
            if part.startswith(op):
                target = APIVersion.parse(part[len(op) :])
                ok = {
                    ">=": core >= target,
                    "<=": core <= target,
                    ">": (core.major, core.minor, core.patch)
                    > (target.major, target.minor, target.patch),
                    "<": (core.major, core.minor, core.patch)
                    < (target.major, target.minor, target.patch),
                    "==": core == target,
                }[op]
                if not ok:
                    return False
                break
    return True
