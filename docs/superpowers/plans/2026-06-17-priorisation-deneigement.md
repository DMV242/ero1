# Priorisation du déneigement — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Étendre le moteur de routage (Postier Chinois uniforme) en un système de déneigement priorisé : 3 scénarios de priorisation routés en 2 phases, modèle de coût en fonction du nombre de véhicules, indicateurs comparatifs sur les 4 secteurs, plus une interface Streamlit.

**Architecture:** Le solveur ILP existant est généralisé en Postier Rural (couvrir un sous-ensemble de rues, traverser les autres librement). Chaque scénario définit un « réseau prioritaire » (phase 1) puis le reste (phase 2). Des modules purs (`cost_model`, `priorities`, helpers de `scenarios`) sont testables hors-ligne ; l'orchestration OSM, les exports et l'UI sont vérifiés par exécution sur le cache.

**Tech Stack:** Python, OR-Tools (CBC), NetworkX, OSMnx, geopandas/shapely, matplotlib, Streamlit/folium, pytest.

---

## File Structure

| Fichier | Rôle |
|---|---|
| `snowplow_routing.py` | *(modifié)* `solve_sector(..., required=None)` (Postier Rural) ; `osmnx_to_graph` renvoie aussi `lengths` ; `build_route` inchangé |
| `cost_model.py` | *(nouveau)* `daily_cost`, `cost_curve`, `optimal_fleet` (fonctions pures) |
| `priorities.py` | *(nouveau)* `arterial`, `essential_services`, `transit` + helpers purs `streets_near_points`, `streets_intersecting_lines` |
| `scenarios.py` | *(nouveau)* helpers purs (`route_metrics`, `network_length_km`, `deadhead_fraction`, `coverage_over_time`) + orchestration `run_scenario`, `run_baseline`, exports, `--all` |
| `demo.py` | *(nouveau)* démonstration CLI (1 secteur, scénario artériel) |
| `app.py` | *(nouveau)* interface Streamlit (lit les sorties précalculées) |
| `tests/` | *(nouveau)* tests pytest des modules purs |
| `AUTHORS`, `README.md`, `THEORY.md`, `requirements.txt` | *(modifiés/nouveaux)* livrables et docs |

Convention : `required` et les ensembles prioritaires sont des `set` de paires de nœuds `(u, v)`. Pour une arête, « requise » = `(u,v)` **ou** `(v,u)` présent. `lengths[(u,v)]` est la longueur en mètres de chaque arc dirigé.

---

## Task 1: Généraliser `solve_sector` en Postier Rural

**Files:**
- Modify: `snowplow_routing.py:35-82` (fonction `solve_sector`)
- Modify: `requirements.txt` (ajouter `pytest`)
- Test: `tests/test_solver.py`

- [ ] **Step 1: Ajouter pytest aux dépendances**

Dans `requirements.txt`, ajouter une ligne :
```
pytest
```

- [ ] **Step 2: Écrire le test qui échoue**

Créer `tests/test_solver.py` :
```python
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
```

- [ ] **Step 3: Lancer le test, vérifier l'échec**

Run: `python -m pytest tests/test_solver.py -v`
Expected: FAIL — `solve_sector()` got an unexpected keyword argument `required`.

- [ ] **Step 4: Implémenter le paramètre `required`**

Remplacer la signature et les boucles de contraintes de couverture dans `snowplow_routing.py`. Nouvelle signature :
```python
def solve_sector(vertices, edges, arcs, required=None, backend="CBC"):
```
Juste après la construction de `cost` et `edge_pairs`, ajouter :
```python
    def is_required(i, j):
        if required is None:
            return True
        return (i, j) in required or (j, i) in required
```
Remplacer les deux boucles de couverture existantes par :
```python
    for i, j in edge_pairs:
        if is_required(i, j):
            solver.Add(x[(i, j)] + x[(j, i)] >= 1)

    for i, j, c in arcs:
        if is_required(i, j):
            solver.Add(x[(i, j)] >= 1)
```
Tout le reste (variables `x` pour tous les `(i,j)` de `cost`, conservation de flot, objectif, extraction `passes`) reste **inchangé** : c'est ce qui autorise les rues non requises comme connecteurs.

- [ ] **Step 5: Lancer le test, vérifier le succès**

