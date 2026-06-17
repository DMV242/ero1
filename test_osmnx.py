"""
Test avec OSMnx: télécharge un petit secteur de Montréal et fait tourner le solveur.
"""

import sys
from snowplow_routing import (
    load_sector_osmnx,
    osmnx_to_graph,
    solve_sector,
    build_route,
)

# Petit secteur (Outremont) pour que le test reste rapide.
# Montréal entier est trop gros ; on teste sur les sous-secteurs de l'étude.
PLACE = "Outremont, Montréal, Québec, Canada"

print(f"[1/4] Téléchargement du réseau OSM : {PLACE}")
G = load_sector_osmnx(place=PLACE)
print(f"      {len(G.nodes())} noeuds, {len(G.edges())} arcs")

print("[2/4] Conversion en (vertices, edges, arcs) ...")
print("      (réduction à la plus grande composante fortement connexe)")
vertices, edges, arcs, lengths = osmnx_to_graph(G)
print(
    f"      {len(vertices)} sommets | {len(edges)} edges (2-sens) | {len(arcs)} arcs (1-sens)"
)

print("[3/4] Résolution ILP (OR-Tools CBC) ...")
result = solve_sector(vertices, edges, arcs)

if result is None:
    print("ERREUR: pas de solution trouvée.")
    sys.exit(1)

total_cost, passes = result
driven = {arc: n for arc, n in passes.items() if n > 0}
redriven = {arc: n for arc, n in driven.items() if n > 1}

print(f"      Coût total optimal : {total_cost:.2f}")
print(f"      Arcs couverts      : {len(driven)}")
print(f"      Arcs re-parcourus  : {len(redriven)} (rééquilibrage)")

print("[4/4] Construction de la route (Hierholzer) ...")
start = vertices[0]
route = build_route(passes, start=start)
print(f"      Longueur de la route : {len(route)} étapes")
print(f"      Départ = Arrivée : {route[0] == route[-1]}")
print("\nTest OK.")
