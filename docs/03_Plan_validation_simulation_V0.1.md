# Plan de validation et de simulation

| Champ | Valeur |
|---|---|
| Référence | DOC-03 |
| Version | V0.1 |
| Date | 18 août 2026 |
| Statut | Préliminaire |

## 1. Objectif

Construire un banc reproductible permettant de comparer les algorithmes, versions, paramètres, calculateurs et capteurs avant les achats ou vols risqués. La campagne relie chaque scénario aux exigences, métriques, configurations et résultats.

## 2. Niveaux de validation

```text
Tests unitaires
      |
      v
Rejeu de datasets / rosbags
      |
      v
Simulation capteurs + PX4 SITL
      |
      v
HITL et bancs actionneurs
      |
      v
Vol sans bras
      |
      v
Vol avec bras sans liquide
      |
      v
Eau + traceur
      |
      v
Essais autorisés en conditions réelles
```

Un niveau ne doit pas être utilisé pour compenser l'absence de validation du niveau précédent.

## 3. Jeu virtuel `VINEYARD_BENCH_V01`

| ID | Scénario | But principal | Variantes minimales |
|---|---|---|---|
| VB01 | `01_flat_regular` | référence simple et répétable | vitesses 0,5/1/2 m/s |
| VB02 | `02_curved_rows` | rangs non rectilignes et planification | courbures faible/forte |
| VB03 | `03_steep_slope` | suivi de relief et dynamique | pentes 15/25/35° |
| VB04 | `04_terrace` | ruptures de niveau et transitions | mur, talus, bout de terrasse |
| VB05 | `05_dense_vegetation` | LIO/perception avec feuillage abondant | statique et mouvement simulé |
| VB06 | `06_posts` | détection, association et évitement des poteaux | bois/métal, occultation |
| VB07 | `07_wires` | danger des fils et politique conservatrice | diamètres/hauteurs/contrastes |
| VB08 | `08_rtk_loss` | continuité de localisation et reprise | coupure courte/longue, biais |
| VB09 | `09_fast_motion` | latence, deskew et dynamique | accélérations et rotations |
| VB10 | `10_low_geometry` | robustesse en géométrie pauvre/répétitive | rang homogène, peu de repères |

Chaque scénario doit disposer :

```text
scenario.yaml
world/
mission/
ground_truth/
expected_events.yaml
acceptance.yaml
README.md
```

## 4. Datasets publics de départ

| Dataset | Utilisation | Limite pour le projet |
|---|---|---|
| Newer College | premier benchmark LIO, extérieur et végétation | pas une vigne, pas de RTK principal |
| M2DGR | fusion multi-capteurs et GNSS/RTK | volume très important, environnement différent |
| Hilti SLAM | robustesse pure en conditions difficiles | faible représentativité viticole |
| ARD-VO / FriûlBot / TreeScope / SCORPION / BLT | pistes agricoles à qualifier | formats, accès et vérités terrain variables |

Les datasets agricoles seront ajoutés au manifeste seulement après vérification de leur licence, de leurs capteurs, de la calibration et de la vérité terrain.

## 5. Interface commune de rejeu

Le package `vineyard_dataset_adapter` doit convertir chaque source vers :

```text
/benchmark/lidar_points
/benchmark/imu
/benchmark/gnss
/benchmark/ground_truth
/benchmark/camera
/tf_static
```

Repères communs :

```text
map -> odom -> base_link -> lidar_link / imu_link / camera_link
```

L'adaptateur ne corrige pas silencieusement les données. Toute conversion d'unité, de timestamp, de repère ou de champ est déclarée dans un manifeste.

## 6. Algorithmes de la première campagne

- FAST-LIO2 ;
- Point-LIO ;
- LIO-SAM.

Chaque implémentation est figée par commit, patchs et image Docker. Les sorties sont converties vers une interface unique :

```text
/benchmark/odom
/benchmark/path
/benchmark/map
/benchmark/diagnostics
```

## 7. Métriques LIO et SLAM

| Catégorie | Mesures |
|---|---|
| Précision | ATE, RPE translation/rotation, erreur finale |
| Robustesse | taux d'échec, resets, sauts, durée sans solution |
| Temps réel | latence médiane/P95/P99, fréquence, backlog |
| Ressources | CPU, GPU, RAM, VRAM, température, puissance |
| Carte | cohérence locale, doublons, erreur de fermeture de boucle |
| Intégration | temps de compilation, dépendances, stabilité ROS 2 |
| Reproductibilité | variance entre répétitions, hash de configuration |