Run: `python -m pytest tests/test_solver.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Vérifier la non-régression de l'exemple intégré**

Run: `python snowplow_routing.py`
Expected: affiche `Optimal total cost: 35` et une route `D -> ... -> D` (identique à avant).

- [ ] **Step 7: Commit**

```bash
git add requirements.txt tests/test_solver.py snowplow_routing.py
git commit -m "feat: generalize solve_sector to Rural Postman via required set"
```

---

## Task 2: `osmnx_to_graph` renvoie aussi les longueurs

**Files:**
- Modify: `snowplow_routing.py:141-173` (fonction `osmnx_to_graph`)
- Modify: `test_osmnx.py:22` (dépaquetage du retour)
- Test: `tests/test_osmnx_to_graph.py`

- [ ] **Step 1: Écrire le test qui échoue**

Créer `tests/test_osmnx_to_graph.py` :
```python
import networkx as nx
from snowplow_routing import osmnx_to_graph


def _toy_graph():
    # Petit MultiDiGraph fortement connexe : 1<->2, 2<->3 (deux sens), 1->3 (sens unique).
    G = nx.MultiDiGraph()
    G.add_edge(1, 2, length=100.0)
    G.add_edge(2, 1, length=100.0)
    G.add_edge(2, 3, length=200.0)
    G.add_edge(3, 2, length=200.0)
    G.add_edge(1, 3, length=50.0)
    return G


def test_returns_lengths_and_classifies_streets():
    vertices, edges, arcs, lengths = osmnx_to_graph(_toy_graph())
    assert set(vertices) == {1, 2, 3}
    # 1-2 et 2-3 sont à double sens -> arêtes ; 1->3 est à sens unique -> arc.
    edge_pairs = {frozenset((i, j)) for i, j, _ in edges}
    assert edge_pairs == {frozenset((1, 2)), frozenset((2, 3))}
    assert [(i, j) for i, j, _ in arcs] == [(1, 3)]
    assert lengths[(1, 3)] == 50.0
    assert lengths[(1, 2)] == 100.0
```

- [ ] **Step 2: Lancer le test, vérifier l'échec**

Run: `python -m pytest tests/test_osmnx_to_graph.py -v`
Expected: FAIL — `not enough values to unpack (expected 4, got 3)`.

- [ ] **Step 3: Implémenter le retour des longueurs**

Dans `osmnx_to_graph`, après la réduction CFC et avant la boucle de regroupement, construire un dict `lengths` en parallèle de `arc_cost` :
```python
    arc_cost = {}
    lengths = {}
    for u, v, data in G.edges(data=True):
        length_m = data.get("length", 0.0)
        arc_cost[(u, v)] = segment_cost(length_m)
        lengths[(u, v)] = length_m
```
Et changer la ligne de retour finale :
```python
    return vertices, edges, arcs, lengths
```

- [ ] **Step 4: Mettre à jour le dépaquetage dans `test_osmnx.py`**

Remplacer la ligne `vertices, edges, arcs = osmnx_to_graph(G)` par :
```python
vertices, edges, arcs, lengths = osmnx_to_graph(G)
```

- [ ] **Step 5: Lancer le test, vérifier le succès**

Run: `python -m pytest tests/test_osmnx_to_graph.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tests/test_osmnx_to_graph.py snowplow_routing.py test_osmnx.py
git commit -m "feat: osmnx_to_graph returns per-street lengths"
```

---

## Task 3: Modèle de coût `f(N)` (`cost_model.py`)

**Files:**
- Create: `cost_model.py`
- Test: `tests/test_cost_model.py`

- [ ] **Step 1: Écrire le test qui échoue**

Créer `tests/test_cost_model.py` :
```python
import math
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
```

- [ ] **Step 2: Lancer le test, vérifier l'échec**

Run: `python -m pytest tests/test_cost_model.py -v`
Expected: FAIL — `No module named 'cost_model'`.

- [ ] **Step 3: Implémenter `cost_model.py`**

```python
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
```

- [ ] **Step 4: Lancer le test, vérifier le succès**

Run: `python -m pytest tests/test_cost_model.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add cost_model.py tests/test_cost_model.py
git commit -m "feat: add fleet cost model (cost as a function of N vehicles)"
```

---

## Task 4: Scénario artériel (`priorities.py`)

**Files:**
- Create: `priorities.py`
- Test: `tests/test_priorities_arterial.py`

- [ ] **Step 1: Écrire le test qui échoue**

Créer `tests/test_priorities_arterial.py` :
```python
import networkx as nx
from priorities import arterial


