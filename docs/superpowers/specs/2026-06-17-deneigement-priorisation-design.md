# Design — Priorisation du déneigement, modèle de coût et interface

*Projet ERO1 « Déneiger Montréal ». Date : 2026-06-17.*

## 1. Objectif

Compléter le moteur de routage existant (Postier Chinois uniforme) pour répondre
aux points de la mission encore manquants :

1. **Trois scénarios de priorisation** du déneigement.
2. Itinéraires des véhicules — *déjà fait* (solveur ILP + Hierholzer).
3. **Modèle de coût** des opérations en fonction du **nombre de véhicules** `N`.
4. **Comparaison** des trois scénarios via des indicateurs, sur les 4 secteurs.

Plus les livrables de forme manquants : `AUTHORS`, sous-arborescence des 4 secteurs,
script de démonstration, et une interface graphique (bonus).

Le **rapport PDF** (argumentaire sourcé, projection sur les habitants) reste rédigé
par l'équipe ; ce travail produit le **socle quantitatif** (chiffres, tableaux, cartes)
qui le nourrit.

## 2. Périmètre et hypothèses

- **Secteurs étudiés** : Outremont, Verdun, Anjou, Rivière-des-Prairies–Pointe-aux-Trembles.
- **Données** : OpenStreetMap via `osmnx` (réseau routier `drive`, POI, lignes de bus).
- **Sens de circulation** : respectés structurellement (rue à sens unique = arc, jamais
  d'arête inverse) — cf. `THEORY.md`.
- **Connexité** : on travaille sur la plus grande composante **fortement** connexe
  (déjà appliqué dans `osmnx_to_graph`, cf. `Limits.md`). Conséquence assumée : les
  rues hors de cette composante (artefacts de découpe à la frontière) ne sont pas routées.
- **Tarifs imposés** (énoncé) : coût fixe 500 $/jour/véhicule ; 1,1 $/km ;
  1,1 $/h jusqu'à 8 h puis 1,3 $/h ; vitesse moyenne 10 km/h.
- **Priorisation = ordre/délai de service** : on dégage *tout*, mais le réseau
  prioritaire d'abord (modèle réel de Montréal : artériel → collecteur → local).
- **Flotte** : modèle **analytique idéalisé** — le travail d'un secteur est réparti
  parfaitement entre `N` véhicules (temps/véhicule = temps_total / N). Pas de découpage
  géométrique réel des tournées (extension k-postiers hors périmètre).

## 3. Architecture

| Fichier | Statut | Responsabilité |
|---|---|---|
| `snowplow_routing.py` | modifié | Solveur ILP généralisé (Postier Rural) + `osmnx_to_graph` étendu (renvoie aussi les longueurs) + `build_route` (inchangé) |
| `priorities.py` | nouveau | Classification des rues prioritaires, une fonction par scénario |
| `cost_model.py` | nouveau | Métriques de tournée + coût journalier `f(N)` |
| `scenarios.py` | nouveau | Orchestration phase 1 / phase 2, calcul des indicateurs, export des sorties + cartes |
| `app.py` | nouveau | Interface graphique Streamlit (lit les sorties précalculées) |
| `demo.py` | nouveau | Script de démonstration CLI exigé par le sujet |
| `AUTHORS` | nouveau | Liste des auteurs |
| `README.md` | modifié | Structure, secteurs, lancement démo + interface |
| `requirements.txt` | modifié | Ajout : osmnx, matplotlib, geopandas, streamlit, folium, streamlit-folium |
| `THEORY.md` | modifié | Sections priorisation, coût(N), routage en 2 phases |

Chaque module a une responsabilité unique et une interface claire ; `scenarios.py`
est le seul à orchestrer, les autres sont des bibliothèques pures (testables isolément).

## 4. Moteur

### 4.1 Généralisation de `solve_sector`

```python
solve_sector(vertices, edges, arcs, required=None, backend="CBC")
```

- Toutes les arêtes/arcs gardent leur variable `x` (connexité, connecteurs) ; la
  conservation de flot s'applique partout — **inchangé**.
- La contrainte de couverture (`x ≥ 1`, ou `x[i,j] + x[j,i] ≥ 1` pour une arête) ne
  s'applique **qu'aux rues de `required`**.
- `required=None` ⇒ toutes les rues requises ⇒ **comportement actuel à l'identique**
  (rétro-compatibilité : `__main__` et `test_osmnx.py` continuent de fonctionner).
- Appartenance direction-agnostique pour les arêtes : `(i,j)` requise si `(i,j) ∈ required`
  **ou** `(j,i) ∈ required`. `required` contient des paires de nœuds `(u,v)`.
- L'objectif (minimiser `Σ cost·x`) est inchangé : les rues non requises utilisées comme
  connecteurs coûtent (deadhead réaliste).

C'est le **Problème du Postier Rural** : couvrir un sous-ensemble d'arêtes, en pouvant
traverser les autres librement, en boucle fermée et à coût minimal. Faisabilité garantie
car le graphe (réduit à sa CFC) est fortement connexe.

### 4.2 `osmnx_to_graph` étendu

Renvoie désormais `(vertices, edges, arcs, lengths)` où `lengths[(u,v)]` est la longueur
en mètres de chaque rue (nécessaire au calcul des km/temps réels par phase, indépendant
du coût ILP). La réduction à la plus grande CFC reste en tête de fonction.

### 4.3 Routage en deux phases (par secteur × scénario)

```
G --load_sector_osmnx + réduction CFC--> graphe fortement connexe
  --osmnx_to_graph--> vertices, edges, arcs, lengths
  prioritaires = priorities.<scénario>(G)

Phase 1 : solve_sector(..., required = prioritaires)
          -> passes1 -> build_route(start) -> route1 ; L1 (km), T1 (h) = L1/10
Phase 2 : solve_sector(..., required = NON-prioritaires)
          -> passes2 -> build_route(start) -> route2 ; L2 (km), T2 (h)

Total : L = L1 + L2 ; T = T1 + T2
```

Deux tournées fermées (retour au dépôt entre les phases). `T1` = temps avant que 100 %
du réseau prioritaire soit dégagé (indicateur signature).

## 5. Scénarios de priorisation (`priorities.py`)

Chaque fonction prend `G` (et au besoin le lieu/polygone) et renvoie un `set` de paires
`(u,v)` constituant le réseau prioritaire (tier 1).

| Scénario | Fonction | Règle tier 1 | Source OSM |
|---|---|---|---|
| Réseau artériel | `arterial(G)` | tag `highway` ∈ {motorway, trunk, primary, secondary, tertiary} (+ `_link`) | déjà dans `G` |
| Accès aux services essentiels | `essential_services(G, place, dist=150)` | rues à ≤ `dist` m d'un hôpital, école, caserne (`fire_station`), CHSLD | `ox.features_from_place(tags={"amenity":[...]})` + proximité |
| Transport collectif | `transit(G, place)` | rues recouvertes par une ligne de bus | `ox.features_from_place(tags={"route":"bus"})` + intersection (buffer) avec les arêtes |

- `highway` peut être une chaîne ou une liste : tester l'appartenance dans les deux cas.
- Proximité POI (`essential_services`) : pour chaque POI, marquer les arêtes à ≤ `dist`
  mètres (via `ox.distance.nearest_edges` puis expansion, ou buffer géométrique geopandas).
- Bus (`transit`) : bufferiser les géométries de lignes et marquer les arêtes intersectées.
- Les seuils géométriques (`dist`, largeur de buffer bus) sont des **hypothèses réglables**
  à documenter dans le rapport.

## 6. Modèle de coût `f(N)` (`cost_model.py`)

À partir de la longueur totale parcourue `L` (km) et du temps total `T = L/10` (h) :

```
coût(N) = 500·N                  # coût fixe par véhicule
        + 1,1·L                   # coût kilométrique (indépendant de N)
        + 1,1·min(T, 8·N)         # heures normales (≤ 8 h/véhicule)
        + 1,3·max(T − 8·N, 0)     # heures supplémentaires
```

API :
- `daily_cost(L, T, N) -> float`
- `cost_curve(L, T, N_max) -> list[(N, coût)]`
- `optimal_fleet(L, T) -> int` : plus petit `N` tel que `T/N ≤ 8` (élimine les heures sup).

## 7. Indicateurs

**Génériques** (comparables entre scénarios, calculés par `scenarios.py`) :
- coût total journalier ($) à `N` fixé **et** courbe coût(N) ;
- longueur totale parcourue (km) ; **part « à vide »** (deadhead %) = `(L − longueur_réseau)/L` ;
- temps total (h) ;
- nb de véhicules pour finir en ≤ 8 h (`optimal_fleet`).

**Spécifiques à la priorisation** :
- **T₁** : temps avant 100 % du réseau prioritaire dégagé (h) ;
- longueur du réseau prioritaire (km) et sa part du réseau total ;
- **% du réseau prioritaire dégagé à t = 1 h / 2 h / 4 h** (lu sur `route1` ordonnée et les longueurs) ;
- **surcoût de priorisation** = coût(phasé) − coût(CPP uniforme).

**Ligne de base** : le CPP uniforme (toutes rues requises, une phase) sert de référence
pour la comparaison.

## 8. Sorties et structure de rendu

```
ero1/
├── AUTHORS
├── README.md
├── requirements.txt
├── THEORY.md
├── Limits.md
├── snowplow_routing.py
├── priorities.py
├── cost_model.py
├── scenarios.py
├── app.py
├── demo.py
├── sectors/
│   ├── outremont/
│   │   ├── resultats.json          # indicateurs des 3 scénarios + baseline
│   │   ├── arteriel.geojson        # réseau prioritaire + tournée (pour l'UI)
│   │   ├── services.geojson
│   │   ├── transport.geojson
│   │   ├── carte_arteriel.png      # image statique (pour le rapport PDF)
│   │   ├── carte_services.png
│   │   └── carte_transport.png
│   ├── verdun/
│   ├── anjou/
│   └── riviere-des-prairies-pointe-aux-trembles/
├── comparaison_scenarios.csv       # récap 4 secteurs × 3 scénarios + baseline
└── test_osmnx.py
```

`scenarios.py --all` calcule tout et écrit `sectors/` + `comparaison_scenarios.csv`.
Cartes via `osmnx` + `matplotlib` : réseau gris, réseau prioritaire surligné, tournée tracée.

## 9. Interface graphique (`app.py`, Streamlit)

- **Découplage calcul/affichage** : l'app lit les sorties **précalculées**
  (`resultats.json`, `<scenario>.geojson`) → affichage instantané. L'ILP n'est pas relancé
  en direct par défaut.
- **Contrôles** : menu secteur, menu scénario (+ « baseline uniforme »), curseur `N`,
  bouton « Recalculer en direct » (relance le solveur pour un petit secteur à la demande).
- **Affichage** : carte interactive folium (réseau prioritaire surligné + tournée) via
  `streamlit-folium` ; tableau d'indicateurs ; courbe coût(N) ; tableau comparatif des scénarios.
- **Lancement** : `streamlit run app.py`.

## 10. Script de démonstration (`demo.py`)

`python demo.py` : tourne rapidement sur **un** secteur (Outremont, scénario artériel) —
charge (cache OSM), lance les 2 phases, affiche les indicateurs, sauve une carte. C'est le
livrable « script exécutant une démonstration » exigé par le sujet. Coexiste avec `app.py`.

## 11. Dépendances

`requirements.txt` ajoute : `osmnx`, `matplotlib`, `geopandas`, `streamlit`, `folium`,
`streamlit-folium` (en plus de `ortools`, `networkx`, `ruff` déjà présents).

## 12. Limites et risques

- **Performance** : l'ILP sur un arrondissement entier peut être lent (RDP-PAT est grand) ;
  la démo reste rapide sur un petit secteur ; option de sous-échantillonnage (`point` + `radius_m`)
  pour le développement.
- **Seuils géométriques** (proximité POI 150 m, buffer bus) : hypothèses à assumer et à
  discuter dans le rapport.
- **Modèle de flotte idéalisé** : ne tient pas compte des trajets dépôt→zone ni d'un découpage
  réel des tournées (extension k-postiers possible).
- **Couverture** : rues hors de la plus grande CFC non routées (artefacts de découpe).
- **Données bus** : la complétude des relations `route=bus` dans OSM varie selon les secteurs.

## 13. Validation

- **Rétro-compatibilité** : `python snowplow_routing.py` (exemple 5 sommets) et
  `test_osmnx.py` donnent le même résultat qu'avant (`required=None`).
- **Tests unitaires** : `cost_model` (formule coût(N), `optimal_fleet`) ; `priorities`
  (classification sur un petit graphe synthétique annoté) ; `solve_sector` avec `required`
  (Postier Rural sur un petit cas où la solution optimale est connue à la main).
- **Bout en bout** : `scenarios.py --all` produit `sectors/` et `comparaison_scenarios.csv`
  sans erreur ; `T1 ≤ T` et la couverture du réseau prioritaire = 100 % pour chaque scénario.
- **Lint** : `ruff check` propre sur tous les fichiers.
