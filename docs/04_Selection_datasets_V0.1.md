# Sélection initiale des datasets

| Champ | Valeur |
|---|---|
| Référence | DOC-04 |
| Version | V0.1 |
| Date de revue | 18 août 2026 |
| Statut | Préliminaire |
| Usage | Benchmark FAST-LIO2 / Point-LIO / LIO-SAM, puis fusion et perception |

## 1. Décision synthétique

La campagne ne reposera pas sur un seul dataset. Le lot initial doit couvrir quatre fonctions différentes :

1. une référence LIO reconnue et bien documentée ;
2. un environnement naturel dense avec une vérité terrain précise ;
3. un vrai vignoble avec LiDAR, IMU et RTK ;
4. une comparaison saisonnière dans le même vignoble.

### Lot initial retenu

| Ordre | Dataset / séquence | Rôle | État |
|---:|---|---|---|
| 1 | BotanicGarden `1006-03` en version LIO | test de fumée en environnement naturel | retenu, accès public |
| 2 | Newer College `01_short_experiment` | référence LIO/SLAM et validation de l'évaluateur | retenu, formulaire d'accès |
| 3 | ARD-VO, une séquence « vineyard » à choisir après inspection du catalogue | représentativité viticole + RTK | retenu sous réserve de licence et métadonnées |
| 4 | BLT, une session de début de saison et une session dense | changement saisonnier, boucles et végétation | retenu, formulaire d'accès |

`TEMPO-VINE` devient le candidat prioritaire dès qu'un lien de téléchargement officiel et une licence exploitable sont disponibles.

## 2. Critères de sélection

| Critère | Importance | Justification |
|---|---:|---|
| Vignoble et végétation réelle | critique | domaine final du projet |
| LiDAR 3D + IMU bruts et synchronisés | critique | nécessaire à FAST-LIO2, Point-LIO et LIO-SAM |
| Vérité terrain exploitable | critique | calcul objectif ATE/RPE |
| Calibration et repères documentés | élevée | éviter un classement biaisé |
| Format ROS/rosbag/MCAP | élevée | intégration reproductible |
| Taille et accès à une séquence isolée | élevée | démarrage rapide et stockage maîtrisé |
| Similarité avec Airy/Mid-360 | moyenne/élevée | anticiper les futurs capteurs |
| Licence compatible avec notre usage | critique | projet potentiellement commercial |
| Caméras et annotations | moyenne | préparation de la fusion/perception |

Une licence absente, ambiguë ou limitée au non-commercial n'empêche pas une étude technique interne préliminaire, mais interdit de considérer le dataset comme une base définitive sans clarification.

## 3. Dataset n°1 — BotanicGarden

### Pourquoi le retenir

- jardin botanique de plus de 48 000 m², riche en végétation et structures naturelles ;
- Velodyne VLP-16, Livox AVIA, IMU Xsens et IMU Livox ;
- synchronisation matérielle ;
- trajectoires et carte de référence issues d'un relevé Leica ;
- fichiers rosbag, poses au format TUM et configurations pour FAST-LIO2 ;
- variantes LIO sans images permettant un premier téléchargement raisonnable.

### Séquence de départ

`1006-03`, LIO rosbag, annoncée autour de 5,9 Go. Elle permet de valider la chaîne `dataset -> adaptateur -> algorithme -> trajectoire -> evo` avant de télécharger les campagnes plus lourdes.

### Limites

- robot terrestre et non drone ;
- pas un vignoble ;
- Livox AVIA plutôt que Mid-360 ;
- données annoncées pour usage académique : conditions commerciales **à valider**.

