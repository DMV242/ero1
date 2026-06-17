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
