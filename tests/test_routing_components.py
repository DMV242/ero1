from snowplow_routing import solve_sector, build_route_all
from scenarios import coverage_over_time


def test_build_route_all_covers_disconnected_priority():
    # Deux triangles disjoints (A-B-C et D-E-F) reliés par une arête NON prioritaire
    # et chère (C-D). L'optimum couvre chaque triangle comme un circuit séparé.
    vertices = ["A", "B", "C", "D", "E", "F"]
    edges = [
        ("A", "B", 1), ("B", "C", 1), ("C", "A", 1),
        ("D", "E", 1), ("E", "F", 1), ("F", "D", 1),
        ("C", "D", 50),
    ]
    required = {("A", "B"), ("B", "C"), ("C", "A"),
                ("D", "E"), ("E", "F"), ("F", "D")}
    cost, passes = solve_sector(vertices, edges, [], required=required)
    route = build_route_all(passes)

    # Toutes les rues prioritaires apparaissent dans la route concaténée.
    driven = {frozenset(p) for p in zip(route, route[1:])}
    for (u, v) in required:
        assert frozenset((u, v)) in driven

    # La couverture du réseau prioritaire atteint 100 %.
    lengths = {}
    for u, v, _ in edges:
        lengths[(u, v)] = 1000.0
        lengths[(v, u)] = 1000.0
    cov = coverage_over_time(route, lengths, required, times_h=[100.0])
    assert round(cov[100.0], 6) == 1.0
