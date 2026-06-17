# Tournées de déneigeuses — les fondements théoriques

*Projet : « Déneiger Montréal » (ERO1). Objectif : router les déneigeuses pour que chaque rue soit dégagée, au coût le plus bas possible.*

Ce document présente les fondements théoriques du projet, à destination de l'encadrement comme de l'équipe. Aucun prérequis en théorie des graphes n'est nécessaire : on construit tout à partir de zéro, avec de petits exemples concrets. Les sections se lisent dans l'ordre, chacune s'appuyant sur la précédente.

---

## 1. Le problème en une phrase

Une déneigeuse doit parcourir **chaque rue** d'un secteur au moins une fois et revenir à son point de départ, en gaspillant le moins de temps et d'argent possible.

C'est tout. Le reste de ce document vous explique comment on transforme cet objectif simple en quelque chose qu'un ordinateur peut résoudre exactement.

---

## 2. Transformer une carte en graphe

Une carte de rues est désordonnée. Pour raisonner dessus, on la réduit à deux types d'objets :

- **Sommets** — les intersections (là où les rues se croisent). Voyez-les comme des points.
- **Liens** — les tronçons de rue qui relient deux intersections. Voyez-les comme des traits entre les points.

Cette image épurée en points-et-traits s'appelle un **graphe**. Le problème de déneigement consiste à couvrir les **traits** (les rues), pas à visiter les **points** (les intersections). Gardez bien cette distinction en tête : on s'occupe de déneiger des routes, pas de se tenir à des carrefours.

Il existe deux sortes de liens, et la différence entre eux est tout l'enjeu :

- **Arête** — une rue à double sens. La déneigeuse peut la parcourir dans les deux directions.
- **Arc** — une rue à sens unique. La déneigeuse ne peut la parcourir que dans la direction légale.

> **Pourquoi c'est si important :** si on traite par erreur une rue à sens unique comme si elle était à double sens, l'ordinateur enverra volontiers la déneigeuse *à contresens*, car c'est souvent plus court. Le résultat serait moins cher sur le papier, mais **illégal et impossible** à conduire. Respecter le code de la route n'est pas une règle qu'on rajoute après coup : c'est inscrit dans le fait même qu'on appelle un lien « arête » ou « arc ».

Chaque lien porte aussi un **coût** — en gros, ce qu'il en coûte de parcourir ce tronçon (on le calcule à partir de la longueur de la rue et de la vitesse de la déneigeuse ; voir la fin du document).

---

## 3. Quand une déneigeuse peut-elle tout déblayer et rentrer en une seule boucle propre ?

Imaginez le cas idéal : la déneigeuse parcourt chaque rue **exactement une fois** et revient au départ, sans jamais repasser sur une rue. Un tel parcours s'appelle un **circuit eulérien** (du nom du mathématicien Euler).

Quand une telle boucle parfaite est-elle possible ? Il existe une règle d'une élégante simplicité.

### Pour une carte composée uniquement de rues à double sens

Regardez chaque intersection et comptez combien de rues la touchent. Ce nombre est le **degré** de l'intersection.

> **La règle :** une boucle parfaite existe si et seulement si **chaque intersection a un degré pair** (2, 4, 6 rues qui la touchent — jamais 3 ni 5).

**Pourquoi pair ?** Imaginez la déneigeuse traversant une intersection. Chaque fois qu'elle arrive par une rue, elle doit repartir par une autre. Arriver–repartir, arriver–repartir : les rues s'utilisent par paires. Si une intersection a un nombre impair de rues, à un moment la déneigeuse arrive et il ne reste plus de rue libre pour repartir — elle se retrouve bloquée. Un degré pair partout = la déneigeuse peut toujours continuer à circuler.

### Pour une carte composée uniquement de rues à sens unique

Maintenant, chaque intersection a des rues qui *entrent* et des rues qui *sortent*. On appelle ça le degré entrant et le degré sortant.

> **La règle :** une boucle parfaite existe si et seulement si à **chaque intersection, le degré entrant égale le degré sortant** — le nombre de façons d'entrer correspond au nombre de façons de sortir.

