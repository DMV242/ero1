import networkx as nx
from priorities import streets_near_points


def _proj_graph():
    # Coordonnées en mètres (graphe déjà projeté). Arête 1-2 près de l'origine,
    # arête 3-4 à 1000 m.
    G = nx.MultiDiGraph()
    G.add_node(1, x=0.0, y=0.0)
    G.add_node(2, x=100.0, y=0.0)
    G.add_node(3, x=1000.0, y=0.0)
    G.add_node(4, x=1100.0, y=0.0)
    G.add_edge(1, 2)
    G.add_edge(3, 4)
    return G


def test_streets_near_points_marks_only_close_streets():
    points = [(10.0, 5.0)]  # POI à 5 m de l'arête 1-2
    prio = streets_near_points(_proj_graph(), points, dist=150.0)
    assert (1, 2) in prio
    assert (3, 4) not in prio
