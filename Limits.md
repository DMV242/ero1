# Limites connues

## Graphe non fortement connexe (OSMnx)

Le graphe retourné par `load_sector_osmnx()` n'est pas toujours fortement connexe.
Des rues à sens unique peuvent isoler certains noeuds (entrants seulement ou sortants seulement),
ce qui rend la contrainte de conservation de flot infaisable pour le solveur ILP.

**Symptôme** : `solve_sector()` retourne `None`.

**Correctif à appliquer (pas encore intégré)** : extraire la plus grande composante fortement connexe avant conversion.

```python
import networkx as nx
scc = max(nx.strongly_connected_components(G), key=len)
G = G.subgraph(scc).copy()
```

À intégrer dans `osmnx_to_graph()` ou en amont dans le pipeline.