def test_arterial_selects_major_roads_only():
    G = nx.MultiDiGraph()
    G.add_edge(1, 2, highway="primary")
    G.add_edge(2, 3, highway="residential")
    G.add_edge(3, 4, highway=["secondary", "tertiary"])  # OSM peut donner une liste
    G.add_edge(4, 5, highway="service")
    prio = arterial(G)
    assert (1, 2) in prio
    assert (3, 4) in prio
    assert (2, 3) not in prio
    assert (4, 5) not in prio
```

- [ ] **Step 2: Lancer le test, vérifier l'échec**

Run: `python -m pytest tests/test_priorities_arterial.py -v`
Expected: FAIL — `No module named 'priorities'`.

- [ ] **Step 3: Implémenter `arterial` dans `priorities.py`**

```python
"""Classification des rues prioritaires (tier 1) selon trois scénarios.

Chaque fonction renvoie un set de paires de nœuds (u, v) constituant le réseau
prioritaire, à passer comme `required` à solve_sector pour la phase 1.
"""

ARTERIAL_HIGHWAYS = {
    "motorway", "trunk", "primary", "secondary", "tertiary",
    "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link",
}


def _highway_values(data):
    hw = data.get("highway")
    if hw is None:
        return []
    return hw if isinstance(hw, list) else [hw]


def arterial(G):
    """Tier 1 = grandes voies (tag OSM `highway` structurant)."""
    prio = set()
    for u, v, data in G.edges(data=True):
        if any(h in ARTERIAL_HIGHWAYS for h in _highway_values(data)):
            prio.add((u, v))
    return prio
```

- [ ] **Step 4: Lancer le test, vérifier le succès**

Run: `python -m pytest tests/test_priorities_arterial.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add priorities.py tests/test_priorities_arterial.py
git commit -m "feat: add arterial-network prioritization scenario"
```

---

## Task 5: Scénario services essentiels — helper de proximité

**Files:**
- Modify: `priorities.py` (ajouter `streets_near_points` + `essential_services`)
- Test: `tests/test_priorities_services.py`

- [ ] **Step 1: Écrire le test qui échoue (sur le helper pur)**

Créer `tests/test_priorities_services.py` :
```python
import networkx as nx
from priorities import streets_near_points


def _proj_graph():
    # Coordonnées en mètres (graphe déjà projeté). Arête 1-2 près de l'origine,
    # arête 3-4 à 1000 m.
    G = nx.MultiDiGraph()
    G.add_node(1, x=0.0, y=0.0)
    G.add_node(2, x=100.0, y=0.0)
    G.add_node(3, x=1000.0, y=0.0)
    G.add_node(4, x=1100.0, y=0.0)
    G.add_edge(1, 2)
    G.add_edge(3, 4)
    return G


def test_streets_near_points_marks_only_close_streets():
    points = [(10.0, 5.0)]  # POI à 5 m de l'arête 1-2
    prio = streets_near_points(_proj_graph(), points, dist=150.0)
    assert (1, 2) in prio
    assert (3, 4) not in prio
```

- [ ] **Step 2: Lancer le test, vérifier l'échec**

Run: `python -m pytest tests/test_priorities_services.py -v`
Expected: FAIL — `cannot import name 'streets_near_points'`.

- [ ] **Step 3: Implémenter `streets_near_points` et `essential_services`**

Ajouter à `priorities.py` :
```python
def _segment_point_distance(ax, ay, bx, by, px, py):
    """Distance euclidienne du point (px,py) au segment [(ax,ay),(bx,by)]."""
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    cx, cy = ax + t * dx, ay + t * dy
    return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5


def streets_near_points(G_proj, points_xy, dist):
    """(u,v) dont le segment passe à <= dist mètres d'au moins un point.

    G_proj : graphe PROJETÉ (attributs de nœud x, y en mètres).
    points_xy : liste de (x, y) dans le même repère métrique.
    """
    prio = set()
    for u, v in G_proj.edges():
        ax, ay = G_proj.nodes[u]["x"], G_proj.nodes[u]["y"]
        bx, by = G_proj.nodes[v]["x"], G_proj.nodes[v]["y"]
        for px, py in points_xy:
            if _segment_point_distance(ax, ay, bx, by, px, py) <= dist:
                prio.add((u, v))
                break
    return prio


def essential_services(G, place, dist=150.0,
                       amenities=("hospital", "school", "fire_station", "clinic")):
    """Tier 1 = rues à <= dist m d'un service essentiel (POI OSM)."""
    import osmnx as ox

    pois = ox.features_from_place(place, tags={"amenity": list(amenities)})
    G_proj = ox.project_graph(G)
    pois_proj = ox.projection.project_gdf(pois, to_crs=G_proj.graph["crs"])
    points_xy = [(geom.centroid.x, geom.centroid.y) for geom in pois_proj.geometry]
    return streets_near_points(G_proj, points_xy, dist)