Source officielle : [BotanicGarden](https://github.com/robot-pesg/BotanicGarden).

## 4. Dataset n°2 — Newer College

### Pourquoi le retenir

- benchmark LIO/vision très utilisé et documenté ;
- Ouster OS-1 64 + IMU et caméra stéréo-inertielle ;
- zones bâties, espaces ouverts et végétation ;
- poses 6 DoF centimétriques obtenues par recalage sur une carte de relevé ;
- séquences avec mouvement rapide, secousses et variations de lumière.

### Séquence de départ

`01_short_experiment` contient plusieurs boucles dans les cours et le parc. Malgré son nom, elle dure environ 1 530 s ; un extrait reproductible de 60 à 120 s sera généré localement pour les tests de fumée, tout en conservant le fichier source intact.

### Limites

- environnement non viticole ;
- acquisition portée à la main ;
- licence CC BY-NC-SA 4.0, usage commercial soumis à accord.

Sources officielles : [présentation et capteurs](https://ori-drs.github.io/newer-college-dataset/), [téléchargement et licence](https://ori-drs.github.io/newer-college-dataset/download/).

## 5. Dataset n°3 — ARD-VO

### Pourquoi le retenir

- acquisitions dans des vignobles et oliveraies réels ;
- 11 sessions et environ 28,8 km annoncés ;
- LiDAR Velodyne, IMU, GPS-RTK, caméras stéréo et caméra multispectrale ;
- conçu pour comparer SLAM, odométrie visuelle, LiDAR et inertiel ;
- pertinent ultérieurement pour la perception et les cartes de prescription.

### Sélection à faire avant téléchargement

Choisir une seule séquence de vignoble possédant simultanément :

- nuage LiDAR brut ;
- IMU synchronisée ;
- trajectoire RTK exploitable comme référence ;
- calibration et timestamps documentés ;
- durée raisonnable pour un premier essai.

### Limites

- la page publique ne rend pas immédiatement visibles la taille et la licence de chaque archive ;
- la licence doit être vérifiée avant conservation dans le lot officiel ;
- géométrie et dynamique de robot terrestre.

Sources officielles : [page de téléchargement ISARLab](https://isar.unipg.it/datasets/), [article ARD-VO](https://onlinelibrary.wiley.com/doi/10.1002/rob.22179).

## 6. Dataset n°4 — BACCHUS Long-Term (BLT)

### Pourquoi le retenir

- vrai vignoble palissé ;
- Ouster OS-1 3D, IMU, caméras RGB-D et RTK-GNSS ;
- même parcours d'environ 500 m répété pendant la saison ;
- boucles, passages dans les deux sens et végétation de densité variable ;
- rosbags par session ;
- très pertinent pour la dérive longitudinale et la robustesse aux changements de feuillage.

### Paire de départ

- une session de mars ou début avril, avec structure et poteaux visibles ;
- une session de juin, avec végétation dense et occultations.

Cette paire mesure directement la robustesse à l'évolution de la végétation sans télécharger toutes les campagnes.

### Limites

- accès après formulaire nominatif ;
- conditions de licence et taille exacte des rosbags **à valider** ;
- trajectoire terrestre à environ 0,6 m/s, moins dynamique qu'un drone.

Source officielle : [BACCHUS Long-Term Dataset, University of Lincoln](https://lcas.lincoln.ac.uk/wp/research/data-sets-software/blt/).

## 7. Priorité future — TEMPO-VINE

TEMPO-VINE est techniquement le dataset le plus proche de notre besoin :

- vignes en palissage classique et en pergola ;
- campagnes de plusieurs saisons et rangs dépassant 100 m ;
- Velodyne VLP-16 et Livox Mid-360 ;
- caméra RGB-D, AHRS/IMU, odométrie et RTK ;
- données ROS compatibles, trajectoires de référence, répétitions et boucles ;
- format annoncé `bag.mcap.zstd` avec `metadata.yaml` et `GT_traj.csv`.

Le Livox Mid-360 est directement lié à notre shortlist matérielle. Cependant, l'article disponible indique que le dataset, les outils et les résultats seront publiés sur une page dédiée après acceptation ; aucune page officielle de téléchargement exploitable n'a été identifiée lors de la revue du 18 août 2026.

Décision : conserver `TEMPO-VINE` avec l'état `pending_release` et vérifier périodiquement sa disponibilité, sans bloquer le banc initial.

Source primaire : [article TEMPO-VINE](https://arxiv.org/abs/2512.04772).

## 8. Datasets différés

### M2DGR

Très riche en LiDAR, IMU, caméras, GNSS et RTK, avec 36 séquences et environ 1 To. Il sera utile pour la fusion GNSS/LIO, mais son environnement urbain et son volume le rendent peu adapté au premier incrément. Une seule séquence extérieure sera choisie plus tard.

Source officielle : [M2DGR](https://github.com/SJTU-ViSYS/M2DGR).

### Hilti SLAM

Excellent pour le stress test LIO avec une vérité terrain très précise, mais les chantiers sont éloignés du domaine viticole. Il sera ajouté après stabilisation du banc, pas avant.

Source primaire : [The Hilti SLAM Challenge Dataset](https://arxiv.org/abs/2109.11316).

### FriûlBot

Dataset viticole récent et prometteur avec VLP-16, IMU, GNSS, odométrie et multispectral. Il reste en veille jusqu'à vérification complète des archives, de la vérité terrain et de la licence.

Source primaire : [publication FriûlBot](https://air.uniud.it/handle/11390/1322017).

### VineLiDAR

Très utile pour l'analyse de structure et les modèles 3D de vigne, mais il s'agit surtout de nuages UAV cartographiques et non d'un flux LiDAR+IMU destiné à comparer des algorithmes LIO en ligne. Il sera réservé à la perception/cartographie.

Source primaire : [VineLiDAR](https://research.wur.nl/en/publications/vinelidar-high-resolution-uav-lidar-vineyard-dataset-acquired-ove/).

## 9. Ordre d'intégration

```text
BotanicGarden 1006-03
    -> validation du pipeline et des métriques

Newer College 01_short_experiment
    -> comparaison de référence des trois LIO

ARD-VO vineyard (1 séquence)
    -> premier test réellement viticole + RTK

BLT mars/avril + juin
    -> test saisonnier et végétation dense

TEMPO-VINE dès disponibilité
    -> benchmark viticole principal avec Mid-360
```

## 10. Règles avant ajout au catalogue actif

Un dataset ne passe à l'état `ready` que si les éléments suivants sont archivés :

- URL officielle et référence scientifique ;
- licence ou conditions d'usage ;
- taille, checksum et nom exact de l'archive ;
- liste des topics/champs et fréquences ;
- calibration et arbre de repères ;
- définition du ground truth et de son repère ;
- script reproductible de préparation ;
- extrait de fumée et résultat de contrôle qualité.

## 11. Prochaine action

Commencer par BotanicGarden `1006-03` : télécharger seulement le rosbag LIO et les poses de référence, calculer leurs checksums, inspecter les topics, puis créer le premier adaptateur. Les formulaires Newer College et BLT pourront ensuite être remplis par le propriétaire du projet, car ils demandent un nom et une adresse électronique.
