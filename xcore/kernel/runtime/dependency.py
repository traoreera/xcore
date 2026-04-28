"""
dependency.py — Utility for managing plugin dependency graphs.
"""

from __future__ import annotations

import logging
from collections import deque
from typing import Generic, TypeVar

T = TypeVar("T")

logger = logging.getLogger("xcore.runtime.dependency")


class DependencyGraph(Generic[T]):
    """
    Directed Acyclic Graph (DAG) for managing dependencies between items of type T.
    Items are identified by a unique name.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, T] = {}
        # node -> set of nodes it depends on
        self._dependencies: dict[str, set[str]] = {}
        # node -> set of nodes that depend on it
        self._dependents: dict[str, set[str]] = {}

    def add_node(self, name: str, data: T) -> None:
        """Adds a node to the graph with its associated data."""
        self._nodes[name] = data
        if name not in self._dependencies:
            self._dependencies[name] = set()
        if name not in self._dependents:
            self._dependents[name] = set()

    def add_dependency(self, node: str, depends_on: str) -> None:
        """
        Adds a directed edge: node -> depends_on.
        Means 'node' requires 'depends_on'.
        """
        if node not in self._nodes:
            raise ValueError(f"Node '{node}' not in graph. Call add_node first.")
        if depends_on not in self._nodes:
            # Note: We might want to allow external dependencies that are not in this batch,
            # but for topo_sort within a batch, both must be present.
            raise ValueError(f"Dependency '{depends_on}' not in graph.")

        self._dependencies[node].add(depends_on)
        self._dependents[depends_on].add(node)

    def get_ordered(self) -> list[T]:
        """
        Returns nodes in topological order (Kahn's algorithm).
        Nodes with zero dependencies come first.

        Raises:
            ValueError: if a circular dependency is detected.
        """
        # Kahn's algorithm
        # Copy in-degrees (number of dependencies each node has)
        in_degree = {name: len(deps) for name, deps in self._dependencies.items()}

        # Queue of nodes with no dependencies
        queue = deque([name for name, degree in in_degree.items() if degree == 0])

        ordered_names = []
        while queue:
            name = queue.popleft()
            ordered_names.append(name)

            # For each node that depends on 'name'
            for dependent in self._dependents[name]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(ordered_names) != len(self._nodes):
            remaining = set(self._nodes.keys()) - set(ordered_names)
            raise ValueError(
                f"Circular dependency detected involving: {sorted(list(remaining))}"
            )

        return [self._nodes[name] for name in ordered_names]

    def __contains__(self, name: str) -> bool:
        return name in self._nodes

    def get_data(self, name: str) -> T:
        return self._nodes[name]
