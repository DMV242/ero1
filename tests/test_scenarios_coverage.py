from scenarios import coverage_over_time

LENGTHS = {("A", "B"): 36000.0, ("B", "C"): 36000.0}  # 36 km chacun = 3,6 h à 10 km/h


def test_coverage_over_time_fraction_of_priority_cleared():
    # Route ordonnée A->B->C : A-B dégagé à t=3.6h, B-C à t=7.2h.
    route = ["A", "B", "C"]
    priority = {("A", "B"), ("B", "C")}
    cov = coverage_over_time(route, LENGTHS, priority, times_h=[1.0, 4.0, 8.0])
    assert cov[1.0] == 0.0   # rien de fini à 1 h
    assert cov[4.0] == 0.5   # A-B fini (1/2 du réseau prioritaire)
    assert cov[8.0] == 1.0   # tout fini
