# Déneiger Montréal — ERO1

Routage optimal de déneigeuses sur le réseau routier de Montréal.

Le problème n'est pas un plus court chemin mais une **couverture de rues** : chaque rue doit être déblayée au moins une fois, à coût minimal, en revenant au point de départ. C'est une variante du **problème du postier chinois** (et du **postier rural** pour les phases de priorisation). Il est résolu **exactement** par un programme linéaire en nombres entiers (OR-Tools / CP-SAT), puis la tournée est reconstruite par l'algorithme de **Hierholzer**.

Le projet compare en plus **trois politiques de priorisation** (réseau artériel, services essentiels, transport collectif) sur quatre arrondissements : **Outremont**, **Verdun**, **Anjou** et **Rivière-des-Prairies–Pointe-aux-Trembles**.

> Le rapport de formalisation complet est dans [rapport_deneiger_montreal.pdf](rapport_deneiger_montreal.pdf). L'explication théorique sans prérequis mathématiques est dans [THEORY.md](THEORY.md).

## Installation

**Prérequis** : Python 3.9+

```bash
git clone <url-du-repo>
cd ero1

# Environnement virtuel (recommandé)
python -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate

pip install -r requirements.txt
pip install osmnx                  # nécessaire pour charger les données OpenStreetMap
```

## Utilisation

```bash
python demo.py                 # démonstration : Outremont, scénario artériel + indicateurs clés
python scenarios.py --all      # calcule les 4 secteurs -> sectors/ + comparaison_scenarios.csv
streamlit run app.py           # interface graphique (à lancer après --all)
python -m pytest               # tests unitaires
python snowplow_routing.py     # exemple intégré (petit graphe à 5 sommets), sans réseau OSM
```

`scenarios.py --all` télécharge les réseaux OSM (mis en cache localement) et écrit, pour chaque secteur, `sectors/<secteur>/resultats.json` et trois cartes `carte_*.png`, plus le comparatif global `comparaison_scenarios.csv`.

### Utiliser le solveur sur ses propres données

```python
from snowplow_routing import solve_sector, build_route

vertices = ["A", "B", "C"]
edges = [("A", "B", 4), ("B", "C", 5)]   # rues à double sens (i, j, coût)
arcs  = [("A", "C", 3)]                  # rues à sens unique  (i, j, coût)

total_cost, passes = solve_sector(vertices, edges, arcs)
route = build_route(passes, start="A")
print(total_cost, route)
```

### Depuis OpenStreetMap

```python
from snowplow_routing import load_sector_osmnx, osmnx_to_graph, solve_sector, build_route

G = load_sector_osmnx(place="Outremont, Montréal, Québec, Canada")
vertices, edges, arcs, lengths = osmnx_to_graph(G)
total_cost, passes = solve_sector(vertices, edges, arcs)
route = build_route(passes, start=vertices[0])
```

> Nécessite `osmnx` et une connexion internet (données mises en cache dans `cache/`).

## Structure du projet

```
ero1/
├── AUTHORS                       # auteurs
├── snowplow_routing.py           # solveur (postier chinois/rural) + utilitaires OSM
├── priorities.py                 # classification du réseau prioritaire (3 scénarios)
├── cost_model.py                 # modèle de coût (tarifs imposés)
├── scenarios.py                  # orchestration 2 phases + indicateurs + exports
├── demo.py                       # script de démonstration
├── app.py                        # interface graphique Streamlit
├── sectors/                      # résultats par secteur (resultats.json + cartes PNG)
├── comparaison_scenarios.csv     # comparatif généré (tous secteurs, tous scénarios)
├── tests/                        # tests unitaires (pytest)
├── rapport_deneiger_montreal.pdf # rapport de formalisation
└── THEORY.md / Limits.md / requirements.txt / README.md
```

## Description des modules

### `snowplow_routing.py` — cœur algorithmique

Module **générique** : la même fonction traite n'importe quel secteur, seules les données changent.