Les métriques sont calculées sur une fenêtre commune et dans les mêmes repères. Les phases d'initialisation et segments exclus sont explicitement consignés.

## 8. Métriques perception

- précision, rappel, F1 et IoU par classe ;
- erreur de position/dimension 3D des poteaux ;
- taux de non-détection des fils, avec priorité de sûreté ;
- distance de détection utile et latence bout en bout ;
- stabilité temporelle des objets ;
- calibration de la confiance ;
- performances RTX puis Jetson/TensorRT.

## 9. Métriques navigation et traitement

- erreur de suivi latérale et verticale ;
- distance minimale au sol, à la végétation, aux poteaux et aux volumes de fils ;
- collisions et violations du corridor ;
- temps de réaction à un obstacle ou flux périmé ;
- taux de réussite des transitions de mission ;
- erreur de position du bras ;
- décalage buse/cible ;
- erreur de débit et de dose ;
- homogénéité verticale du dépôt et pertes au sol sur traceur ;
- volume traité hors zone autorisée : objectif zéro.

## 10. Dataset physique futur `VINEYARD_DATASET_V1`

```text
01_flat_regular
02_flat_irregular
03_slope_15deg
04_slope_25deg
05_slope_35deg
06_terrace
07_dense_foliage
08_sparse_foliage
09_windy
10_posts_and_wires
11_rtk_loss
12_fast_motion
13_hover
14_loop_closure
```

Flux à conserver :

- paquets ou points LiDAR bruts avec timestamps par point lorsque disponibles ;
- IMU du LiDAR et IMU PX4 ;
- GNSS/RTK brut, solution et indicateurs de qualité ;
- attitude, position, vitesse et états PX4 ;
- images brutes et informations caméra ;
- synchronisation, calibrations et transformations ;
- commande et état des actionneurs ;
- conditions de l'essai et vérité terrain disponible.

## 11. `benchmark_runner`

Entrée :

```yaml
campaign_id: example
dataset: newer_college_short
algorithm: fast_lio2
container_image: image@sha256:...
parameters: configs/fast_lio2/example.yaml
repetitions: 3
```

Sortie :

```text
results/<campaign>/<run>/
├── manifest.yaml
├── stdout.log
├── metrics.json
├── trajectory.tum
├── resource_usage.csv
├── plots/
└── report.html
```

Le runner doit échouer explicitement si un dataset, une calibration, une vérité terrain ou une image ne correspond pas au hash attendu.

## 12. Matrice minimale de campagne

| Axe | Valeurs initiales |
|---|---|
| Algorithme | FAST-LIO2, Point-LIO, LIO-SAM |
| Dataset réel | petit segment Newer College, puis M2DGR ciblé |
| Scénario virtuel | VB01 à VB10 |
| Architecture | PC `amd64`, puis Jetson `arm64` |
| Version | image Docker immuable |
| Répétitions | 3 nominales, davantage si forte variance |

La matrice complète n'est lancée qu'après un test court de fumée afin d'éviter de consommer du temps sur une configuration invalide.

## 13. Portes de validation

### GATE-01 — Infrastructure

- lancement Docker reproductible ;
- dataset et calibration identifiés ;
- rapports générés automatiquement ;
- même exécution possible sur une seconde machine.

### GATE-02 — Localisation

- aucun échec silencieux ;
- ATE/RPE produits ;
- perte RTK simulée gérée ;
- algorithmes classés avec justification.

### GATE-03 — SITL navigation

- mission complète sans collision sur VB01 à VB06 ;
- comportement conservatif sur VB07 ;
- reprise ou abandon maîtrisé sur VB08 ;
- limites dynamiques respectées sur VB09/VB10.

### GATE-04 — Bras et actionneurs sur banc

- états sûrs démontrés ;
- défauts capteurs/actionneurs injectés ;
- erreur temporelle et dose mesurées avec eau/traceur.

### GATE-05 — Vol progressif

- revue de risques et procédure d'essai approuvées ;
- géofence et arrêt d'urgence testés ;
- critères du niveau précédent satisfaits ;
- données complètes et incident rejouable.

## 14. Premier incrément recommandé

1. créer le format de manifeste ;
2. intégrer un court rosbag Newer College ;
3. lancer un seul candidat LIO dans Docker ;
4. produire ATE/RPE et ressources ;
5. ajouter les deux autres candidats ;
6. seulement ensuite créer VB01 sous Gazebo/PX4 SITL.

Cette séquence valide le banc avant de multiplier les mondes et scénarios.
