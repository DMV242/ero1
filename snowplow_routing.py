"""
Snowplow routing for the "Déneiger Montréal" project (ERO1).

This solves a variant of the Chinese Postman Problem: route a snowplow so
that it covers EVERY street (edge/arc) at least once and returns to its
starting point, at minimum total cost.

Pipeline:
    raw OSM data --> graph (vertices, edges, arcs)
                 --> integer linear program (OR-Tools)
                 --> arc multiset (how many times each street is driven)
                 --> Hierholzer --> ordered route a plow can actually follow

The solver is GENERIC: solve_sector() takes any graph and returns the optimal
route. The same function is applied to Outremont, Verdun, Anjou and RDP-PAT;
only the input data changes.
"""

from collections import defaultdict
from ortools.linear_solver import pywraplp


COST_PER_KM = 1.1
COST_PER_HOUR = 1.1
SPEED_KMH = 10.0


def segment_cost(length_m):
    """Cost of a single street segment from its length in metres.

    A missing OSM `length` defaults to 0 (near-universal on `drive` networks)."""
    length_km = length_m / 1000.0
    time_h = length_km / SPEED_KMH
    return COST_PER_KM * length_km + COST_PER_HOUR * time_h


def solve_sector(vertices, edges, arcs, required=None, backend="CBC"):
    """
    vertices : list of vertex ids, e.g. ["A", "B", "C", "D", "E"]
    edges    : TWO-WAY streets, list of (i, j, cost)
    arcs     : ONE-WAY streets,  list of (i, j, cost)  -- from i to j only
    backend  : OR-Tools backend ("CBC" for integer counts, "SAT" also works)

    Returns (total_cost, passes) where passes[(i, j)] = number of times the
    plow drives arc i -> j. Returns None if no feasible solution exists.
    """

    cost = {}
    edge_pairs = []

    for i, j, c in edges:
        cost[(i, j)] = c
        cost[(j, i)] = c
        edge_pairs.append((i, j))

    for i, j, c in arcs:
        cost[(i, j)] = c

    def is_required(i, j):
        if required is None:
            return True
        return (i, j) in required or (j, i) in required

    solver = pywraplp.Solver.CreateSolver(backend)
    if not solver:
        return None
    infinity = solver.infinity()

    x = {(i, j): solver.IntVar(0, infinity, f"x_{i}_{j}") for (i, j) in cost}

    for i, j in edge_pairs:
        if is_required(i, j):
            solver.Add(x[(i, j)] + x[(j, i)] >= 1)

    for i, j, c in arcs:
        if is_required(i, j):
            solver.Add(x[(i, j)] >= 1)

    # Flow conservation: in-degree == out-degree at each vertex.
    # Pre-group arcs by head/tail so this is O(E + V) instead of O(V * E)
    # (the naive "scan every arc for every vertex" is quadratic and makes
    # large sectors like RDP-PAT extremely slow to build).
    incoming = defaultdict(list)
    outgoing = defaultdict(list)
    for (i, j) in cost:
        outgoing[i].append(x[(i, j)])
        incoming[j].append(x[(i, j)])

    for v in vertices:
        solver.Add(solver.Sum(incoming[v]) == solver.Sum(outgoing[v]))

    solver.Minimize(solver.Sum([cost[(i, j)] * x[(i, j)] for (i, j) in cost]))

    status = solver.Solve()
    if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        return None

    passes = {(i, j): int(round(x[(i, j)].solution_value())) for (i, j) in cost}
    return solver.Objective().Value(), passes


def _hierholzer(remaining, start):
    """Eulerian circuit through the component reachable from `start`, consuming
    arcs from `remaining` (a dict {(i,j): count}) in place."""
    out_arcs = defaultdict(list)
    for (i, j), n in remaining.items():
        if n > 0:
            out_arcs[i].append(j)

    route = []
    stack = [start]
    while stack:
        v = stack[-1]
        nxt = None
        for j in out_arcs[v]:
            if remaining.get((v, j), 0) > 0:
                nxt = j
                break
        if nxt is not None:
            remaining[(v, nxt)] -= 1
            stack.append(nxt)
        else:
            route.append(stack.pop())
    route.reverse()
    return route


