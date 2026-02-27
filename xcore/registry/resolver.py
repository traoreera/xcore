"""
resolver.py — Résolution de dépendances et tri topologique.
"""

from __future__ import annotations

from collections import deque


class CircularDependencyError(Exception):
    pass


class MissingDependencyError(Exception):
    pass


class DependencyResolver:
    """
    Tri topologique (Kahn) d'un graphe de plugins.

    Usage:
        resolver = DependencyResolver()
        resolver.add("auth",    requires=[])
        resolver.add("users",   requires=["auth"])
        resolver.add("billing", requires=["auth", "users"])

        order = resolver.resolve()
        # ["auth", "users", "billing"]
    """

    def __init__(self) -> None:
        self._nodes: dict[str, list[str]] = {}

    def add(self, name: str, requires: list[str]) -> None:
        self._nodes[name] = requires

    def remove(self, name: str) -> None:
        self._nodes.pop(name, None)

    def resolve(self) -> list[str]:
        """
        Retourne la liste des noms dans l'ordre de chargement.
        Lève CircularDependencyError ou MissingDependencyError.
        """
        all_names = set(self._nodes.keys())

        # Vérification des dépendances manquantes
        for name, deps in self._nodes.items():
            for dep in deps:
                if dep not in all_names:
                    raise MissingDependencyError(
                        f"[{name}] Dépendance '{dep}' introuvable. "
                        f"Disponibles : {sorted(all_names)}"
                    )

        # Kahn
        in_degree: dict[str, int] = {n: 0 for n in all_names}
        reverse: dict[str, list[str]] = {n: [] for n in all_names}

        for name, deps in self._nodes.items():
            for dep in deps:
                reverse[dep].append(name)
                in_degree[name] += 1

        queue: deque[str] = deque(sorted(n for n, d in in_degree.items() if d == 0))
        result: list[str] = []

        while queue:
            name = queue.popleft()
            result.append(name)
            for dependent in sorted(reverse[name]):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(result) != len(all_names):
            remaining = sorted(all_names - set(result))
            raise CircularDependencyError(
                f"Dépendances circulaires détectées : {remaining}"
            )

        return result

    def waves(self) -> list[list[str]]:
        """
        Retourne les vagues de chargement parallèles.
        Chaque vague peut être chargée en parallèle.
        """
        all_names = set(self._nodes.keys())
        resolved: set[str] = set()
        remaining = set(all_names)
        result: list[list[str]] = []

        while remaining:
            wave = sorted(
                n
                for n in remaining
                if all(dep in resolved for dep in self._nodes.get(n, []))
            )
            if not wave:
                raise CircularDependencyError(
                    f"Dépendances circulaires : {sorted(remaining)}"
                )
            result.append(wave)
            resolved.update(wave)
            remaining -= set(wave)

        return result
