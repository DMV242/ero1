"""Modèle de coût des opérations de déblaiement (énoncé ERO1).

Tarifs imposés : coût fixe 500 $/jour/véhicule ; 1,1 $/km ;
1,1 $/h les 8 premières heures puis 1,3 $/h ; vitesse 10 km/h.
Hypothèse de flotte : le travail est réparti idéalement entre N véhicules
(temps/véhicule = temps_total / N).
"""
import math

COST_FIXED_PER_VEHICLE = 500.0
COST_PER_KM = 1.1
COST_PER_HOUR_REGULAR = 1.1
COST_PER_HOUR_OVERTIME = 1.3
REGULAR_HOURS = 8.0
SPEED_KMH = 10.0


def daily_cost(total_km, total_hours, n_vehicles):
    """Coût journalier total pour parcourir total_km / total_hours avec N véhicules."""
    fixed = COST_FIXED_PER_VEHICLE * n_vehicles
    km = COST_PER_KM * total_km
    regular_capacity = REGULAR_HOURS * n_vehicles
    regular_hours = min(total_hours, regular_capacity)
    overtime_hours = max(total_hours - regular_capacity, 0.0)
    hourly = COST_PER_HOUR_REGULAR * regular_hours + COST_PER_HOUR_OVERTIME * overtime_hours
    return fixed + km + hourly


def cost_curve(total_km, total_hours, n_max):
    """Liste [(N, coût)] pour N = 1..n_max."""
    return [(n, daily_cost(total_km, total_hours, n)) for n in range(1, n_max + 1)]


def optimal_fleet(total_hours):
    """Plus petit N tel que chaque véhicule tienne en 8 h (T/N <= 8)."""
    return max(1, math.ceil(total_hours / REGULAR_HOURS))
