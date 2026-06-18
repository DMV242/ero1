"""Orchestration des scénarios de priorisation : routage en 2 phases (Postier
Rural), calcul des indicateurs, exports (JSON, cartes PNG) et comparatif CSV.
"""

import json
import csv
import os
import time

from snowplow_routing import (
    load_sector_osmnx,
    osmnx_to_graph,
    solve_sector,
    build_route_all,
    largest_strongly_connected_subgraph,
)
from cost_model import daily_cost, cost_curve, optimal_fleet
import priorities

SPEED_KMH = 10.0
# Limite de temps par résolution ILP (s). CP-SAT trouve l'optimum vite sur ces
# problèmes ; la limite borne surtout la preuve d'optimalité sur les gros secteurs
# (RDP-PAT) et renvoie la meilleure solution trouvée — quasi gratuit en qualité.
SOLVE_TIME_LIMIT_S = 20.0


def _log(msg):
    """Message de progression, affiché immédiatement (sans buffer)."""
    print(msg, flush=True)


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
        result[tq] = float(done_m / total_priority_m) if total_priority_m > 0 else 0.0
    return result


SCENARIOS = {
    "arteriel": lambda G, place: priorities.arterial(G),
    "services": lambda G, place: priorities.essential_services(G, place),
    "transport": lambda G, place: priorities.transit(G, place),
}


def _solve_phase(vertices, edges, arcs, lengths, required, verbose=False, label=""):
    """Résout une phase (Postier Rural sur `required`) et renvoie (route, km, h, passes).

    build_route_all couvre TOUS les arcs parcourus, y compris quand la solution
    optimale forme plusieurs circuits disjoints (réseau prioritaire dispersé)."""
    if verbose:
        n_req = "toutes" if required is None else len(required)
        _log(f"      • {label} : résolution ILP ({n_req} rues à couvrir)…")
    result = solve_sector(vertices, edges, arcs, required=required,
                          time_limit_s=SOLVE_TIME_LIMIT_S)
    if result is None:
        raise RuntimeError("Phase infaisable (graphe non fortement connexe ?).")
    _, passes = result
    route = build_route_all(passes)
    km, hours = route_metrics(passes, lengths)
    if verbose:
        _log(f"        → {km:.1f} km, {hours:.2f} h")
    return route, km, hours, passes


def run_scenario(place, scenario, n_vehicles=None, n_max=10, verbose=False):
    """Route un secteur en 2 phases pour un scénario et renvoie les indicateurs."""
    if verbose:
        _log("    chargement du réseau OSM…")
    G = load_sector_osmnx(place=place)
    vertices, edges, arcs, lengths = osmnx_to_graph(G)
    all_streets = {(i, j) for i, j, _ in edges} | {(i, j) for i, j, _ in arcs}
    if verbose:
        _log(f"    {len(vertices)} sommets ; classification « {scenario} »…")
    priority = SCENARIOS[scenario](G, place) & all_streets
    rest = all_streets - priority
    if verbose:
        _log(f"    {len(priority)} rues prioritaires sur {len(all_streets)}")

    route1, km1, h1, passes1 = _solve_phase(
        vertices, edges, arcs, lengths, priority, verbose, "phase 1 — réseau prioritaire")
    route2, km2, h2, passes2 = _solve_phase(
        vertices, edges, arcs, lengths, rest, verbose, "phase 2 — reste du réseau")

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


def run_baseline(place, n_vehicles=None, n_max=10, verbose=False):
    """Postier Chinois uniforme (toutes rues, une phase) — ligne de base."""
    if verbose:
        _log("    chargement du réseau OSM…")
    G = load_sector_osmnx(place=place)
    vertices, edges, arcs, lengths = osmnx_to_graph(G)
    route, km, h, _ = _solve_phase(
        vertices, edges, arcs, lengths, None, verbose, "tournée uniforme")
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