Même intuition : chaque arrivée doit être compensée par un départ. Si trois rues mènent à une intersection mais que seulement deux en sortent, la déneigeuse finira par arriver sans nulle part où aller légalement.

### Pour une vraie carte (mélange des deux)

Le vrai Montréal a *à la fois* des rues à double sens et à sens unique. Ce cas « mixte » est réellement difficile — il n'y a pas de règle simple, et c'est en général un problème difficile à calculer.

**L'astuce qui nous sauve :** on convertit chaque rue à double sens en **deux rues à sens unique pointant dans des directions opposées** (un arc dans chaque sens, même coût). Maintenant la carte *entière* n'est faite que de rues à sens unique, et on revient au cas traitable où il suffit que degré entrant = degré sortant partout.

Ce seul geste — dédoubler chaque arête en deux arcs opposés — est ce qui rend tout le projet résoluble. On l'a fait à la main sur de petits exemples ; les outils de données le font automatiquement sur les vraies cartes.

---

## 4. Et si une boucle parfaite est impossible ? (C'est presque toujours le cas.)

La plupart des vrais secteurs **n'auront pas** toutes leurs intersections équilibrées. Certaines seront « impaires » ou déséquilibrées. Faut-il abandonner ?

Non — cela signifie que la déneigeuse devra **parcourir certaines rues plus d'une fois**. Une intersection déséquilibrée ne *piège* pas la déneigeuse ; elle force juste un peu de retour en arrière. Ces parcours répétés s'appellent des **trajets à vide** (*deadhead trips*) — la déneigeuse repasse sur une rue déjà dégagée, uniquement pour se rééquilibrer.

La grande question devient : *quelles* rues faut-il répéter, et comment, pour que le **coût supplémentaire total soit le plus petit possible** ? Répéter une rue courte et bon marché, pas une rue longue et coûteuse.

C'est un problème d'optimisation — et c'est exactement ce qu'on confie à un ordinateur.

---

## 5. L'écrire comme un problème mathématique que l'ordinateur peut résoudre

On utilise la **programmation linéaire** (PL) : on énonce ce qu'on veut minimiser et les règles que la réponse doit respecter, et un solveur trouve la meilleure réponse possible. Voici notre problème sous cette forme.

### La variable de décision

Pour chaque arc à sens unique *(i → j)* du graphe, on introduit un nombre :

```
x[i,j] = nombre de fois où la déneigeuse parcourt l'arc i -> j
```

C'est un nombre entier (0, 1, 2, …), jamais fractionnaire — on ne peut pas parcourir une rue 1,5 fois. Surtout, il peut valoir **2 ou plus**, et c'est ainsi que le modèle exprime un trajet à vide.

### Règle 1 — Couvrir chaque rue

Chaque rue doit être dégagée au moins une fois.

- Rue à double sens entre *i* et *j* : `x[i,j] + x[j,i] >= 1` — la parcourir dans *l'un ou l'autre* sens compte comme l'avoir dégagée.
- Rue à sens unique *i → j* : `x[i,j] >= 1`.

> **Pourquoi « >= 1 » et non « = 1 » ?** Parce que « = 1 » interdirait de jamais répéter une rue — or répéter est exactement ce qu'il faut faire pour rééquilibrer les intersections impaires. « Au moins une fois » laisse la porte ouverte ; « exactement une fois » la claque et rend souvent le problème insoluble.

### Règle 2 — Le parcours doit former une boucle fermée

À chaque intersection, le nombre de fois où la déneigeuse entre doit égaler le nombre de fois où elle sort :

```
(somme des x sur les arcs entrant en v) = (somme des x sur les arcs sortant de v)    pour chaque intersection v
```

C'est la règle de **conservation du flot**, et ce n'est que la condition degré entrant = degré sortant de la section 3, écrite pour le solveur. C'est la contrainte la plus importante :

- C'est elle qui **force le rééquilibrage** : pour la satisfaire à une intersection impaire, le solveur est *contraint* de monter certains `x[i,j]` à 2.
- C'est elle qui **garantit que la boucle se referme** : équilibré partout signifie que la déneigeuse peut toujours circuler et revenir au départ.

