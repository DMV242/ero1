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