def build_route(passes, start):
    """Single closed Eulerian circuit from `start` (Hierholzer).

    passes : dict {(i, j): number of passes}  -- output of solve_sector
    start  : starting vertex (the plow returns here at the end)
    Returns a list of vertices [start, ..., start].

    Assumes the driven arcs form ONE connected, balanced component (true for the
    uniform Chinese Postman over a strongly connected sector). For a sparse Rural
    Postman phase whose driven arcs may be disconnected, use build_route_all."""
    remaining = {arc: n for arc, n in passes.items() if n > 0}
    return _hierholzer(remaining, start)


def build_route_all(passes):
    """Ordered route covering EVERY driven arc, even when they form several
    disconnected balanced circuits (the usual case for a sparse Rural Postman
    phase). Returns the concatenation of one Eulerian circuit per component; for
    a connected driven graph this equals build_route. Transitions between
    components are not explicitly routed (the plow is assumed to deadhead)."""
    remaining = {arc: n for arc, n in passes.items() if n > 0}
    full = []
    while any(n > 0 for n in remaining.values()):
        start = next(arc[0] for arc, n in remaining.items() if n > 0)
        full.extend(_hierholzer(remaining, start))
    return full


def largest_strongly_connected_subgraph(G):
    """Return G reduced to its largest strongly connected component (a copy).

    Guarantees the ILP flow-conservation is feasible, and lets maps display
    exactly what is routed (same reduction everywhere)."""
    import networkx as nx

    if G.number_of_nodes() == 0:
        return G
    scc = max(nx.strongly_connected_components(G), key=len)
    return G.subgraph(scc).copy()


def load_sector_osmnx(place=None, point=None, radius_m=None):
    """
    Download the road network of a sector from OpenStreetMap.
        - by name:   place="Outremont, Montréal, Québec, Canada"
        - by centre: point=(lat, lon), radius_m=500
    Returns an OSMnx MultiDiGraph. Run on a machine with internet access.
    """
    import osmnx as ox

    ox.settings.use_cache = True
    if place is not None:
        return ox.graph_from_place(place, network_type="drive")
    elif point is not None and radius_m is not None:
        return ox.graph_from_point(point, dist=radius_m, network_type="drive")
    else:
        raise ValueError("Provide either place, or point + radius_m.")


def osmnx_to_graph(G):
    """
    Convert an OSMnx MultiDiGraph into (vertices, edges, arcs, lengths) for the solver.

    OSMnx already returns a DIRECTED graph: a two-way street appears as TWO
    opposite arcs; a one-way street as a single arc. We regroup by vertex pair:
        - both directions present -> a two-way EDGE
        - only one direction      -> a one-way ARC

    This rule is the structural enforcement of the traffic code: a one-way
    street never gets a reverse variable, so the plow can never be routed
    against the legal direction.

    The raw OSM graph is not always strongly connected: one-way streets can
    isolate nodes (in-only or out-only), which makes the ILP flow-conservation
    constraint infeasible (solve_sector would return None). We therefore keep
    only the largest strongly connected component, which is always solver-ready.
    """
    G = largest_strongly_connected_subgraph(G)

    vertices = list(G.nodes())

    arc_cost = {}
    lengths = {}
    for u, v, data in G.edges(data=True):
        length_m = data.get("length", 0.0)
        arc_cost[(u, v)] = segment_cost(length_m)
        lengths[(u, v)] = length_m

    edges, arcs, seen = [], [], set()
    for (u, v), c in arc_cost.items():
        if (u, v) in seen:
            continue
        if (v, u) in arc_cost:
            edges.append((u, v, round(c, 4)))
            seen.add((u, v))
            seen.add((v, u))
        else:
            arcs.append((u, v, round(c, 4)))
            seen.add((u, v))

    return vertices, edges, arcs, lengths


if __name__ == "__main__":
    vertices = ["A", "B", "C", "D", "E"]

    edges = [
        ("A", "B", 4),
        ("B", "C", 5),
        ("A", "D", 6),
        ("D", "E", 3),
        ("C", "E", 5),
        ("B", "E", 7),
    ]

    arcs = [
        ("D", "B", 2),
    ]

    result = solve_sector(vertices, edges, arcs)
    if result:
        total_cost, passes = result
        print(f"Optimal total cost: {total_cost:.0f}\n")
        print("Passes per arc (only those driven):")
        for (i, j), n in sorted(passes.items()):
            if n > 0:
                mark = "  <-- re-driven (rebalancing)" if n > 1 else ""
                print(f"  {i} -> {j} : {n}x{mark}")

        route = build_route(passes, start="D")
        print("\nSnowplow route (street order):")
        print("  " + " -> ".join(route))
