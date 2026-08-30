# Architecture logicielle et algorithmes

| Champ | Valeur |
|---|---|
| Référence | DOC-01 |
| Version | V0.2 |
| Date | 18 août 2026 |
| Statut | Préliminaire |

## 1. Principes d'architecture

1. **Autorité de vol séparée** : PX4 exécute les boucles d'attitude, la stabilisation, l'estimation primaire et les failsafes.
2. **Intelligence sur compagnon** : ROS 2 exécute perception, cartographie, navigation avancée, mission et traitement.
3. **Dégradation maîtrisée** : la perte d'une fonction ROS 2 ne doit pas provoquer une commande moteur non maîtrisée.
4. **Interfaces stables** : les algorithmes sont interchangeables derrière des topics/actions et formats communs.
5. **Reproductibilité** : acquisition, paramètres, version logicielle et résultats sont archivés ensemble.
6. **Mesure avant choix définitif** : les algorithmes et calculateurs sont sélectionnés par benchmark.

## 2. Vue système

```text
                         STATION SOL
                  QGroundControl personnalisé
                              |
                   MAVLink / télémétrie
                              |
          +-------------------+-------------------+
          |                                       |
  DRONE CARTOGRAPHE                       DRONE TRAITEMENT
          |                                       |
       PX4 FCU                                  PX4 FCU
          |                                       |
     interface ROS 2                         interface ROS 2
          |                                       |
     Jetson Orin                              Jetson Orin
          |                                       |
 LiDAR / RGB / RTK / IMU              LiDAR / RGB / RTK / IMU
          |                                       |
 carte sémantique 3D                 navigation + bras + dose
```

## 3. Chaîne du drone cartographe

```text
LiDAR + IMU + RTK + caméras
             |
             v
synchronisation, calibration et contrôle qualité
             |
      +------+------+
      |             |
      v             v
     LIO            VIO
      |             |
      +------+------+
             v
 fusion / SLAM / fermeture de boucle
             |
             v
 nuage 3D géoréférencé
             |
             v
 perception sémantique
             |
  +----------+----------+----------+
  |          |          |          |
terrain   poteaux     végétation  obstacles
  |          |          |          |
  +----------+----------+----------+
             v
 modèle de parcelle + graphe navigable
```

## 4. Chaîne du drone de traitement

```text
carte cartographe + mission
             |
             v
planification globale
             |
RTK + IMU + LIO/VIO + perception locale
             |
             v
recalage carte / réel
             |
             v
corridor 3D sûr : drone + bras
             |
      +------+------+
      |             |
suivi terrain   évitement obstacles
      |             |
      +------+------+
             v
trajectoire locale -> consignes PX4
             |
             v
association cible / pied
             |
             v
prédiction temporelle buse-cible
             |
      +------+------+------+
      |             |      |
commande bras   dose liquide  assistance d'air
```

## 5. Catalogue des algorithmes

### 5.1 Acquisition et localisation

| ID | Algorithme/fonction | Entrées | Sorties | KPI principal |
|---|---|---|---|---|
| SEN-01 | Synchronisation et validation capteurs | timestamps, PPS/PTP, flux capteurs | flux alignés, diagnostics | erreur temporelle, pertes |
| CAL-01 | Calibration intrinsèque/extrinsèque | LiDAR, caméra, IMU | transformations et incertitudes | erreur de reprojection |
| LOC-01 | Fusion GNSS RTK/IMU | GNSS, IMU, état PX4 | pose globale | erreur 3D, disponibilité |
| LOC-02 | LIO | nuage LiDAR, IMU | odométrie locale | ATE, RPE, latence |
| LOC-03 | VIO | images, IMU | odométrie visuelle | ATE, robustesse lumière |
| LOC-04 | Gestion de perte RTK | qualité GNSS, innovations | mode de localisation, alarme | détection, continuité |
| LOC-05 | Recalage carte/réel | carte, observations locales | transformation de recalage | erreur et convergence |

