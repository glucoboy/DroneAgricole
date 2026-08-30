# DOC-24 — T0.4 — Comparaison des résultats et fermeture de la porte T0

- Version : V0.1
- Date : 30 août 2026
- Statut : opérationnel préliminaire
- Références : DOC-17, DOC-20, DOC-21, DOC-22, DOC-23, ADR-0005

## 1. Objectif

T0.4 termine le socle transversal du tableau de bord. Il permet de sélectionner plusieurs résultats historiques, de vérifier qu'ils sont directement comparables, puis de :

- comparer leurs métriques, paramètres, runners et contrats de résultat ;
- désigner les meilleures valeurs uniquement lorsque le sens de comparaison est défini ;
- superposer les trajectoires et courbes archivées sans relancer les algorithmes ;
- afficher ou exporter un rapport Markdown autonome ;
- reproduire depuis l'historique la comparaison finale FAST-LIO2 / Point-LIO / LIO-SAM.

Aucun résultat historique n'est modifié et aucune simulation n'est lancée par ces actions.

## 2. Règles de compatibilité

Une demande contient de deux à quatre identifiants publics uniques. La comparaison directe est acceptée lorsque tous les résultats possèdent :

- l'état terminal `completed` ;
- le même domaine ;
- le même identifiant de simulation ;
- le même `comparison_group` non vide ;
- au moins une métrique commune dont l'unité et le sens sont identiques.

Le domaine `localization` impose en plus le même dataset et la même séquence. Le domaine `flight_simulation` impose le même scénario. Une différence produit une liste de motifs lisibles et interdit la superposition.

La matrice des métriques présente l'union des métriques archivées. Une ligne n'est classable que si elle est disponible pour tous les résultats avec une unité et une direction cohérentes. Les égalités sont conservées : plusieurs exécutions peuvent donc recevoir la marque de meilleure valeur.

La disponibilité des artefacts de rejeu est contrôlée séparément. Une comparaison de métriques peut rester informative même si une trajectoire n'est pas archivée, mais le bouton de superposition reste alors désactivé.

## 3. Service et API

`software/visualization/result_comparison.py` centralise les règles, les matrices, le rejeu multiple et le rapport. Le serveur expose :

| Route | Rôle |
|---|---|
| `POST /api/comparisons/preview` | compatibilité, exécutions, métriques, paramètres et versions |
| `POST /api/comparisons/replay` | scène multi-trajectoires et courbes comparées |
| `POST /api/comparisons/report` | rapport Markdown téléchargeable |

Le rejeu lit les artefacts séquentiellement afin de borner la mémoire lors du chargement de plusieurs rosbags complets. `ResultRepository` conserve ensuite chaque scène hors ligne dans un cache mémoire lié à l'identifiant stable du résultat. Le cache est invalidé si le résultat disparaît de l'index et il est naturellement perdu au redémarrage du serveur.

## 4. Interface utilisateur

Chaque ligne de l'historique possède maintenant une action « Ajouter ». Le panneau « Comparer les essais archivés » fournit :

- une sélection persistante de deux à quatre résultats, indépendante des filtres courants ;
- un diagnostic de compatibilité avant le chargement des artefacts lourds ;
- une matrice des métriques avec meilleure valeur signalée ;
- une matrice de tous les paramètres, avec différences visibles ;
- une matrice des runners, sources, versions de contrat et codes de sortie ;
- les actions de superposition, d'aperçu du rapport et d'export `.md`.

En mode comparaison, la scène WebGL affiche une couleur distincte par exécution et conserve la vérité terrain en orange. La légende masque les entrées sans objet pour éviter toute ambiguïté. Le quatrième graphique superpose les courbes d'ATE cumulée ; les graphiques CPU, mémoire et temps réel renvoient vers la matrice, car leurs séries temporelles ne sont pas archivées.

Le bouton « Revenir au direct » restaure la scène et les courbes ROS 2 sans affecter la sélection ni l'état des runners.

## 5. Rapport

Le rapport Markdown contient :

- le diagnostic de compatibilité et ses motifs éventuels ;
- l'identité, la date, l'état et la source des exécutions ;
- la matrice des métriques et les meilleures valeurs ;
- la matrice des paramètres ;
- les runners, algorithmes déclarés et versions disponibles ;
- les limites d'interprétation.

Une valeur absente reste représentée par `—`. Le rapport ne transforme donc pas une information historique manquante en version supposée. L'aperçu et le fichier exporté sont produits depuis exactement la même représentation normalisée.

## 6. Reproduction de la comparaison LIO

La validation principale utilise les trois passages complets à `1×` et QoS harmonisée :

