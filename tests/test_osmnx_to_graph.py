import networkx as nx
from snowplow_routing import osmnx_to_graph


def _toy_graph():
    # Petit MultiDiGraph fortement connexe : 1<->2, 2<->3 (deux sens), 1->3 (sens unique).
    G = nx.MultiDiGraph()
    G.add_edge(1, 2, length=100.0)
    G.add_edge(2, 1, length=100.0)
    G.add_edge(2, 3, length=200.0)
    G.add_edge(3, 2, length=200.0)
    G.add_edge(1, 3, length=50.0)
    return G


def test_returns_lengths_and_classifies_streets():
    vertices, edges, arcs, lengths = osmnx_to_graph(_toy_graph())
    assert set(vertices) == {1, 2, 3}
    # 1-2 et 2-3 sont à double sens -> arêtes ; 1->3 est à sens unique -> arc.
    edge_pairs = {frozenset((i, j)) for i, j, _ in edges}
    assert edge_pairs == {frozenset((1, 2)), frozenset((2, 3))}
    assert [(i, j) for i, j, _ in arcs] == [(1, 3)]
    assert lengths[(1, 3)] == 50.0
    assert lengths[(1, 2)] == 100.0
