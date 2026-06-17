import networkx as nx
from priorities import arterial


def test_arterial_selects_major_roads_only():
    G = nx.MultiDiGraph()
    G.add_edge(1, 2, highway="primary")
    G.add_edge(2, 3, highway="residential")
    G.add_edge(3, 4, highway=["secondary", "tertiary"])  # OSM peut donner une liste
    G.add_edge(4, 5, highway="service")
    prio = arterial(G)
    assert (1, 2) in prio
    assert (3, 4) in prio
    assert (2, 3) not in prio
    assert (4, 5) not in prio