FAST-LIO2, Point-LIO et LIO-SAM sont les trois candidats LIO initiaux. Leur sélection dépendra de la précision, de la robustesse dans la végétation, du temps réel, de la consommation de ressources et de la maintenabilité ROS 2.

### 5.2 Cartographie et perception

| ID | Algorithme/fonction | But | KPI principal |
|---|---|---|---|
| SLAM-01 | SLAM et fermeture de boucle | carte cohérente sur mission longue | dérive, erreur de boucle |
| MAP-01 | Géoréférencement | aligner la carte locale dans le référentiel parcelle | erreur absolue |
| MAP-02 | Modèle de terrain | sol, pente, normales, ruptures | erreur d'altitude |
| MAP-03 | Construction du graphe | segments navigables et connectivité réelle | validité topologique |
| PER-01 | Segmentation sémantique | terrain, végétation, poteau, mur, talus, autre | IoU par classe |
| PER-02 | Détection de poteaux | obstacles et repères persistants | précision/rappel, erreur 3D |
| PER-03 | Détection/estimation des fils | danger et corridor interdit | taux de non-détection |
| PER-04 | Individualisation des pieds | entités de traitement | précision/rappel, association |
| PER-05 | Volume de végétation | hauteur, largeur, densité, volume | erreur vs référence |
| PER-06 | Détection d'obstacles | obstacles statiques/dynamiques | rappel, latence |
| PER-07 | Confiance cartographique | zones observées/incertaines | calibration de confiance |

La détection des fils combine autant que possible LiDAR, vision, géométrie connue de la carte et marges conservatrices. Elle ne doit pas être présentée comme garantie par le seul nuage LiDAR.

### 5.3 Navigation

| ID | Algorithme/fonction | But | KPI principal |
|---|---|---|---|
| NAV-01 | Planification globale | ordonner rangs, terrasses et transitions | distance, faisabilité |
| NAV-02 | Planification locale 3D | produire une trajectoire sans collision | marge minimale, temps calcul |
| NAV-03 | Suivi de trajectoire | convertir trajectoire en consignes PX4 | erreur de suivi |
| NAV-04 | Suivi/anticipation du terrain | maintenir altitude et attitude compatibles | erreur verticale |
| NAV-05 | Corridor drone + bras | enveloppe complète dans l'espace libre | violation de marge |
| NAV-06 | Gestion des bouts de rang | sortie, rétraction, demi-tour, reprise | taux de réussite |
| NAV-07 | Replanification | réagir à obstacle, écart carte/réel ou blocage | temps de réaction |

### 5.4 Traitement et bras

| ID | Algorithme/fonction | But | KPI principal |
|---|---|---|---|
| ARM-01 | Déploiement/rétraction | commander et confirmer la position du bras | temps, erreurs, blocage |
| ARM-02 | Surveillance enveloppe | intégrer position réelle du bras au corridor | cohérence et latence |
| TRT-01 | Association cible | relier observation, pied cartographié et côté traité | taux d'association |
| TRT-02 | Synchronisation temporelle | anticiper l'arrivée de la buse devant la cible | erreur longitudinale |
| TRT-03 | Calcul de dose | consigne selon vitesse, distance, végétation et prescription | erreur de dose |
| TRT-04 | Régulation débit/pression | suivre la consigne liquide | temps de réponse, erreur |
| AIR-01 | Assistance d'air | commander les modules d'air | débit/vitesse d'air |
| AIR-02 | Compensation vent/downwash | ajuster orientation et puissance | dépôt et dérive |
| TRT-05 | Carte de traitement | enregistrer zones, dose et qualité | complétude, traçabilité |

La synchronisation est explicitement temporelle :

```text
temps avant cible = distance projetée / vitesse relative
commande = temps avant cible - latence pompe/vanne - marge
```

Les retards sont identifiés sur banc et versionnés dans la configuration de l'actionneur.

### 5.5 Mission et sécurité

