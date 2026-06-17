from cost_model import daily_cost, cost_curve, optimal_fleet


def test_daily_cost_no_overtime():
    # L=100 km, T=5 h, 1 véhicule : 500 + 1.1*100 + 1.1*5 = 615.5
    assert daily_cost(100.0, 5.0, 1) == 615.5


def test_daily_cost_with_overtime():
    # L=100, T=10, N=1 : 500 + 110 + 1.1*8 + 1.3*2 = 621.4
    assert round(daily_cost(100.0, 10.0, 1), 2) == 621.4


def test_daily_cost_two_vehicles_splits_hours():
    # L=100, T=10, N=2 : 8h normales/véhicule dispo -> pas d'heures sup.
    # 1000 (fixe) + 110 (km) + 1.1*10 (heures) = 1121.0
    assert round(daily_cost(100.0, 10.0, 2), 2) == 1121.0


def test_optimal_fleet():
    assert optimal_fleet(10.0) == 2   # ceil(10/8)
    assert optimal_fleet(8.0) == 1
    assert optimal_fleet(0.0) == 1


def test_cost_curve_length():
    curve = cost_curve(100.0, 10.0, 5)
    assert len(curve) == 5
    assert curve[0][0] == 1 and curve[-1][0] == 5
