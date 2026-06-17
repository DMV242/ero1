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


def _street_length(u, v, lengths):
    """Longueur d'une rue, en tolérant l'ordre des nœuds (arête)."""
    if (u, v) in lengths:
        return lengths[(u, v)]
    return lengths.get((v, u), 0.0)


def coverage_over_time(route, lengths, priority, times_h):
    """Fraction du réseau prioritaire dégagée à chaque instant de `times_h`.

    On parcourt `route` (liste ordonnée de nœuds) ; la première fois qu'une rue
    prioritaire est empruntée, elle est considérée dégagée à l'instant courant.
    """
    priority_pairs = {frozenset(p) for p in priority}
    total_priority_m = sum(_street_length(u, v, lengths) for (u, v) in priority)

    cleared = []   # liste de (instant_h, longueur_m) des rues prioritaires dégagées
    seen = set()
    t = 0.0
    for u, v in zip(route, route[1:]):
        seg_m = _street_length(u, v, lengths)
        t += (seg_m / 1000.0) / SPEED_KMH
        key = frozenset((u, v))
        if key in priority_pairs and key not in seen:
            seen.add(key)
            cleared.append((t, seg_m))

    result = {}
    for tq in times_h:
        done_m = sum(m for (tc, m) in cleared if tc <= tq)
        result[tq] = (done_m / total_priority_m) if total_priority_m > 0 else 0.0
    return result