SECTORS = {
    "outremont": "Outremont, Montréal, Québec, Canada",
    "verdun": "Verdun, Montréal, Québec, Canada",
    "anjou": "Anjou, Montréal, Québec, Canada",
    "riviere-des-prairies-pointe-aux-trembles":
        "Rivière-des-Prairies–Pointe-aux-Trembles, Montréal, Québec, Canada",
}
SECTORS_DIR = "sectors"


def save_map(place, priority, out_png):
    """Carte : réseau gris + réseau prioritaire surligné (rouge)."""
    import osmnx as ox
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    G = largest_strongly_connected_subgraph(load_sector_osmnx(place=place))

    def is_prio(u, v):
        return (u, v) in priority or (v, u) in priority

    colors = ["#d62728" if is_prio(u, v) else "#cccccc" for u, v, _ in G.edges(keys=True)]
    widths = [2.0 if is_prio(u, v) else 0.5 for u, v, _ in G.edges(keys=True)]
    fig, ax = ox.plot_graph(G, edge_color=colors, edge_linewidth=widths,
                            node_size=0, show=False, close=False)
    fig.savefig(out_png, dpi=150, bbox_inches="tight")
    plt.close(fig)


def export_sector(slug, place, n_vehicles=None):
    """Calcule les 3 scénarios + baseline d'un secteur et écrit ses sorties."""
    _log(f"\n── Secteur : {slug}  ({place})")
    out_dir = os.path.join(SECTORS_DIR, slug)
    os.makedirs(out_dir, exist_ok=True)

    t = time.time()
    _log("  [baseline] Postier Chinois uniforme")
    results = {"baseline": run_baseline(place, n_vehicles=n_vehicles, verbose=True)}
    _log(f"  [baseline] ✓ coût {results['baseline']['cout_total']} $  ({time.time() - t:.0f}s)")

    for scen in SCENARIOS:
        t = time.time()
        _log(f"  [{scen}] calcul des 2 phases…")
        res = run_scenario(place, scen, n_vehicles=n_vehicles, verbose=True)
        results[scen] = res
        priority = {tuple(p) for p in res["priority_streets"]}
        _log(f"  [{scen}] génération de la carte…")
        save_map(place, priority, os.path.join(out_dir, f"carte_{scen}.png"))
        _log(f"  [{scen}] ✓ coût {res['cout_total']} $ | "
             f"T1 {res['T1_reseau_prioritaire_h']} h  ({time.time() - t:.0f}s)")

    with open(os.path.join(out_dir, "resultats.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    _log(f"  → écrit {out_dir}/resultats.json (+ 3 cartes)")
    return results


def run_all(n_vehicles=None):
    """Calcule tous les secteurs et écrit le comparatif CSV."""
    sectors = list(SECTORS.items())
    _log(f"=== Génération de {len(sectors)} secteurs "
         "(quelques minutes, RDP-PAT est le plus long) ===")
    t0 = time.time()
    rows = []
    for i, (slug, place) in enumerate(sectors, 1):
        _log(f"\n========== [{i}/{len(sectors)}] {slug} ==========")
        res = export_sector(slug, place, n_vehicles=n_vehicles)
        for scen, r in res.items():
            rows.append({
                "secteur": slug, "scenario": scen,
                "cout_total": r["cout_total"], "km_total": r["km_total"],
                "heures_total": r["heures_total"], "part_a_vide": r["part_a_vide"],
                "nb_vehicules_8h": r["nb_vehicules_8h"],
                "T1": r.get("T1_reseau_prioritaire_h", ""),
            })
    with open("comparaison_scenarios.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    _log(f"\n✓ Terminé en {time.time() - t0:.0f}s — "
         f"sectors/ + comparaison_scenarios.csv ({len(rows)} lignes)")
    return rows


if __name__ == "__main__":
    import sys

    if "--all" in sys.argv:
        run_all()
    else:
        print("Usage : python scenarios.py --all")
