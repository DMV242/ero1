"""Orchestration des scénarios de priorisation : routage en 2 phases,
calcul des indicateurs, exports (JSON, GeoJSON, cartes) et comparatif.

Cette première partie ne contient que des helpers PURS (testables hors-ligne) ;
l'orchestration OSM est ajoutée ensuite.
"""

SPEED_KMH = 10.0


def route_metrics(passes, lengths):
    """(km parcourus, heures) pour un multiensemble d'arcs `passes`."""
    total_m = sum(lengths[(i, j)] * n for (i, j), n in passes.items() if n > 0)
    total_km = total_m / 1000.0
    return total_km, total_km / SPEED_KMH


def network_length_km(required, lengths):
    """Longueur (km) du réseau `required`, chaque rue comptée une fois."""
    total_m = sum(lengths[(u, v)] for (u, v) in required)
    return total_m / 1000.0


def deadhead_fraction(driven_km, network_km):
    """Part des km parcourus « à vide » (au-delà de la couverture utile)."""
    if driven_km <= 0:
        return 0.0
    return max(driven_km - network_km, 0.0) / driven_km
