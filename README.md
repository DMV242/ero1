# Déneiger Montréal — ERO1

Routage optimal de déneigeuses sur le réseau routier de Montréal.  
Résout une variante du **Problème du Postier Chinois** via un programme linéaire en nombres entiers (OR-Tools / CBC), puis construit la tournée avec l'algorithme de Hierholzer.

## Installation

**Prérequis** : Python 3.9+

```bash
# Cloner le dépôt
git clone <url-du-repo>
cd ero1

# Créer un environnement virtuel (recommandé)
python -m venv .venv
source .venv/bin/activate   # Windows : .venv\Scripts\activate

# Installer les dépendances
pip install -r requirements.txt

# Pour utiliser les données OpenStreetMap (optionnel)
pip install osmnx
```

## Lancer le programme

```bash
python snowplow_routing.py
```

Cela exécute l'exemple intégré (graphe à 5 sommets avec rues à double et à sens unique) et affiche :

- le coût total optimal
- le nombre de passages par arc
- la tournée complète de la déneigeuse

Exemple de sortie :

```
Optimal total cost: 36

Passes per arc (only those driven):
  A -> B : 1x
  A -> D : 1x
  B -> A : 1x
  ...

Snowplow route (street order):
  D -> B -> A -> D -> E -> C -> B -> E -> D
```

## Utiliser le solveur sur vos propres données

```python
from snowplow_routing import solve_sector, build_route

vertices = ["A", "B", "C"]
edges = [("A", "B", 4), ("B", "C", 5)]   # rues à double sens (i, j, coût)
arcs  = [("A", "C", 3)]                  # rues à sens unique  (i, j, coût)

total_cost, passes = solve_sector(vertices, edges, arcs)
route = build_route(passes, start="A")
print(route)
```

### Depuis OpenStreetMap

```python
from snowplow_routing import load_sector_osmnx, osmnx_to_graph, solve_sector, build_route

G = load_sector_osmnx(place="Outremont, Montréal, Québec, Canada")
vertices, edges, arcs = osmnx_to_graph(G)

total_cost, passes = solve_sector(vertices, edges, arcs)
# start = n'importe quel sommet du graphe
route = build_route(passes, start=vertices[0])
```

> Nécessite `osmnx` et une connexion internet. Les données sont mises en cache localement.

## Structure du projet

```
ero1/
├── AUTHORS               # auteurs
├── snowplow_routing.py   # solveur (Postier Rural) + utilitaires OSM
├── priorities.py         # classification prioritaire (3 scénarios)
├── cost_model.py         # modèle de coût f(N)
├── scenarios.py          # orchestration 2 phases + indicateurs + exports
├── demo.py               # script de démonstration
├── app.py                # interface graphique Streamlit
├── sectors/              # résultats par secteur (JSON + cartes PNG)
├── comparaison_scenarios.csv
├── THEORY.md / Limits.md / requirements.txt / README.md
└── tests/                # tests unitaires (pytest)
```

## Lancer

```bash
python demo.py                 # démonstration (Outremont, scénario artériel)
python scenarios.py --all      # calcule les 4 secteurs -> sectors/ + comparaison_scenarios.csv
streamlit run app.py           # interface graphique (après --all)
python -m pytest               # tests unitaires
```

## Algorithme en bref

1. **Modélisation** — le réseau routier est converti en graphe orienté (arêtes bidirectionnelles + arcs unidirectionnels).
2. **ILP** — OR-Tools cherche combien de fois chaque arc doit être parcouru pour couvrir toutes les rues tout en respectant la conservation de flot (circuit fermé).
3. **Hierholzer** — le multiensemble d'arcs produit par l'ILP est converti en une séquence ordonnée de rues.

Voir [THEORY.md](THEORY.md) pour une explication détaillée sans prérequis mathématiques.

## Limites connues

Certaines limites sont déjà identifiées (notamment la forte connexité du graphe OSMnx, qui peut faire échouer le solveur ILP). Voir [Limits.md](Limits.md) : ce sont des points connus, à discuter dans le rapport de fin.