- **`segment_cost(length_m)`** — convertit la longueur d'une rue (m) en coût (km + temps au tarif normal).
- **`solve_sector(vertices, edges, arcs, required=None, backend="SAT", time_limit_s=None)`** — construit et résout le PLNE. Les variables entières comptent les passages sur chaque arc ; les contraintes assurent la couverture des rues requises et la conservation du flot (circuit fermé) ; l'objectif minimise le coût total. Renvoie `(coût, passes)` ou `None` si infaisable. Back-end **CP-SAT** par défaut (`"SAT"`), bien plus rapide que `"CBC"` sur les gros secteurs.
- **`build_route(passes, start)`** / **`build_route_all(passes)`** — reconstruisent la tournée ordonnée par Hierholzer. `build_route_all` couvre tous les arcs même lorsqu'ils forment plusieurs circuits disjoints (cas d'un réseau prioritaire dispersé).
- **`largest_strongly_connected_subgraph(G)`** — réduit le graphe à sa plus grande composante fortement connexe (garantit la faisabilité du flot).
- **`load_sector_osmnx(...)`** / **`osmnx_to_graph(G)`** — téléchargent un secteur depuis OpenStreetMap et le convertissent en `(vertices, edges, arcs, lengths)`. Une rue à double sens devient deux arcs opposés, une rue à sens unique un seul arc : le code de la route est encodé structurellement.

### `priorities.py` — réseau prioritaire (tier 1)

Chaque fonction renvoie l'ensemble des rues prioritaires, passé à `solve_sector` en phase 1 :

- **`arterial(G)`** — grandes voies structurantes (tags OSM `highway` : *motorway, trunk, primary, secondary, tertiary* et bretelles).
- **`essential_services(G, place, dist=150, amenities=(hospital, school, fire_station, clinic))`** — rues à ≤ 150 m d'un service essentiel.
- **`transit(G, place, dist=100)`** — rues à ≤ 100 m d'un arrêt de bus (`highway=bus_stop`).

### `cost_model.py` — modèle économique

Tarifs imposés par l'énoncé :

| Poste | Valeur |
|---|---|
| Coût fixe / déneigeuse | 500 $/jour |
| Coût kilométrique | 1,1 $/km |
| Coût horaire (≤ 8 h) | 1,1 $/h |
| Coût horaire (> 8 h) | 1,3 $/h |
| Vitesse moyenne | 10 km/h |

- **`daily_cost(total_km, total_hours, n_vehicles)`** — coût journalier total.
- **`cost_curve(...)`** / **`optimal_fleet(total_hours)`** — courbe coût selon la taille de flotte et plus petit `N` tel que chaque véhicule tienne en 8 h.

### `scenarios.py` — orchestration & indicateurs

- **`run_scenario(place, scenario, ...)`** — route un secteur **en deux phases** (phase 1 : réseau prioritaire ; phase 2 : reste) et calcule les indicateurs.
- **`run_baseline(place, ...)`** — postier chinois uniforme (sans priorisation), ligne de référence.
- **`route_metrics`**, **`coverage_over_time`** — km/heures parcourus et fraction du réseau prioritaire dégagée à 1 h / 2 h / 4 h.
- **`export_sector`** / **`run_all`** — calculent tout, écrivent `sectors/` et `comparaison_scenarios.csv`.

### `demo.py`, `app.py`

- **`demo.py`** — démonstration courte (Outremont, scénario artériel) affichant les indicateurs clés. Livrable « script de démonstration ».
- **`app.py`** — interface Streamlit pour comparer visuellement les scénarios (après `scenarios.py --all`).

## Indicateurs produits

**Génériques** (toute tournée) : coût total journalier, distance totale (km), temps total (h), part de kilomètres à vide, nombre minimal de véhicules pour terminer en ≤ 8 h.

**Spécifiques à la priorisation** : durée de dégagement du réseau prioritaire (T1) et taux de couverture de ce réseau après 1 h, 2 h et 4 h.

## Limites connues

Plusieurs limites sont assumées (dépendance aux données OSM, réduction à la plus grande composante fortement connexe, vitesse constante à 10 km/h, répartition idéale de la flotte, point de départ simplifié, priorisation à seuils de distance fixes). Elles sont détaillées dans [Limits.md](Limits.md) et discutées dans le rapport.
