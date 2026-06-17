# Limites connues

## Graphe non fortement connexe (OSMnx)

Le graphe retourné par `load_sector_osmnx()` n'est pas toujours fortement connexe.
Des rues à sens unique peuvent isoler certains noeuds (entrants seulement ou sortants seulement),
ce qui rend la contrainte de conservation de flot infaisable pour le solveur ILP.

**Symptôme** : `solve_sector()` retourne `None`.

**Correctif (intégré)** : `osmnx_to_graph()` extrait désormais la plus grande
composante fortement connexe avant conversion, ce qui garantit un graphe
toujours résoluble par le solveur.

```python
import networkx as nx
scc = max(nx.strongly_connected_components(G), key=len)
G = G.subgraph(scc).copy()
```

**Limite résiduelle** : les noeuds hors de cette composante sont ignorés ; les
rues qui leur sont rattachées ne sont donc pas déneigées dans le trajet calculé.

## Tournées de phase déconnectées (Postier Rural)

Le solveur ILP impose la conservation de flot par sommet mais pas la connexité.
Pour un réseau prioritaire dispersé, la solution optimale d'une phase peut former
plusieurs circuits disjoints. `build_route_all` les parcourt tous (un circuit
eulérien par composante), mais les **trajets de liaison entre composantes ne sont
pas explicitement routés** : le coût et le temps les ignorent (le véhicule est
supposé s'y déplacer à vide). Les indicateurs de distance/temps/coût restent
calculés sur l'ensemble des arcs parcourus ; seule la liaison inter-composantes
est approximée.
