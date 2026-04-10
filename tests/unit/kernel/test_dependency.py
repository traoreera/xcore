import pytest

from xcore.kernel.runtime.dependency import DependencyGraph


def test_dependency_graph_ordered():
    graph = DependencyGraph()
    graph.add_node("A", "dataA")
    graph.add_node("B", "dataB")
    graph.add_node("C", "dataC")

    # B -> A (B depends on A)
    # C -> B (C depends on B)
    graph.add_dependency("B", "A")
    graph.add_dependency("C", "B")

    ordered = graph.get_ordered()
    assert ordered == ["dataA", "dataB", "dataC"]


def test_dependency_graph_cycle():
    graph = DependencyGraph()
    graph.add_node("A", 1)
    graph.add_node("B", 2)
    graph.add_dependency("A", "B")
    graph.add_dependency("B", "A")

    with pytest.raises(ValueError, match="Circular dependency"):
        graph.get_ordered()


def test_dependency_graph_missing_node():
    graph = DependencyGraph()
    graph.add_node("A", 1)
    with pytest.raises(ValueError):
        graph.add_dependency("A", "B")
