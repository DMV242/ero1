# Rapport technique — Projet Déneiger Montréal

**Auteurs :** Amokrane Aït-Taouit · Imran Belmessaoud · Emmanueli-David Valle Mvoula-Moukouyou · Amar Kaci · Christina Gapy

---

## Partie I — Formalisation et méthode de résolution

### 1. Données et périmètre

**Données fournies (énoncé).** Les opérations de déblaiement sont chiffrées avec les tarifs imposés suivants, qui constituent l'entrée du modèle économique :

| Poste | Valeur |
|---|---|
| Coût fixe par déneigeuse | 500 $/jour |
| Coût kilométrique | 1,1 $/km |
| Coût horaire (8 premières heures) | 1,1 $/h |
| Coût horaire (au-delà de 8 h) | 1,3 $/h |
| Vitesse moyenne de travail | 10 km/h |

**Périmètre géographique.** Quatre arrondissements de Montréal sont étudiés : **Outremont**, **Verdun**, **Anjou** et **Rivière-des-Prairies–Pointe-aux-Trembles** (RDP-PAT). Le réseau routier de chaque secteur est extrait d'OpenStreetMap (réseau carrossable, `network_type="drive"`).

**Contraintes prises en compte.**

- Couverture intégrale : chaque rue du secteur doit être déblayée au moins une fois.
- Respect du code de la route : une rue à sens unique n'est parcourue que dans son sens légal.
- Retour au point de départ : la tournée forme un circuit fermé (continuité du service).
- Tarification réelle imposée (coûts fixes, kilométriques et horaires avec heures supplémentaires).
- Dimensionnement de flotte pour terminer une opération dans une journée de travail (≤ 8 h).

**Contraintes volontairement écartées** (cf. §6) : météo et accumulation de neige variables, capacité d'emport et déchargement, fenêtres horaires de stationnement, et localisation d'un dépôt physique.

### 2. Hypothèses et choix de modélisation

Le réseau est modélisé comme un **graphe orienté** `G = (V, A)` :

- les sommets `V` représentent les intersections ;
- les arcs `A` représentent les rues. Une rue à **double sens** devient deux arcs opposés `(i, j)`/`(j, i)` ; une rue à **sens unique** un seul arc. C'est l'encodage structurel du code de la route : sans variable inverse, une rue à sens unique ne peut jamais être empruntée à contresens.

Le graphe OSM brut n'est pas toujours fortement connexe (des sens uniques peuvent isoler des sommets), ce qui rendrait la conservation de flot infaisable. On **réduit donc le graphe à sa plus grande composante fortement connexe (CFC)**, toujours résoluble et identique pour le calcul comme pour les cartes.

**Hypothèses de travail :**

1. Vitesse de déblaiement constante (10 km/h) : `temps = distance / vitesse`.
2. Coût d'un segment de longueur `L` (m) : `c = 1,1·(L/1000) + 1,1·(L/1000)/10`, soit la somme du coût kilométrique et du coût horaire au tarif normal.
3. Flotte idéalisée : le travail total est réparti équitablement entre `N` véhicules (temps par véhicule = temps total / `N`).
4. Point de départ non assimilé à un dépôt réel (simplification, cf. §6).

### 3. Formulation mathématique

Le problème n'est pas un plus court chemin mais un **problème de couverture d'arcs** : c'est une variante du **problème du postier chinois** (couvrir toutes les rues à coût minimal en revenant au départ), et du **postier rural** lorsqu'on impose de traiter d'abord un sous-réseau prioritaire (Partie II).

On introduit une variable entière `x_ij ∈ ℕ` = nombre de passages de la déneigeuse sur l'arc `(i, j)`. Le programme linéaire en nombres entiers (PLNE) résolu est :

```
minimiser   Σ  c_ij · x_ij
          (i,j)∈A

sous :
  (couverture, double sens {i,j})   x_ij + x_ji ≥ 1
  (couverture, sens unique i→j)     x_ij ≥ 1
  (conservation du flot, ∀ v∈V)     Σ x_iv  =  Σ x_vj       (entrées = sorties)
                                   i:(i,v)    j:(v,j)
  (intégrité)                       x_ij ∈ ℕ
```

