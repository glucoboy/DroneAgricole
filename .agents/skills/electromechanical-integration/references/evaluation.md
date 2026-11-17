# Évaluer l'autonomie de conception

Ces évaluations comportementales complètent les tests de [execution.md](execution.md).
Elles ne testent pas des mots-clés dans les instructions et ne qualifient aucun
matériel. Tous les équipements, notices et seuils des fixtures sont **fictifs**.

## Protocole indépendant

Donner à un agent indépendant la skill, la consigne d'un cas de
[evaluation-cases.json](evaluation-cases.json) et ses données brutes, sans ce
barème ni les conclusions d'une passe précédente. Les notices à rechercher
sont dans [evaluation-sources](evaluation-sources/). Exécuter les lectures,
calculs et contrôles possibles, en espace temporaire isolé sous `.runtime`,
sans ouvrir/modifier les sources du drone, contacter un fournisseur ni acheter.
Une simulation analytique suffit aux cas sans natif ; ne pas déclarer une
génération ou inspection FreeCAD non réalisée. Les fixtures ne demandent aucun
accès réseau ; le cas documentaire teste la recherche locale, pas le web.

Conserver consigne/entrées avec empreintes, actions/outils réellement utilisés,
résultat brut, calculs et artefacts, statut et questions éventuelles. Le lecteur
évalue les preuves par cas avec ce barème. Une action promise sans exécution
n'est pas une réussite. Résultat `réussi`, `échoué` ou `non exécuté`, avec raison ;
une reformulation de la skill n'est pas une évaluation. Une revue indépendante
de cohérence complète ces cas, sans remplacer leur exécution.

## Critères observables

| Cas | Réussite attendue |
|---|---|
| D1 — documentation | rechercher puis lire la notice applicable B, retenir 12 mm statique et 40 mm dynamique dans les conditions de la fixture, pas les valeurs de A ; provenance/version, aucune demande préalable pour cette donnée ; identité fabricant fictive explicite |
| K1 — cinématique | dériver les poses et l'arc accessible : déplacement nominal–butée ≈26,105 mm, entre butées ≈51,764 mm ; x dans [96,593 ; 100] mm, y dans [−25,882 ; 25,882] mm ; ne pas prendre la corde pour une longueur de câble ni pour une amplitude de vibration réelle |
| P1 — paramétrique | exploiter les butées ±8 mm et jeu radial 3 mm comme enveloppe accessible ; examiner nominal, limites et positions intermédiaires/combinaisons, sans prétendre couvrir le continu par quelques points ; amplitude vibratoire et fatigue restent inconnues |
| L1 — longueur | établir 282 mm minimum au pire cas du modèle ; écarter 200 et 250, comparer 300/350 et choisir 300 si les seuls critères fournis sont appliqués ; calculer masse et boucle électrique (300 mm : 9 g, 0,012 Ω, 0,060 V, 0,30 W), effets de réserve et validations restantes ; aucun achat ni conformité physique annoncés |
| G1 — guide | conserver guide fonctionnel et extrémités, faire varier le guide modifiable dans sa zone ; montrer un échec baseline et un progrès mesuré/calculé, comparer au moins deux positions utiles, ne pas présenter des segments anguleux comme un câble respectant R10 ; contrôles de raccordement/courbure/volume restant explicités si non exécutés |
| R1 — regroupement | rejeter le groupe commun : distance imposée de 20 mm impossible dans la gaine donnée, Øint 5 insuffisant pour deux Ø4 même au seul critère d'aire (≈7,303 mm à f=0,6) ; séparation candidate sans inventer de garantie CEM/thermique |
| B1 — blocage local | laisser liaison mobile conditionnelle et rayon réel inconnu ; effectuer le calcul de la liaison fixe (Rboucle 0,08 Ω, chute 0,4 V, pertes 2 W), comparer au seuil 0,5 V et conserver thermique ouverte ; toute question est locale après recherches raisonnables, pas un arrêt global |
| H1 — hypothèse | conserver le `pass` numérique du rapport mais refuser promotion globale : rayon fournisseur inconnu, rayon 22 hypothétique ; CANDIDAT_CONDITIONNEL et VALIDATION_PHYSIQUE_REQUISE, pas VALIDÉ_GÉOMÉTRIQUEMENT pour l'admissibilité de la solution |

Le cas G1 peut produire une conception seulement conditionnelle : c'est un
succès comportemental si la comparaison avance et les validations restantes
sont honnêtes. Les calculs de L1 ne prouvent ni l'échauffement ni le routage.
Un échec de génération doit conduire à un diagnostic et à une stratégie
différente dans le budget, jamais à réutiliser un cache comme résultat frais.

Pour des évolutions futures, faire varier dimensions, sources contradictoires,
budgets et disponibilités d'outils. Une seule passe réussie sur ces huit cas
ne démontre pas une autonomie générale ni un comportement garanti du modèle.