### L'objectif — dépenser le moins possible

```
minimiser :  somme sur tous les arcs de  ( cost[i,j] × x[i,j] )
```

Tout parcourir comme requis, rééquilibrer là où c'est forcé, et parmi toutes les façons de le faire, choisir la moins chère.

### Le bénéfice

Le solveur fait le rééquilibrage **à notre place, de façon optimale**. On ne lui dit jamais *quelles* rues répéter — on énonce seulement les règles, et il trouve tout seul le jeu de trajets à vide le moins coûteux. C'est toute la raison d'utiliser la programmation linéaire plutôt que de rafistoler le parcours à la main.

> **Une subtilité à retenir :** le solveur ne « crée » jamais de nouvelle rue pour corriger un déséquilibre. Chaque rue a déjà sa variable `x[i,j]` dès le départ. Rééquilibrer signifie simplement que le solveur met une variable existante à 2 au lieu de 1 — il décide de parcourir une rue existante une fois de plus. « Ajouter un trajet à vide » veut en réalité dire « augmenter un nombre qui était déjà là ».

---

## 6. De « combien de fois » à « dans quel ordre »

Le PL nous donne un décompte : *rue A→B une fois, rue E→D deux fois,* etc. Mais une déneigeuse ne peut rien faire d'un décompte — elle a besoin d'un **itinéraire pas à pas** : va ici, puis ici, puis ici, sans se téléporter.

Convertir le décompte en itinéraire ordonné revient à trouver le vrai circuit eulérien dans le graphe. La méthode standard est l'**algorithme de Hierholzer**, et l'idée est simple :