```

- [ ] **Step 4: Lancer le test, vérifier le succès**

Run: `python -m pytest tests/test_priorities_services.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add priorities.py tests/test_priorities_services.py
git commit -m "feat: add essential-services prioritization scenario"
```

---

## Task 6: Scénario transport collectif — helper d'intersection

**Files:**
- Modify: `priorities.py` (ajouter `streets_intersecting_lines` + `transit`)
- Modify: `requirements.txt` (ajouter `shapely`)
- Test: `tests/test_priorities_transit.py`

- [ ] **Step 1: Ajouter shapely aux dépendances**

Dans `requirements.txt`, ajouter :
```
shapely
```

- [ ] **Step 2: Écrire le test qui échoue (sur le helper pur)**

Créer `tests/test_priorities_transit.py` :
```python
import networkx as nx
from shapely.geometry import LineString
from priorities import streets_intersecting_lines


def _proj_graph():
    G = nx.MultiDiGraph()
    G.add_node(1, x=0.0, y=0.0)
    G.add_node(2, x=100.0, y=0.0)
    G.add_node(3, x=0.0, y=500.0)
    G.add_node(4, x=100.0, y=500.0)
    G.add_edge(1, 2)  # ligne de bus passe ici (y=0)
    G.add_edge(3, 4)  # loin (y=500)
    return G


def test_streets_intersecting_lines():
    bus_line = LineString([(-50.0, 0.0), (150.0, 0.0)])  # longe l'arête 1-2
    prio = streets_intersecting_lines(_proj_graph(), [bus_line], buffer_m=20.0)
    assert (1, 2) in prio
    assert (3, 4) not in prio
```

- [ ] **Step 3: Lancer le test, vérifier l'échec**

Run: `python -m pytest tests/test_priorities_transit.py -v`
Expected: FAIL — `cannot import name 'streets_intersecting_lines'`.

- [ ] **Step 4: Implémenter `streets_intersecting_lines` et `transit`**

Ajouter à `priorities.py` :
```python
def streets_intersecting_lines(G_proj, lines, buffer_m):
    """(u,v) dont le segment passe à <= buffer_m d'une des lignes (LineString projetées)."""
    from shapely.geometry import LineString

    buffered = [ln.buffer(buffer_m) for ln in lines]
    prio = set()
    for u, v, data in G_proj.edges(data=True):
        geom = data.get("geometry")
        if geom is None:
            ax, ay = G_proj.nodes[u]["x"], G_proj.nodes[u]["y"]
            bx, by = G_proj.nodes[v]["x"], G_proj.nodes[v]["y"]
            geom = LineString([(ax, ay), (bx, by)])
        if any(geom.intersects(b) for b in buffered):
            prio.add((u, v))
    return prio


def transit(G, place, buffer_m=20.0):
    """Tier 1 = rues recouvertes par une ligne de bus (relations route=bus OSM)."""
    import osmnx as ox

    routes = ox.features_from_place(place, tags={"route": "bus"})
    G_proj = ox.project_graph(G)
    routes_proj = ox.projection.project_gdf(routes, to_crs=G_proj.graph["crs"])
    flat = []
    for geom in routes_proj.geometry:
        if geom is None:
            continue
        if geom.geom_type == "MultiLineString":
            flat.extend(geom.geoms)
        elif geom.geom_type == "LineString":
            flat.append(geom)
    return streets_intersecting_lines(G_proj, flat, buffer_m)
