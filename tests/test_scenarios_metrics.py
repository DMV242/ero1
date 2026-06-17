from scenarios import route_metrics, network_length_km, deadhead_fraction


# lengths : longueur (m) de chaque arc dirigé. Arête A-B (200 m), arc B-C (300 m).
LENGTHS = {("A", "B"): 200.0, ("B", "A"): 200.0, ("B", "C"): 300.0}


def test_route_metrics_km_and_hours():
    passes = {("A", "B"): 2, ("B", "C"): 1}  # 2x200 + 1x300 = 700 m = 0.7 km
    km, hours = route_metrics(passes, LENGTHS)
    assert round(km, 3) == 0.7
    assert round(hours, 3) == 0.07  # 0.7 km / 10 km/h


def test_network_length_counts_each_street_once():
    required = {("A", "B"), ("B", "C")}  # 200 + 300 = 500 m = 0.5 km
    assert round(network_length_km(required, LENGTHS), 3) == 0.5


def test_deadhead_fraction():
    # 0.7 km parcourus, 0.5 km de réseau utile -> 0.2/0.7 à vide
    frac = deadhead_fraction(driven_km=0.7, network_km=0.5)
    assert round(frac, 4) == round(0.2 / 0.7, 4)
