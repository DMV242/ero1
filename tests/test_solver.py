from snowplow_routing import solve_sector

# Triangle A-B-C (arêtes coût 1) + un éperon C-D coûteux (arête coût 10).
VERTICES = ["A", "B", "C", "D"]
EDGES = [("A", "B", 1), ("B", "C", 1), ("C", "A", 1), ("C", "D", 10)]
ARCS = []


def test_required_none_covers_everything():
    # Comportement historique : tout est requis, l'éperon doit être parcouru.
    total_cost, passes = solve_sector(VERTICES, EDGES, ARCS, required=None)
    assert passes[("C", "D")] >= 1
    assert total_cost == 23  # triangle (3) + aller-retour éperon (2 x 10)


def test_required_subset_skips_non_required():
    # Postier Rural : seul le triangle est requis ; l'éperon n'est pas parcouru.
    required = {("A", "B"), ("B", "C"), ("C", "A")}
    total_cost, passes = solve_sector(VERTICES, EDGES, ARCS, required=required)
    assert passes[("C", "D")] == 0
    assert passes[("D", "C")] == 0
    assert total_cost == 3