```

- [ ] **Step 5: Lancer le test, vérifier le succès**

Run: `python -m pytest tests/test_priorities_transit.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt priorities.py tests/test_priorities_transit.py
git commit -m "feat: add public-transit prioritization scenario"
```

---

## Task 7: Helpers d'indicateurs (`scenarios.py`)

**Files:**
- Create: `scenarios.py` (helpers purs uniquement à cette étape)
- Test: `tests/test_scenarios_metrics.py`

- [ ] **Step 1: Écrire le test qui échoue**

Créer `tests/test_scenarios_metrics.py` :
```python
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
```

- [ ] **Step 2: Lancer le test, vérifier l'échec**

Run: `python -m pytest tests/test_scenarios_metrics.py -v`
Expected: FAIL — `No module named 'scenarios'`.

- [ ] **Step 3: Implémenter les helpers purs dans `scenarios.py`**

```python
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
```

- [ ] **Step 4: Lancer le test, vérifier le succès**

Run: `python -m pytest tests/test_scenarios_metrics.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add scenarios.py tests/test_scenarios_metrics.py
git commit -m "feat: add tour metric helpers (km, hours, deadhead)"
```

---

## Task 8: Couverture du réseau prioritaire dans le temps

**Files:**
- Modify: `scenarios.py` (ajouter `coverage_over_time`)
- Test: `tests/test_scenarios_coverage.py`

- [ ] **Step 1: Écrire le test qui échoue**

Créer `tests/test_scenarios_coverage.py` :
```python
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
```

- [ ] **Step 2: Lancer le test, vérifier l'échec**

Run: `python -m pytest tests/test_scenarios_coverage.py -v`
Expected: FAIL — `cannot import name 'coverage_over_time'`.

- [ ] **Step 3: Implémenter `coverage_over_time`**

Ajouter à `scenarios.py` :
```python
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
```

> Note d'implémentation : on mémorise `(instant, longueur)` au premier passage sur chaque
> rue prioritaire, puis `done_m` somme les longueurs dégagées avant `tq`.

- [ ] **Step 4: Lancer le test, vérifier le succès**

Run: `python -m pytest tests/test_scenarios_coverage.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scenarios.py tests/test_scenarios_coverage.py
git commit -m "feat: add priority-network coverage-over-time indicator"
```

---

## Task 9: Orchestration `run_scenario` / `run_baseline` (2 phases)

**Files:**
- Modify: `scenarios.py` (ajouter `run_scenario`, `run_baseline`, `SCENARIOS`)

Cette tâche assemble les briques. Vérification par **exécution sur le cache OSM** (Outremont déjà en cache), pas de test unitaire (dépend du réseau/solveur).

- [ ] **Step 1: Implémenter l'orchestration dans `scenarios.py`**

Ajouter en tête de fichier les imports nécessaires :
```python
from snowplow_routing import load_sector_osmnx, osmnx_to_graph, solve_sector, build_route
from cost_model import daily_cost, cost_curve, optimal_fleet
import priorities
```
Puis le registre des scénarios et l'orchestration :
```python
SCENARIOS = {
    "arteriel": lambda G, place: priorities.arterial(G),
    "services": lambda G, place: priorities.essential_services(G, place),
    "transport": lambda G, place: priorities.transit(G, place),
}


def _solve_phase(vertices, edges, arcs, lengths, required, start):
    """Résout une phase (Postier Rural sur `required`) et renvoie (route, km, h, passes)."""
    result = solve_sector(vertices, edges, arcs, required=required)
    if result is None:
        raise RuntimeError("Phase infaisable (graphe non fortement connexe ?).")
    _, passes = result
    route = build_route(passes, start=start)
    km, hours = route_metrics(passes, lengths)
    return route, km, hours, passes


def run_scenario(place, scenario, n_vehicles=None, n_max=10):
    """Route un secteur en 2 phases pour un scénario et renvoie les indicateurs."""
    G = load_sector_osmnx(place=place)
    vertices, edges, arcs, lengths = osmnx_to_graph(G)
    start = vertices[0]

    all_streets = {(i, j) for i, j, _ in edges} | {(i, j) for i, j, _ in arcs}
    priority = SCENARIOS[scenario](G, place) & all_streets
    rest = all_streets - priority

    route1, km1, h1, passes1 = _solve_phase(vertices, edges, arcs, lengths, priority, start)
    route2, km2, h2, passes2 = _solve_phase(vertices, edges, arcs, lengths, rest, start)

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
    start = vertices[0]
    route, km, h, _ = _solve_phase(vertices, edges, arcs, lengths, None, start)
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
```

- [ ] **Step 2: Vérifier l'orchestration sur le cache (Outremont, artériel)**

Run:
```bash
python -c "from scenarios import run_scenario; r = run_scenario('Outremont, Montréal, Québec, Canada', 'arteriel'); print('cout', r['cout_total'], '| T1', r['T1_reseau_prioritaire_h'], '| couverture', r['couverture_prioritaire'])"
```
Expected: affiche un coût > 0, `T1 <= heures_total`, et un dict de couverture avec des fractions entre 0 et 1. Pas d'exception.

- [ ] **Step 3: Commit**

```bash
git add scenarios.py
git commit -m "feat: two-phase scenario orchestration with indicators and baseline"
```

---

## Task 10: Exports (JSON, GeoJSON, cartes PNG) et `--all`

**Files:**
- Modify: `scenarios.py` (ajouter `export_sector`, `export_geojson`, `save_map`, `run_all`, bloc `__main__`)
- Modify: `requirements.txt` (ajouter `matplotlib`, `geopandas`)

Vérification par exécution (génère les fichiers d'un secteur).

- [ ] **Step 1: Ajouter les dépendances**

Dans `requirements.txt`, ajouter :
```
matplotlib
geopandas
```

- [ ] **Step 2: Implémenter exports + run_all + CLI**

Ajouter à `scenarios.py` :
```python
import json
import csv
import os

