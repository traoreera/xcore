"""
versioning.py — Contraintes de version pour le registry.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
_CONSTRAINT = re.compile(r"([><=!]+)\s*(\d+\.\d+(?:\.\d+)?)")


@dataclass(frozen=True, order=True)
class VersionConstraint:
    major: int
    minor: int
    patch: int = 0

    @classmethod
    def parse(cls, v: str) -> "VersionConstraint":
        v = v.strip()
        m = _SEMVER.match(v)
        if m:
            return cls(*map(int, m.groups()))
        # essai sans patch
        m2 = re.match(r"^(\d+)\.(\d+)$", v)
        if m2:
            major, minor = map(int, m2.groups())
            return cls(major, minor, 0)
        raise ValueError(f"Version invalide : {v!r}")

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


def satisfies(version_str: str, constraint_expr: str) -> bool:
    """
    Vérifie si une version satisfait une contrainte.

    Examples:
        satisfies("2.1.0", ">=2.0")       → True
        satisfies("1.9.0", ">=2.0")       → False
        satisfies("2.1.0", ">=2.0,<3.0") → True
        satisfies("3.0.0", ">=2.0,<3.0") → False
    """
    v = VersionConstraint.parse(version_str)

    for part in constraint_expr.split(","):
        part = part.strip()
        m = _CONSTRAINT.match(part)
        if not m:
            continue
        op, target_str = m.group(1), m.group(2)
        t = VersionConstraint.parse(target_str)

        ok_map = {
            ">=": v >= t,
            "<=": v <= t,
            ">": v > t,
            "<": v < t,
            "==": v == t,
            "!=": v != t,
        }
        if not ok_map.get(op, True):
            return False
    return True
