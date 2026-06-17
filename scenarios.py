"""Orchestration des scénarios de priorisation : routage en 2 phases,
calcul des indicateurs, exports (JSON, GeoJSON, cartes) et comparatif.

Cette première partie ne contient que des helpers PURS (testables hors-ligne) ;
l'orchestration OSM est ajoutée ensuite.
"""

from snowplow_routing import load_sector_osmnx, osmnx_to_graph, solve_sector, build_route
from cost_model import daily_cost, cost_curve, optimal_fleet
import priorities

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


SCENARIOS = {
    "arteriel": lambda G, place: priorities.arterial(G),
    "services": lambda G, place: priorities.essential_services(G, place),
    "transport": lambda G, place: priorities.transit(G, place),
}


def _solve_phase(vertices, edges, arcs, lengths, required, fallback_start):
    """Résout une phase (Postier Rural sur `required`) et renvoie (route, km, h, passes).

    Le point de départ de Hierholzer doit être un nœud RÉELLEMENT parcouru, sinon
    la route serait dégénérée (la phase ne couvre qu'un sous-ensemble du graphe).
    """
    result = solve_sector(vertices, edges, arcs, required=required)
    if result is None:
        raise RuntimeError("Phase infaisable (graphe non fortement connexe ?).")
    _, passes = result
    start = next((i for (i, j), n in passes.items() if n > 0), fallback_start)
    route = build_route(passes, start=start)
    km, hours = route_metrics(passes, lengths)
    return route, km, hours, passes


def run_scenario(place, scenario, n_vehicles=None, n_max=10):
    """Route un secteur en 2 phases pour un scénario et renvoie les indicateurs."""
    G = load_sector_osmnx(place=place)
    vertices, edges, arcs, lengths = osmnx_to_graph(G)
    fallback = vertices[0]

    all_streets = {(i, j) for i, j, _ in edges} | {(i, j) for i, j, _ in arcs}
    priority = SCENARIOS[scenario](G, place) & all_streets
    rest = all_streets - priority

    route1, km1, h1, passes1 = _solve_phase(vertices, edges, arcs, lengths, priority, fallback)
    route2, km2, h2, passes2 = _solve_phase(vertices, edges, arcs, lengths, rest, fallback)

    total_km, total_h = km1 + km2, h1 + h2
    net_km = network_length_km(all_streets, lengths)
    prio_km = network_length_km(priority, lengths)
    fleet = n_vehicles or optimal_fleet(total_h)

    return {
        "place": place,
        "scenario": scenario,
        "priority_streets": sorted(map(list, priority)),
        "cout_total": round(daily_cost(total_km, total_h, fleet), 2),
        "courbe_cout": cost_curve(total_km, total_h, n_max),
        "km_total": round(total_km, 3),
        "heures_total": round(total_h, 3),
        "part_a_vide": round(deadhead_fraction(total_km, net_km), 4),
        "nb_vehicules_8h": optimal_fleet(total_h),
        "T1_reseau_prioritaire_h": round(h1, 3),
        "km_reseau_prioritaire": round(prio_km, 3),
        "part_reseau_prioritaire": round(prio_km / net_km, 4) if net_km else 0.0,
        "couverture_prioritaire": coverage_over_time(route1, lengths, priority, [1.0, 2.0, 4.0]),
        "route_phase1": route1,
        "route_phase2": route2,
    }


def run_baseline(place, n_vehicles=None, n_max=10):
    """Postier Chinois uniforme (toutes rues, une phase) — ligne de base."""
    G = load_sector_osmnx(place=place)
    vertices, edges, arcs, lengths = osmnx_to_graph(G)
    fallback = vertices[0]
    route, km, h, _ = _solve_phase(vertices, edges, arcs, lengths, None, fallback)
    net_km = network_length_km({(i, j) for i, j, _ in edges} | {(i, j) for i, j, _ in arcs}, lengths)
    fleet = n_vehicles or optimal_fleet(h)
    return {
        "place": place, "scenario": "baseline",
        "cout_total": round(daily_cost(km, h, fleet), 2),
        "courbe_cout": cost_curve(km, h, n_max),
        "km_total": round(km, 3), "heures_total": round(h, 3),
        "part_a_vide": round(deadhead_fraction(km, net_km), 4),
        "nb_vehicules_8h": optimal_fleet(h),
        "route": route,
    }
