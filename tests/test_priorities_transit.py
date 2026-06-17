import networkx as nx
from shapely.geometry import LineString
from priorities import streets_intersecting_lines


def _proj_graph():
    G = nx.MultiDiGraph()
    G.add_node(1, x=0.0, y=0.0)
    G.add_node(2, x=100.0, y=0.0)
    G.add_node(3, x=0.0, y=500.0)
    G.add_node(4, x=100.0, y=500.0)
    G.add_edge(1, 2)  # ligne de bus passe ici (y=0)
    G.add_edge(3, 4)  # loin (y=500)
    return G


def test_streets_intersecting_lines():
    bus_line = LineString([(-50.0, 0.0), (150.0, 0.0)])  # longe l'arête 1-2
    prio = streets_intersecting_lines(_proj_graph(), [bus_line], buffer_m=20.0)
    assert (1, 2) in prio
    assert (3, 4) not in prio