Les contraintes de couverture garantissent que chaque rue est déblayée ; la conservation du flot garantit que les arcs parcourus forment un circuit fermé eulérien (la déneigeuse repart d'où elle entre dans chaque sommet) ; l'objectif minimise le coût total. La solution `x` est un **multiensemble d'arcs**, transformé en tournée ordonnée et roulable par l'**algorithme de Hierholzer** (parcours eulérien). Quand les arcs parcourus forment plusieurs circuits disjoints (cas fréquent d'un réseau prioritaire dispersé), on concatène un circuit par composante.

### 4. Méthode retenue

Le PLNE est résolu **exactement** par OR-Tools (back-end **CP-SAT**), qui atteint l'optimum bien plus vite que le simplexe entier classique (CBC) sur les grands secteurs. Une limite de temps borne la preuve d'optimalité sur RDP-PAT (le plus gros secteur) et renvoie alors la meilleure solution trouvée. Le solveur est **générique** : la même fonction traite les quatre secteurs, seules les données changent.

Pour les scénarios de priorisation, la résolution se fait **en deux phases** (logique du postier rural) : *phase 1* — couvrir le réseau prioritaire ; *phase 2* — couvrir le reste du réseau. La somme des deux donne la tournée complète, le réseau prioritaire étant dégagé en premier.

### 5. Indicateurs génériques

Pour comparer objectivement toute tournée, le projet calcule :

- **coût total journalier** ($), via le modèle tarifaire imposé ;
- **distance totale parcourue** (km) et **temps total** (h) ;
- **part à vide** : fraction des kilomètres parcourus au-delà de la longueur utile du réseau (repositionnements, re-passages) ;
- **nombre minimal de véhicules** pour terminer en ≤ 8 h : `N = ⌈temps_total / 8⌉`.

Une **ligne de base** (baseline : postier chinois uniforme, sans priorisation) sert de référence pour mesurer le surcoût de chaque scénario.

### 6. Limites du modèle

- **Dépendance aux données OSM** : la qualité du résultat dépend de l'exhaustivité de la cartographie (tags `highway`, POI, arrêts de bus).
- **Réduction à la plus grande CFC** : améliore la faisabilité mais peut exclure quelques rues marginales.
- **Vitesse constante** (10 km/h) : ignore le trafic, la pente et l'épaisseur de neige réelle.
- **Flotte idéalement répartie** : suppose un partage parfait du travail entre véhicules.
- **Point de départ simplifié** : pas de dépôt réel ni de coûts de trajet dépôt↔secteur.
- **Priorisation géométrique** : les scénarios reposent sur des seuils de distance fixes (150 m, 100 m), une approximation de l'accessibilité réelle.

---

## Partie II — Définition des trois scénarios de priorisation

Le déneigement de Montréal coûte de l'ordre de **200 millions de dollars** par hiver et les budgets sont régulièrement dépassés [For23][Vé20], dans un contexte de hausse continue des coûts [Lef19] et d'une logistique massive (≈ 300 000 voyages de camions par saison) [New18]. Dans ces conditions, *l'ordre* dans lequel on dégage le réseau a un impact social fort à budget quasi constant. Chaque scénario définit un **réseau prioritaire** (tier 1) dégagé en premier.

### Scénario A — Réseau artériel

**Définition.** Tier 1 = les grandes voies structurantes (tags OSM `highway` : *motorway, trunk, primary, secondary, tertiary* et leurs bretelles).

**Argumentaire sourcé.** C'est la politique effectivement appliquée par la Ville de Montréal, qui déneige et déglace en priorité le réseau artériel avant les rues locales [dM][Low25]. Dégager d'abord les axes maximise le débit de circulation rétabli par kilomètre déblayé.

**Bénéfices attendus & cibles.** Rétablissement rapide de la mobilité générale : automobilistes, **transport collectif** (les bus circulent sur les artères), services d'urgence et **logistique de livraison**. Cible large : l'ensemble des usagers du secteur et l'activité économique.

**Risques.** Les rues résidentielles sont traitées en dernier : inégalité d'accès « porte-à-porte », gêne pour les riverains et les piétons des quartiers calmes tant que la phase 2 n'est pas terminée.

**Indicateurs spécifiques.** Durée de dégagement du réseau prioritaire (T1) ; taux de couverture du réseau artériel après 1 h, 2 h, 4 h.

### Scénario B — Services essentiels

**Définition.** Tier 1 = les rues situées à ≤ 150 m d'un service essentiel (POI OSM : *hôpital, école, caserne de pompiers, clinique*).

**Argumentaire sourcé.** La continuité des services essentiels et de la sécurité est l'objectif premier d'un plan de déneigement municipal [dM]. Garantir l'accès aux soins et aux secours par temps de neige est un enjeu de santé publique et de sécurité, distinct de la seule fluidité du trafic.

**Bénéfices attendus & cibles.** Accès préservé aux **urgences hospitalières**, aux **casernes de pompiers** (temps d'intervention) et aux **écoles**. Cibles prioritaires : populations vulnérables, patients, enfants, services d'urgence.

**Risques.** Réseau prioritaire dispersé en petits îlots autour des POI → davantage de trajets à vide entre ces îlots. Pertinence dépendante de la complétude des POI dans OSM.

**Indicateurs spécifiques.** T1 ; couverture des abords de services essentiels à 1 h / 2 h / 4 h ; étendue du réseau prioritaire (km, % du réseau).

### Scénario C — Transport collectif

**Définition.** Tier 1 = les rues à ≤ 100 m d'un arrêt de bus (`highway=bus_stop`, mieux renseigné dans OSM que les relations de lignes à l'échelle d'un arrondissement).

**Argumentaire sourcé.** Le déneigement conditionne directement la fiabilité du réseau de bus, sur lequel Montréal s'appuie fortement l'hiver [dM][Low25]. Prioriser les abords des arrêts vise l'**équité de mobilité** envers les usagers dépendants du transport collectif.

**Bénéfices attendus & cibles.** Accès et sécurité aux arrêts pour les usagers sans voiture : **personnes âgées, étudiants, ménages à faible revenu**. Régularité du service de bus améliorée.

**Risques.** Dans les arrondissements denses, les arrêts maillent presque tout le réseau : le tier 1 devient très étendu (jusqu'à > 90 % des rues), ce qui **dilue** la priorisation et la rapproche d'une tournée uniforme, allongeant fortement T1.

**Indicateurs spécifiques.** T1 ; couverture des abords d'arrêts à 1 h / 2 h / 4 h ; part du réseau classée prioritaire.

---

## Partie III — Analyse des résultats

### 1. Indicateurs génériques (4 secteurs)

| Secteur | Scénario | Coût ($) | Distance (km) | Temps (h) | Part à vide | Véhic. (≤8 h) |
|---|---|---:|---:|---:|---:|---:|
| **Outremont** | Baseline | 564,14 | 53,0 | 5,30 | 18,7 % | 1 |
| | Artériel | 571,76 | 59,3 | 5,93 | 27,4 % | 1 |
| | Services | 571,40 | 59,0 | 5,90 | 27,0 % | 1 |
| | Transport | 571,65 | 59,2 | 5,92 | 27,2 % | 1 |
| **Verdun** | Baseline | 1 100,69 | 83,2 | 8,32 | 12,8 % | 2 |
| | Artériel | 1 107,64 | 89,0 | 8,90 | 18,4 % | 2 |
| | Services | 1 113,59 | 93,9 | 9,39 | 22,7 % | 2 |
| | Transport | 1 106,38 | 87,9 | 8,79 | 17,4 % | 2 |
| **Anjou** | Baseline | 1 737,55 | 196,3 | 19,63 | 26,3 % | 3 |
| | Artériel | 1 756,17 | 211,7 | 21,17 | 31,7 % | 3 |
| | Services | 1 754,31 | 210,2 | 21,02 | 31,2 % | 3 |
| | Transport | 1 783,60 | 234,4 | 23,44 | 38,3 % | 3 |
| **RDP-PAT** | Baseline | 4 155,96 | 542,1 | 54,21 | 23,7 % | 7 |
| | Artériel | 4 678,74 | 560,9 | 56,09 | 26,3 % | 8 |
| | Services | 4 681,89 | 563,5 | 56,36 | 26,6 % | 8 |
| | Transport | 4 724,21 | 598,5 | 59,85 | 30,9 % | 8 |

**Lecture.** La priorisation a un **coût marginal faible** tant qu'elle ne change pas la taille de flotte : sur Outremont, Verdun et Anjou le surcoût reste sous **+3 %** par rapport à la baseline (Outremont : +1,3 % au plus). Le saut de coût de RDP-PAT (+12,6 % en artériel, +13,7 % en transport) s'explique par un **effet de seuil de flotte** : la priorisation porte le temps total de 54,2 h à plus de 56 h, franchissant `7×8 = 56 h` et imposant un **8ᵉ véhicule** (+500 $ de coût fixe à lui seul). La part à vide augmente systématiquement avec la priorisation : c'est le prix du séquencement (repasser le réseau prioritaire avant le reste génère des repositionnements).

### 2. Indicateurs spécifiques de priorisation

`T1` = durée de la phase 1 (dégagement du réseau prioritaire, un véhicule). Couverture = part du réseau prioritaire dégagée après *t* heures de déblaiement.

| Secteur | Scénario | Réseau prio. (km) | % du réseau | T1 (h) | Couv. 1 h | Couv. 2 h | Couv. 4 h |
|---|---|---:|---:|---:|---:|---:|---:|
| **Outremont** | Artériel | 7,2 | 16,7 % | 1,18 | 88,6 % | 99,9 % | 99,9 % |
| | Services | 18,9 | 43,8 % | 2,44 | 39,9 % | 84,7 % | 100 % |
| | Transport | 27,5 | 63,8 % | 3,62 | 28,3 % | 55,0 % | 100 % |
| **Verdun** | Artériel | 27,3 | 37,6 % | 3,31 | 31,5 % | 60,5 % | 100 % |
| | Services | 30,6 | 42,2 % | 3,85 | 26,6 % | 53,7 % | 100 % |
| | Transport | 67,9 | 93,5 % | 7,86 | 12,1 % | 23,8 % | 49,7 % |
| **Anjou** | Artériel | 69,1 | 47,8 % | 10,77 | 12,2 % | 23,0 % | 46,0 % |
| | Services | 19,3 | 13,3 % | 3,21 | 32,5 % | 60,7 % | 100 % |
| | Transport | 99,4 | 68,7 % | 14,32 | 8,4 % | 15,1 % | 30,3 % |
| **RDP-PAT** | Artériel | 138,8 | 33,6 % | 19,29 | 6,1 % | 12,3 % | 26,8 % |
| | Services | 52,9 | 12,8 % | 7,66 | 11,9 % | 25,4 % | 53,7 % |
| | Transport | 234,5 | 56,7 % | 33,54 | 3,3 % | 6,7 % | 13,3 % |

**Lecture.** L'efficacité d'un scénario dépend surtout de la **taille de son réseau prioritaire** : plus il est compact, plus il est dégagé tôt. C'est pourquoi le **même scénario** n'a pas le même rendement selon le secteur :

- À **Outremont**, l'artériel est très compact (16,7 % du réseau) → 88,6 % dégagé en 1 h : priorisation très efficace.
- À **Anjou**, c'est l'inverse : le réseau artériel est étendu (47,8 %, T1 = 10,8 h) alors que les **services** y forment un petit noyau (13,3 %) couvert à 100 % en 4 h — le scénario services y est le plus pertinent.
- Le **transport collectif** classe une part énorme du réseau comme prioritaire (jusqu'à 93,5 % à Verdun) : la priorisation se dilue, T1 explose (33,5 h à RDP-PAT) et la couverture précoce s'effondre. Ce scénario n'est discriminant que là où le maillage de bus est lâche.

### 3. Projection des effets sur les habitants

- **Artériel** — Bénéfice rapide et large dans les secteurs compacts (Outremont) : mobilité générale, bus et secours rétablis en moins d'une heure sur les axes ; cohérent avec la pratique municipale [dM]. Contrepartie : les riverains des rues résidentielles attendent la fin de la tournée, et dans un secteur étendu comme Anjou le bénéfice « précoce » disparaît.
- **Services essentiels** — Effet le plus tangible pour les populations vulnérables : à Anjou et RDP-PAT, les abords d'hôpitaux, écoles et casernes sont intégralement dégagés en ~4 h, sécurisant l'accès aux soins et aux secours à coût quasi identique à la baseline (+1 % env.). C'est le meilleur rapport « bénéfice social / surcoût » dans les grands secteurs.
- **Transport collectif** — Vise l'équité de mobilité (usagers sans voiture), mais n'est réellement actionnable que dans les secteurs à arrêts espacés ; dans les zones denses, son coût (km, véhicules) et sa lenteur (T1) le rendent peu praticable tel quel.

### 4. Synthèse et recommandation

À budget quasi constant, **aucun scénario ne domine partout** : le choix optimal dépend de la morphologie du secteur. La recommandation opérationnelle est **hybride** :

1. **artériel** dans les arrondissements compacts à fort trafic (type Outremont) pour rétablir vite la mobilité ;
2. **services essentiels** dans les grands arrondissements étalés (Anjou, RDP-PAT), meilleur compromis bénéfice social / surcoût ;
3. réserver le **transport collectif** aux secteurs où le maillage de bus est suffisamment lâche pour rester discriminant.

Surtout, l'analyse révèle un **levier économique de premier ordre** : maintenir le temps total *sous le prochain seuil de flotte* (multiple de 8 h) évite un coût fixe de 500 $ par véhicule supplémentaire — un arbitrage qui pèse plus lourd, sur les grands secteurs, que le choix du scénario lui-même.

---

### Références

- **[dM]** Ville de Montréal. *Tout savoir sur le déneigement dans l'arrondissement* — Opération déneigement.
- **[For23]** Marco Fortier. *Une facture de près de 200 millions cet hiver*, novembre 2023, *La Presse*.
- **[Lef19]** Sarah-Maude Lefebvre. *Les prix du déneigement explosent partout au Québec*, décembre 2019, *Journal de Montréal*.
- **[Low25]** Morgan Lowrie. *Comment ça marche, le déneigement et le déglaçage à Montréal ?*, décembre 2025, *Le Devoir*.
- **[New18]** CBC News. *How Montreal takes 300,000 truckloads of snow off the street every winter*, février 2018.
- **[Vé20]** Henri Ouellette Vézina. *Déneigement : « on craint toujours de dépasser le budget »*, janvier 2020, *Métro*.