1. Partez de n'importe où et continuez simplement à parcourir des rues inutilisées jusqu'à revenir à votre point de départ. Comme chaque intersection est équilibrée (le PL l'a garanti), on peut *toujours* continuer jusqu'à ce que la boucle se referme — on ne peut jamais se retrouver bloqué en cours de route.
2. S'il reste des rues inutilisées, trouvez un point de la boucle actuelle qui a encore des rues inutilisées, et tracez une *deuxième* boucle à partir de là.
3. Recollez les boucles ensemble. Répétez jusqu'à ce que chaque rue soit utilisée.

Le résultat final est un seul grand parcours continu : une séquence propre d'intersections qui commence et se termine au dépôt — **exactement le format que vous chargeriez dans une déneigeuse.**

> **Pourquoi la déneigeuse ne peut-elle pas se retrouver coincée en cours de route ?** Grâce, encore une fois, à la conservation du flot. Chaque fois que le parcours entre dans une intersection, il a consommé une rue entrante — et l'équilibre garantit qu'il existe une rue sortante correspondante pour repartir. Le *seul* endroit où le parcours peut finir par manquer de coups possibles, c'est le point de départ, et c'est pourquoi il se referme toujours en boucle. Le PL prépare un graphe équilibré ; Hierholzer en récolte le parcours. Les deux étapes sont indissociables.

---

## 7. Le pipeline complet

En réunissant tout, voici le trajet depuis une vraie carte jusqu'à un itinéraire conduisible :

```
   Données de rues réelles (OpenStreetMap)
              |
              v
   Graphe  (intersections, arêtes double sens, arcs sens unique, coûts)
              |
              v
   Programme linéaire (OR-Tools)  -->  décompte : combien de fois chaque rue
              |
              v
   Algorithme de Hierholzer  -->  itinéraire ordonné que la déneigeuse suit
```

Le même pipeline tourne sans changement sur les quatre secteurs (Outremont, Verdun, Anjou, RDP-PAT). La *méthode* est générique ; seules les *données* changent d'un secteur à l'autre. Traiter un nouveau secteur ne demande donc aucune modification du code : il suffit de changer l'entrée.

---

## 8. D'où viennent les coûts

Le coût d'une rue n'est pas seulement sa longueur — il combine distance et temps, à partir des chiffres de l'énoncé :

- Coût kilométrique : **1,1 $/km**
- Coût horaire : **1,1 $/h** (8 premières heures)
- Vitesse moyenne : **10 km/h**

Pour un tronçon de longueur *L* (en km), parcouru à 10 km/h :

```
temps  = L / 10   heures
coût   = 1,1 × L  +  1,1 × (L / 10)   dollars
```

La seule donnée géométrique dont on a besoin sur la carte est donc la **longueur** de chaque rue. Le coût fixe journalier (500 $/jour) et le tarif majoré au-delà de 8 h (1,3 $/h) s'appliquent à toute la journée de travail, pas à chaque rue : on les traite au niveau du scénario plutôt qu'à l'intérieur du graphe.

---

## 9. Limites à assumer honnêtement

À énoncer clairement (et à mentionner dans le rapport) :

- **La taille.** Un arrondissement entier compte des centaines d'intersections et environ un millier d'arcs. Le PL passe d'une poignée de variables à plusieurs milliers. Il reste résoluble, mais le solveur ralentit — il vaut la peine de chronométrer différents backends de solveur sur les vraies données.
- **La connexité.** Hierholzer suppose que toutes les rues forment un seul bloc connecté. Le PL garantit l'*équilibre* mais pas la *connexité*. Si les rues d'un secteur arrivaient en deux morceaux séparés, le parcours ne pourrait pas les relier. Sur de vraies données urbaines c'est rare (et les outils de données peuvent ne garder que le plus grand morceau connecté), mais c'est une vraie hypothèse du modèle.
- **Une seule déneigeuse.** Le modèle de base route un seul véhicule. Répartir un grand secteur entre plusieurs déneigeuses est une extension naturelle (une variante « k-postiers ») bâtie sur le même modèle.

---

## 10. Le résumé en une minute

L'essentiel à retenir :

- Une carte devient un **graphe** : des points (intersections) et des traits (rues), où les rues à double sens sont des **arêtes** et les rues à sens unique des **arcs**.
- Une déneigeuse ne peut tout dégager en une boucle parfaite que si chaque intersection est **équilibrée** (degré pair, ou entrant = sortant).
- Les vraies cartes ne sont pas équilibrées, alors la déneigeuse doit **répéter certaines rues** — et on veut le jeu de répétitions le moins cher.
- Un **programme linéaire** énonce les règles (couvrir chaque rue ; garder chaque intersection équilibrée ; minimiser le coût) et le solveur trouve les répétitions optimales automatiquement.
- L'**algorithme de Hierholzer** transforme le décompte du solveur en un **itinéraire ordonné** qu'une déneigeuse peut réellement conduire.
- Traiter les rues à sens unique comme des arcs (jamais comme des arêtes) est ce qui garde le parcours **légal**.

## 7bis. Priorisation : dégager le réseau structurant d'abord

Toutes les rues ne se valent pas. On classe chaque rue en « prioritaire » (tier 1)
ou non, selon le scénario, puis on route en **deux phases** :

1. **Phase 1** — couvrir tout le réseau prioritaire au moindre coût, en s'autorisant
   à traverser les autres rues comme simples connecteurs (c'est le **Problème du
   Postier Rural** : couvrir un sous-ensemble d'arêtes). L'indicateur clé **T₁** est
   la durée de cette phase = temps avant que 100 % du réseau prioritaire soit dégagé.
2. **Phase 2** — couvrir le reste, en réutilisant les rues prioritaires comme connecteurs.

Trois scénarios définissent « prioritaire » différemment : **réseau artériel** (grandes
voies, tag OSM `highway`), **accès aux services essentiels** (rues proches des hôpitaux,
écoles, casernes) et **transport collectif** (rues proches des arrêts de bus). Les deux
derniers reposent sur une proximité géométrique à des points d'intérêt OSM, avec un seuil
de distance réglable (hypothèse à assumer).

## 8bis. Coût en fonction du nombre de véhicules

Pour `N` véhicules se partageant idéalement le travail (temps/véhicule = T/N) :

    coût(N) = 500·N + 1,1·L + 1,1·min(T, 8N) + 1,3·max(T − 8N, 0)

où `L` est la distance totale (km) et `T = L/10` le temps total (h). La flotte
optimale est le plus petit `N` éliminant les heures supplémentaires (`T/N ≤ 8`).