| ID | Algorithme/fonction | But | KPI principal |
|---|---|---|---|
| MIS-01 | Machine à états mission | orchestration explicite et testable | transitions valides |
| MIS-02 | Gestion d'énergie/produit | retour, reprise et fin de mission | prédiction restante |
| SAFE-01 | Superviseur de sécurité | surveiller préconditions et invariants | temps de réaction |
| SAFE-02 | Surveillance des flux | fraîcheur, fréquence, cohérence | défauts non détectés |
| SAFE-03 | Décision d'abandon | état sûr selon la panne | couverture des pannes |
| LOG-01 | Enregistrement | données brutes, événements, paramètres | complétude et rejeu |

## 6. Décomposition ROS 2 cible

```text
sensor_manager
calibration_manager
localization_manager
lio_adapter
semantic_perception
terrain_model
obstacle_tracker
map_builder
map_server_vineyard
route_planner
local_planner
trajectory_controller
treatment_targeter
spray_controller
airflow_controller
arm_controller
safety_supervisor
mission_manager
px4_bridge
logger_recorder
benchmark_runner
```

Les algorithmes lourds ne doivent pas imposer leur format natif aux autres composants. Des adaptateurs traduisent leurs topics vers les interfaces communes du projet.

## 7. Machine à états de traitement

```text
BOOT -> SELF_TEST -> READY -> TAKEOFF -> TRANSIT -> APPROACH
                                                     |
                                                     v
                                               DEPLOY_ARM
                                                     |
                                                     v
                                                TREATMENT
                                                /       \
                                               v         v
                                           ROW_END     ABORT
                                               \         /
                                                v       v
                                              RETRACT_ARM
                                                   |
                                      +------------+------------+
                                      |                         |
                                   NEXT_ROW                    RETURN
```

Chaque transition possède des gardes, un délai maximal et une réponse à l'échec. `ABORT` doit rester accessible depuis chaque état actif.

## 8. Répartition des technologies

| Domaine | Technologie privilégiée |
|---|---|
| Vol critique | PX4, C/C++ sur autopilote |
| Nœuds ROS 2 embarqués | C++17 ou ultérieur après qualification |
| Analyse, orchestration de benchmark | Python |
| Nuages 3D | PCL, Eigen et bibliothèques qualifiées |
| Vision | OpenCV, CUDA, TensorRT selon modèle |
| Visualisation | RViz2 et outils de rapport |
| Station sol | QGroundControl personnalisé |
| Transport ROS 2 | DDS qualifié ; Cyclone DDS comme candidat initial |
| Conteneurs | Docker, BuildKit, images multiarchitecture |

## 9. Déploiement

### 9.1 PC de développement

```text
Windows 11
└── WSL2
    └── Docker
        ├── environnement ROS 2
        ├── PX4 SITL / simulation
        ├── benchmark LIO
        ├── perception GPU RTX 5060 Ti
        └── analyse et rapports
```

### 9.2 Jetson

```text
JetPack / Linux for Tegra
├── pilotes et accès matériel
├── supervision système
└── NVIDIA Container Runtime
    ├── services ROS 2
    ├── perception / LIO
    └── mission / traitement
```

Les services très bas niveau nécessaires au démarrage, aux pilotes ou au watchdog peuvent rester sur l'hôte si cela augmente la robustesse.

## 10. Ordre de développement

1. Banc de rejeu LIO et interfaces de données communes.
2. PX4 SITL + ROS 2 avec mission et sécurité minimales.
3. Cartographie 3D et carte sémantique.
4. Navigation du drone de traitement sans bras.
5. Corridor complet et bras sans liquide.
6. Commande liquide sur banc avec eau/traceur.
7. Compensation vent/downwash et essais agronomiques autorisés.

## 11. Points à qualifier

- version ROS 2 définitive et qualité des forks LIO ;
- messages, actions, QoS et fréquences exactes ;
- support ARM64 des pilotes capteurs ;
- budget CPU/GPU/RAM et thermique ;
- calibration et synchronisation de tous les capteurs ;
- mécanismes de reprise après panne ;
- métriques de confiance utilisables par le superviseur.
