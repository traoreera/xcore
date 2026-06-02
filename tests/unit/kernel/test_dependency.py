import pytest

from xcore.registry.resolver import (
    CircularDependencyError,
    DependencyResolver,
    MissingDependencyError,
)


def test_resolver_ordered():
    resolver = DependencyResolver()
    resolver.add("A", [])
    resolver.add("B", ["A"])
    resolver.add("C", ["B"])

    ordered = resolver.resolve()
    assert ordered == ["A", "B", "C"]


def test_resolver_cycle():
    resolver = DependencyResolver()
    resolver.add("A", ["B"])
    resolver.add("B", ["A"])

    with pytest.raises(CircularDependencyError):
        resolver.resolve()


def test_resolver_missing_dependency():
    resolver = DependencyResolver()
    resolver.add("A", ["B"])

    with pytest.raises(MissingDependencyError):
        resolver.resolve()


def test_resolver_waves():
    resolver = DependencyResolver()
    resolver.add("A", [])
    resolver.add("B", [])
    resolver.add("C", ["A", "B"])

    waves = resolver.waves()
    assert len(waves) == 2
    assert set(waves[0]) == {"A", "B"}
    assert waves[1] == ["C"]