| Algorithme | Run | Identifiant public |
|---|---|---|
| FAST-LIO2 | `2a31bc7f` | `616a651e56ecf7cdabc2` |
| Point-LIO | `6feb6ccc` | `71b764de730415dfd7b2` |
| LIO-SAM | `7f42a0fa` | `f1f0987303f73f1d51c1` |

Ils partagent `localization`, `lio_benchmark`, `lio_trajectory_v1`, BotanicGarden et `1006-03-full`. Les dix métriques sont communes et classables. Le classement reconstruit depuis l'historique confirme :

- FAST-LIO2 pour l'ATE translation, la mémoire maximale et le facteur temps réel mesuré ;
- Point-LIO pour le CPU moyen ;
- LIO-SAM pour l'ATE orientation et les deux RPE ;
- une égalité sur les scans reçus, les odométries publiées et leur ratio.

Ce résultat reproduit la conclusion du DOC-17 sans relancer le dataset.

## 7. Validation

L'image qualifiée est :

| Image | Identifiant | Plateforme |
|---|---|---|
| `drone-agricole/lio-dashboard:0.5.0` | `sha256:3ee43082fbab6b80a4adccf651be6e2bb2819570f354e858ee30c835f2a768ff` | `linux/amd64` |

| Contrôle | Résultat |
|---|---|
| Tests T0.1 à T0.4 dans Docker | 51 réussis |
| Résultats indexés | 59, dont 52 LIO et 7 PX4 |
| Archives invalides | 0 |
| Comparaison LIO complète | 3 exécutions compatibles, 10 métriques communes |
| Matrices visibles | 10 métriques, 14 paramètres, 6 informations de version/source |
| Superposition 3D | 3 trajectoires de 1 440 points et une vérité terrain de 1 441 points |
| Courbes comparées | 3 courbes de 480 points |
| Première lecture séquentielle des trois rosbags | 26,89 s sur le poste de développement |
| Même lecture depuis le cache | 0,415 s |
| Stabilité après lecture complète | conteneur actif et API saine après temporisation |
| Rapport | HTTP 200, aperçu et export Markdown de 2 806 octets |
| Incompatibilité full/smoke | motif de séquence affiché, rejeu refusé avec HTTP 409 |
| Interface réelle servie par Docker | sélection, tableaux, aperçu, superposition, légende et retour au direct validés |

Les temps de lecture sont indicatifs et **À valider** sur une autre machine. La validation graphique a été réalisée sur les fichiers historiques réels ; aucune simulation LIO supplémentaire n'a été nécessaire.

## 8. Limites

- Chaque trajectoire LIO est alignée sur sa vérité terrain par la règle du rejeu T0.3 avant superposition. La vue est adaptée à la comparaison, pas à l'analyse d'une dérive dans un repère brut commun.
- Les archives historiques déclarent le runner et l'algorithme, mais pas toujours un commit logiciel dans leur manifeste normalisé. Le tableau et le rapport laissent alors la version absente.
- Les séries temporelles CPU, mémoire et facteur temps réel ne sont pas disponibles pour ces anciens résultats ; seules leurs valeurs finales sont comparées.
- Le cache accélère la consultation mais ne remplace jamais les artefacts présents sous `results/`.
- La qualification multiarchitecture et les performances sur Jetson restent **À valider**.

## 9. Porte T0

| Critère DOC-20 | Preuve | État |
|---|---|---|
| Lancer les trois LIO depuis le tableau de bord | T0.2 et régression FAST-LIO2 réelle | Satisfait |
| Lancer les deux scénarios PX4 depuis le tableau de bord | carré nominal et perte Offboard T0.2 | Satisfait |
| Retrouver, filtrer et recharger les résultats | T0.3, 59 archives | Satisfait |
| Comparer des résultats compatibles | T0.4, matrices et diagnostic | Satisfait |
| Superposer trajectoires et courbes | T0.4, trois LIO complets | Satisfait |
| Ouvrir et exporter un rapport | T0.4, aperçu et `.md` | Satisfait |
| Reproduire la comparaison LIO depuis l'historique | mêmes conclusions que DOC-17 | Satisfait |

La porte T0 est donc fermée au niveau **opérationnel préliminaire**. Cette fermeture valide le socle de simulation et de traçabilité ; elle ne qualifie ni le matériel, ni un algorithme pour le vol réel.

## 10. Suite recommandée

Le prochain lot est B1 : définir les contrats `SurveyMissionPackage`, `SurveyRunPackage` et `VineyardMapPackage`, puis auditer les flux caméra, timestamps et extrinsèques de BotanicGarden `1006-03`. Chaque future brique doit conserver les commandes, paramètres, résultats et comparaisons accessibles depuis le tableau de bord conformément à l'ADR-0005.