SECTORS = {
    "outremont": "Outremont, Montréal, Québec, Canada",
    "verdun": "Verdun, Montréal, Québec, Canada",
    "anjou": "Anjou, Montréal, Québec, Canada",
    "riviere-des-prairies-pointe-aux-trembles":
        "Rivière-des-Prairies–Pointe-aux-Trembles, Montréal, Québec, Canada",
}
SECTORS_DIR = "sectors"


def save_map(place, priority, out_png):
    """Carte : réseau gris + réseau prioritaire surligné."""
    import osmnx as ox
    import matplotlib
    matplotlib.use("Agg")

    G = load_sector_osmnx(place=place)
    G = ox.utils_graph.get_largest_component(G, strongly=True)
    colors = ["#d62728" if (u, v) in priority or (v, u) in priority else "#cccccc"
              for u, v, _ in G.edges(keys=True)]
    widths = [2.0 if (u, v) in priority or (v, u) in priority else 0.5
              for u, v, _ in G.edges(keys=True)]
    fig, _ = ox.plot_graph(G, edge_color=colors, edge_linewidth=widths,
                           node_size=0, show=False, close=False)
    fig.savefig(out_png, dpi=150, bbox_inches="tight")
    import matplotlib.pyplot as plt
    plt.close(fig)


def export_sector(slug, place, n_vehicles=None):
    """Calcule les 3 scénarios + baseline d'un secteur et écrit ses sorties."""
    out_dir = os.path.join(SECTORS_DIR, slug)
    os.makedirs(out_dir, exist_ok=True)
    results = {"baseline": run_baseline(place, n_vehicles=n_vehicles)}
    for scen in SCENARIOS:
        res = run_scenario(place, scen, n_vehicles=n_vehicles)
        results[scen] = res
        priority = {tuple(p) for p in res["priority_streets"]}
        save_map(place, priority, os.path.join(out_dir, f"carte_{scen}.png"))
    with open(os.path.join(out_dir, "resultats.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    return results


def run_all(n_vehicles=None):
    """Calcule tous les secteurs et écrit le comparatif CSV."""
    rows = []
    for slug, place in SECTORS.items():
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
    return rows


if __name__ == "__main__":
    import sys
    if "--all" in sys.argv:
        run_all()
        print("Écrit : sectors/ et comparaison_scenarios.csv")
    else:
        print("Usage : python scenarios.py --all")
```

- [ ] **Step 3: Vérifier l'export d'un secteur sur le cache**

Run:
```bash
python -c "from scenarios import export_sector, SECTORS; export_sector('outremont', SECTORS['outremont']); import os; print(sorted(os.listdir('sectors/outremont')))"
```
Expected: liste contenant `resultats.json`, `carte_arteriel.png`, `carte_services.png`, `carte_transport.png`.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt scenarios.py
git commit -m "feat: export per-sector results, maps and comparison CSV"
```

---

## Task 11: Script de démonstration (`demo.py`)

**Files:**
- Create: `demo.py`

- [ ] **Step 1: Implémenter `demo.py`**

```python
"""Démonstration : route Outremont selon le scénario 'réseau artériel' et
affiche les indicateurs clés. Livrable « script de démonstration » (sujet ERO1).

Usage : python demo.py
"""
from scenarios import run_scenario, SECTORS

PLACE = SECTORS["outremont"]


def main():
    print(f"Secteur : {PLACE}")
    print("Scénario : réseau artériel (déblaiement prioritaire des grandes voies)\n")
    r = run_scenario(PLACE, "arteriel")
    print(f"  Coût total journalier        : {r['cout_total']} $")
    print(f"  Km parcourus                 : {r['km_total']} km")
    print(f"  Heures totales               : {r['heures_total']} h")
    print(f"  Part à vide                  : {r['part_a_vide'] * 100:.1f} %")
    print(f"  Véhicules pour finir en <=8h : {r['nb_vehicules_8h']}")
    print(f"  T1 (réseau prioritaire dégagé): {r['T1_reseau_prioritaire_h']} h")
    print(f"  Couverture prioritaire (1/2/4h): {r['couverture_prioritaire']}")
    print("\nDémonstration OK.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Vérifier la démo sur le cache**

Run: `python demo.py`
Expected: affiche les indicateurs et `Démonstration OK.` sans exception.

- [ ] **Step 3: Commit**

```bash
git add demo.py
git commit -m "feat: add demonstration script (Outremont, arterial scenario)"
```

---

## Task 12: Interface graphique Streamlit (`app.py`)

**Files:**
- Create: `app.py`
- Modify: `requirements.txt` (ajouter `streamlit`, `folium`, `streamlit-folium`)

Vérification manuelle (lancement de l'app).

- [ ] **Step 1: Ajouter les dépendances**

Dans `requirements.txt`, ajouter :
```
streamlit
folium
streamlit-folium
```

- [ ] **Step 2: Implémenter `app.py`**

```python
"""Interface graphique du projet (Streamlit).

Lit les sorties précalculées par `python scenarios.py --all` (sectors/*/resultats.json)
pour un affichage instantané. Lancement : streamlit run app.py
"""
import json
import os

import streamlit as st

from scenarios import SECTORS, SECTORS_DIR

st.set_page_config(page_title="Déneiger Montréal", layout="wide")
st.title("Déneiger Montréal — priorisation des tournées")

slug = st.sidebar.selectbox("Secteur", list(SECTORS.keys()))
scenario = st.sidebar.selectbox(
    "Scénario", ["arteriel", "services", "transport", "baseline"]
)

results_path = os.path.join(SECTORS_DIR, slug, "resultats.json")
if not os.path.exists(results_path):
    st.warning("Résultats absents. Lance d'abord : python scenarios.py --all")
    st.stop()

with open(results_path, encoding="utf-8") as f:
    results = json.load(f)

r = results[scenario]

col1, col2, col3 = st.columns(3)
col1.metric("Coût total ($)", r["cout_total"])
col2.metric("Km parcourus", r["km_total"])
col3.metric("Heures totales", r["heures_total"])
if "T1_reseau_prioritaire_h" in r:
    st.metric("T1 — réseau prioritaire dégagé (h)", r["T1_reseau_prioritaire_h"])

st.subheader("Carte du réseau prioritaire")
png = os.path.join(SECTORS_DIR, slug, f"carte_{scenario}.png")
if os.path.exists(png):
    st.image(png, use_column_width=True)
else:
    st.info("Carte non disponible pour la baseline.")

st.subheader("Coût en fonction du nombre de véhicules")
curve = r["courbe_cout"]
st.line_chart({"coût ($)": {str(n): c for n, c in curve}})

st.subheader("Comparatif des scénarios (ce secteur)")
st.table([
    {"scénario": s, "coût": v["cout_total"], "km": v["km_total"],
     "heures": v["heures_total"], "à vide %": round(v["part_a_vide"] * 100, 1)}
    for s, v in results.items()
])
```

- [ ] **Step 3: Vérifier que l'app démarre**

Run: `python -c "import ast; ast.parse(open('app.py').read()); print('syntaxe OK')"`
Expected: `syntaxe OK`.
Puis (manuel) : `streamlit run app.py`, sélectionner Outremont / artériel, vérifier l'affichage des métriques, de la carte et de la courbe.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt app.py
git commit -m "feat: add Streamlit graphical interface"
```

---

## Task 13: Livrables et documentation (`AUTHORS`, `README`, `THEORY`)

**Files:**
- Create: `AUTHORS`
- Modify: `README.md` (structure, lancement démo + app)
- Modify: `THEORY.md` (sections priorisation, coût(N), 2 phases)

- [ ] **Step 1: Créer `AUTHORS`**

```
amokrane.ait-taouit
imran.belmessaoud
emmanueli-david-valle.mvoula-moukouyou
amar.kaci
christina.gapy
```

- [ ] **Step 2: Mettre à jour la section « Structure du projet » de `README.md`**

Remplacer le bloc arborescence par :
```
ero1/
├── AUTHORS               # auteurs
├── snowplow_routing.py   # solveur (Postier Rural) + utilitaires OSM
├── priorities.py         # classification prioritaire (3 scénarios)
├── cost_model.py         # modèle de coût f(N)
├── scenarios.py          # orchestration 2 phases + indicateurs + exports
├── demo.py               # script de démonstration
├── app.py                # interface graphique Streamlit
├── sectors/              # résultats par secteur (JSON + cartes)
├── comparaison_scenarios.csv
├── THEORY.md / Limits.md / requirements.txt / README.md
└── tests/                # tests unitaires (pytest)
```
Et ajouter une section « Lancer » :
```markdown
## Lancer

```bash
python demo.py                 # démonstration (Outremont, scénario artériel)
python scenarios.py --all      # calcule les 4 secteurs -> sectors/ + comparaison_scenarios.csv
streamlit run app.py           # interface graphique (après --all)
python -m pytest               # tests unitaires
```
```

- [ ] **Step 3: Compléter `THEORY.md`**

Ajouter une section après la section 7 (« Le pipeline complet ») expliquant :
- la **priorisation par phases** (phase 1 = réseau prioritaire via Postier Rural, phase 2 = le reste) ;
- les **trois scénarios** (artériel / services essentiels / transport collectif) et leur critère ;
- le **modèle de coût `f(N)`** (formule de `cost_model.py`) et l'hypothèse de flotte idéalisée ;
- l'**indicateur T₁** (temps avant réseau prioritaire dégagé).

Texte à insérer :
```markdown
## 7bis. Priorisation : dégager le réseau structurant d'abord

Toutes les rues ne se valent pas. On classe chaque rue en « prioritaire » (tier 1)
ou non, selon le scénario, puis on route en **deux phases** :

1. **Phase 1** — couvrir tout le réseau prioritaire au moindre coût, en s'autorisant
   à traverser les autres rues comme simples connecteurs (c'est le **Problème du
   Postier Rural** : couvrir un sous-ensemble d'arêtes). L'indicateur clé **T₁** est
   la durée de cette phase = temps avant que 100 % du réseau prioritaire soit dégagé.
2. **Phase 2** — couvrir le reste, en réutilisant les rues prioritaires comme connecteurs.

Trois scénarios définissent « prioritaire » différemment : **réseau artériel** (grandes
voies), **accès aux services essentiels** (rues près des hôpitaux, écoles, casernes) et
**transport collectif** (rues desservies par des lignes de bus).

## 8bis. Coût en fonction du nombre de véhicules

Pour `N` véhicules se partageant idéalement le travail (temps/véhicule = T/N) :

    coût(N) = 500·N + 1,1·L + 1,1·min(T, 8N) + 1,3·max(T − 8N, 0)

où `L` est la distance totale (km) et `T = L/10` le temps total (h). La flotte
optimale est le plus petit `N` éliminant les heures supplémentaires (`T/N ≤ 8`).
```

- [ ] **Step 4: Vérifier le lint global**

Run: `ruff check .`
Expected: `All checks passed!` (ou corriger les avertissements signalés).

- [ ] **Step 5: Lancer toute la suite de tests**

Run: `python -m pytest -v`
Expected: tous les tests PASS.

- [ ] **Step 6: Commit**

```bash
git add AUTHORS README.md THEORY.md
git commit -m "docs: add AUTHORS, update README and THEORY for prioritization"
```

---

## Self-Review

**Couverture de la spec :**
- Solveur généralisé (Postier Rural) → Task 1 ✓
- `osmnx_to_graph` + longueurs → Task 2 ✓
- Modèle de coût f(N) → Task 3 ✓
- 3 scénarios (artériel / services / transport) → Tasks 4, 5, 6 ✓
- Indicateurs génériques + spécifiques → Tasks 7, 8 ✓
- Routage 2 phases + baseline → Task 9 ✓
- Sorties `sectors/`, GeoJSON/PNG, comparatif CSV → Task 10 ✓
- Script de démo → Task 11 ✓
- Interface Streamlit → Task 12 ✓
- `AUTHORS`, README, THEORY, requirements → Tasks 1/6/10/12/13 ✓

**Note GeoJSON :** la spec mentionnait un export `.geojson` par scénario pour l'UI ; le plan affiche la carte via le PNG précalculé (plus simple, suffisant pour l'app). L'export GeoJSON est volontairement omis (YAGNI) puisque l'app n'en a plus besoin avec l'affichage image. À réintroduire seulement si une carte folium interactive est exigée.

**Cohérence des types :** `required`/ensembles prioritaires = `set` de `(u,v)` partout ; `lengths` = dict `(u,v) -> mètres` partout ; `run_scenario` renvoie un dict dont les clés sont consommées à l'identique par `export_sector`, `demo.py` et `app.py`.

**Placeholders :** aucun TODO/TBD dans le code ; les seuls « à compléter » sont les noms d'auteurs dans `AUTHORS` (donnée utilisateur) et les co-équipiers.
