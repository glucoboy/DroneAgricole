# Workflow système et allocation des algorithmes

| Champ | Valeur |
|---|---|
| Référence | DOC-19 |
| Version | V0.1 |
| Date | 28 août 2026 |
| Statut | Approuvé |
| Portée | Drone cartographe, station de traitement, station sol et drone agricole |

## 1. Décision proposée

La station de traitement est maintenue. Elle constitue le lieu de production, de contrôle et de versionnement de la carte de référence et des missions agricoles.

La répartition retenue est la suivante :

- le **drone cartographe** acquiert les données brutes, contrôle leur qualité et calcule une odométrie locale temps réel suffisante pour la navigation et le suivi de couverture ;
- la **station de traitement** reconstruit hors ligne la trajectoire optimisée, la carte 3D géoréférencée, la sémantique, le modèle de terrain et le graphe de parcelle ;
- la **station sol** prépare, affiche, lance et interrompt les vols avec QGroundControl ; elle peut être exécutée sur le même PC physique que la station de traitement, mais conserve une responsabilité distincte ;
- le **drone agricole** charge une carte et une mission approuvées, se relocalise en temps réel, construit un corridor local sûr, produit des consignes de trajectoire pour PX4 et commande le traitement sous interverrouillages ;
- **PX4**, sur chaque drone, reste seul responsable du contrôle de vol, des moteurs, de l'armement et des failsafes.

La carte finale ne dépend donc pas de la puissance disponible en vol. Inversement, la sécurité du drone agricole ne dépend jamais d'une connexion permanente à la station.

L'application desktop Qt définie par l'ADR-0007 matérialise la station de traitement et son workflow métier. Elle orchestre les modules headless de réception, compilation, cartographie, édition, approbation, transfert et rapport, sans déplacer leurs algorithmes dans le processus graphique.

## 2. Workflow opérationnel complet

```text
[1. Définition de la parcelle et mission de relevé]
       station de traitement + QGroundControl
                         |
                         v
              SurveyMissionPackage
                         |
                         v
[2. Acquisition par le drone cartographe]
  PX4 + capteurs + enregistrement + FAST-LIO2 temps réel
                         |
                         v
                SurveyRunPackage
       données brutes + calibration + qualité + pose préliminaire
                         |
                         v
[3. Traitement hors ligne sur la station]
  contrôle -> trajectoire optimisée -> nuage 3D -> fusion caméra
  -> terrain -> sémantique -> entités -> graphe -> incertitudes
                         |
                         v
              VineyardMapPackage candidat
                         |
                         v
[4. Contrôle qualité et approbation humaine]
  couverture + cohérence + zones incertaines + compatibilité
                         |
                         v
              VineyardMapPackage approuvé
                         |
                         v
[5. Préparation de la mission agricole]
  prescription -> ordre des rangs -> corridor -> géofence
  -> simulation PX4/Gazebo -> validation opérateur
                         |
                         v
              TreatmentMissionPackage
                         |
                         v
[6. Exécution par le drone agricole]
  vérification -> localisation -> perception locale -> corridor
  -> trajectoire -> PX4 -> bras/dose sous supervision de sécurité
                         |
                         v
                 MissionReportPackage
                         |
                         v
[7. Retour station]
  analyse, carte de traitement, incidents et nouvelle cartographie
  si la parcelle a changé ; aucune mise à jour automatique de la carte
```

Une parcelle ne passe d'une étape à la suivante qu'après franchissement de la porte de validation associée. Une carte candidate ne peut pas être chargée comme carte opérationnelle.

## 3. Responsabilités par calculateur

| Plateforme | Fonctions obligatoires | Fonctions interdites ou différées |
|---|---|---|
| PX4 cartographe | estimation primaire, stabilisation, mission de relevé, géofence, failsafes | sémantique, optimisation globale, commande moteur depuis ROS 2 |
| Compagnon cartographe | pilotes capteurs, synchronisation, diagnostic, enregistrement, LIO local, contrôle de couverture | carte sémantique officielle, entraînement IA, décision finale de qualité |
| Station de traitement | rejeu, calibration, optimisation globale, fusion LiDAR–caméra–GNSS, IA, carte, mission, simulation et rapports | aucune fonction nécessaire à la sûreté pendant le vol |
| QGroundControl | préparation et supervision du vol, armement, alarmes, interruption | traitement lourd des données et autorité sur les boucles de vol |
| PX4 agricole | contrôle de vol, limites, géofence et failsafes | commande directe par un modèle IA |
| Compagnon agricole | vérification carte, localisation, perception locale, corridor, trajectoire haut niveau, mission, bras et dose | entraînement IA, reconstruction globale complète, modification silencieuse de la carte |

## 4. Contrats de données entre les étapes

### 4.1 `SurveyMissionPackage`

Produit par la station, consommé par le cartographe :

- identifiant de parcelle et référentiel géographique ;
- polygone de couverture, géofence et zones interdites ;
- trajectoire de relevé, altitude/vitesse et recouvrements **À valider** ;
- configuration capteurs attendue et critères minimaux de qualité ;
- versions logicielles, paramètres et checksum du paquet.

### 4.2 `SurveyRunPackage`

Produit par le cartographe, consommé par la station :

```text
survey_run/
├── manifest.yaml
├── calibration/
├── raw/                  # LiDAR, images, IMU, GNSS et état PX4
├── trajectory_preview/   # FAST-LIO2 et état de vol, non autoritatifs
├── health/               # pertes, fréquences, températures, horloges
├── events/
└── checksums.sha256
```

Le paquet est refusé si les checksums, la calibration, les horodatages ou la couverture minimale sont invalides.

### 4.3 `VineyardMapPackage`

Produit et approuvé sur la station, consommé par le planificateur et le drone agricole :

```text
vineyard_map/
├── manifest.yaml
├── georeference.yaml
├── trajectory_optimized/
├── geometry/             # nuage/maillage maître et versions allégées
├── terrain/              # altitude, pente, rugosité et ruptures
├── semantics/            # classes et confiances
├── entities/             # rangs, pieds, poteaux, fils, murs, obstacles
├── topology/             # graphe navigable et transitions
├── navigation/           # occupation/ESDF dérivées et tuiles embarquées
├── quality/              # couverture, incertitude et zones interdites
└── checksums.sha256
```

Le format exact des fichiers 3D reste **À valider**. Le manifeste, les identifiants, les repères, les unités, les versions et les checksums sont obligatoires dès le premier prototype.

### 4.4 `TreatmentMissionPackage`

Produit par la station, consommé par le drone agricole :

- référence exacte et checksum du `VineyardMapPackage` ;
- prescription et cibles autorisées ;
- ordre des rangs, sens de passage et transitions ;
- géofence, corridor nominal, vitesses et marges **À valider** ;
- paramètres de traitement autorisés ;
- résultat de simulation et critères d'abandon ;
- état `CANDIDATE`, `SIMULATED`, `APPROVED`, `EXECUTED` ou `REJECTED`.

### 4.5 `MissionReportPackage`

Produit par le drone agricole, consommé par la station : trajectoires commandée et réelle, états de localisation et sécurité, obstacles, actions du bras, débits, zones traitées, événements PX4, configuration et données nécessaires au rejeu.

## 5. Algorithmes du drone cartographe

| Étape | Algorithme de référence initial | Sortie | État de décision |
|---|---|---|---|
| Horodatage | timestamps matériels, PPS/PTP lorsque disponibles, contrôle de dérive | flux alignés + diagnostics | méthode physique **À valider** avec les capteurs |
| Calibration | matrices intrinsèques/extrinsèques versionnées ; aucun ajustement silencieux en vol | arbre TF et incertitudes | principe retenu |
| État de vol | estimateur PX4 avec GNSS RTK et IMU de vol | état PX4 autoritatif pour le vol | retenu |
| Odométrie locale | FAST-LIO2 derrière `lio_adapter` | `odom -> base_link`, qualité et compteurs | baseline retenue, qualification Jetson restante |
| Couverture | grille de visibilité/frustum et densité d'observation | zones vues, trous et alarme de reprise | baseline géométrique à développer |
| Contrôle qualité | règles sur fréquence, latence, pertes, saturation et stockage | état `OK/DEGRADED/ERROR` | déterministe, retenu |
| Enregistrement | rosbag segmenté + manifeste + checksums | `SurveyRunPackage` | retenu |

La segmentation sémantique complète, la colorisation dense et la fermeture de boucle ne sont pas obligatoires en vol dans la première version. Une prévisualisation pourra être ajoutée plus tard si le budget Jetson le permet, mais elle ne deviendra pas la carte de référence.

## 6. Algorithmes de la station de traitement

| Étape | Famille d'algorithmes | Baseline proposée | Critère principal |
|---|---|---|---|
| Intégrité | validation de schéma, checksum et chronologie | règles déterministes | aucune donnée manquante non signalée |
| Calibration | reprojection caméra et alignement LiDAR–IMU | optimisation non linéaire par lot | résidus et stabilité |
| Trajectoire initiale | LIO par rejeu | FAST-LIO2 | ATE/RPE et complétude |
| Trajectoire globale | graphe de facteurs LiDAR–IMU–GNSS avec boucles | LIO-SAM/GTSAM comme candidat, avec boucles qualifiées séparément | erreur absolue, fermeture et covariance |
| Nuage maître | compensation de mouvement, accumulation et filtrage | projection des scans sur la trajectoire optimisée | cohérence de surfaces |
| Fusion LiDAR–caméra | projection calibrée, test de visibilité et association temporelle | colorisation géométrique avant toute IA | erreur de reprojection et taux associé |
| Terrain | classification robuste du sol puis grille 2,5D/maillage | voisinage local, normales, pente et filtrage robuste | erreur d'altitude et ruptures |
| Sémantique | segmentation d'image puis projection probabiliste en 3D | réseau léger de segmentation à sélectionner par benchmark | IoU par classe et calibration de confiance |
| Poteaux/murs/talus | fusion classe IA + primitives géométriques | composantes 3D, lignes/plans/cylindres robustes | précision, rappel et erreur 3D |
| Fils | carte conservatrice multimodale | vision + géométrie + relation poteaux, jamais LiDAR seul | taux de non-détection |
| Rangs/pieds | regroupement de végétation et graphe spatial | clustering, axe local et contraintes viticoles | validité topologique |
| Volume végétal | occupation/maillage par entité | voxels ou enveloppe alpha/convexe selon densité | erreur face à mesures terrain |
| Carte navigation | occupation 3D et champ de distance | nvblox/ESDF comme candidat GPU, export en tuiles | mémoire, latence et marges |
| Confiance | couverture, dispersion, accord des modalités et règles métier | score explicable par entité et par tuile | calibration et détection des zones faibles |

Le modèle IA exact n'est pas figé avant la constitution des annotations. Le premier benchmark comparera au minimum une segmentation légère et une solution plus précise sur la RTX, puis sur Jetson. L'entraînement reste sur la station ; le drone ne reçoit qu'un modèle exporté en ONNX puis optimisé avec la version TensorRT compatible avec son JetPack.

## 7. Algorithmes de préparation de mission

| Fonction | Type d'algorithme | Baseline proposée |
|---|---|---|
| Sélection des rangs/cibles | filtres de prescription et contraintes de carte | règles déterministes et validation opérateur |
| Ordonnancement global | recherche sur graphe avec coût énergie/temps/risque | plus court chemin + optimisation d'ordre des segments |
| Trajectoire nominale | ligne centrale/offset du rang, profil d'altitude issu du terrain | spline 3D bornée en courbure, vitesse et accélération |
| Transitions | graphe de bouts de rang et zones de demi-tour | primitives validées puis optimisation locale |
| Corridor nominal | dilatation géométrique du drone et du bras dans l'espace libre | enveloppe 3D conservatrice |
| Validation | collision, géofence, dynamique, énergie, produit et incertitude | contrôles déterministes + PX4 SITL/Gazebo |

La station produit une mission nominale complète, mais le drone agricole conserve le droit de ralentir, s'arrêter, replanifier localement ou abandonner.

## 8. Algorithmes embarqués sur le drone agricole

| Étape | Algorithme de référence initial | Fréquence indicative | État de décision |
|---|---|---:|---|
| Vérification carte/mission | schéma, version, checksum, repère et compatibilité | avant armement | retenu |
| État de vol | estimateur PX4 GNSS/IMU | natif PX4 | retenu |
| Odométrie continue | FAST-LIO2 derrière `lio_adapter` | LiDAR, typiquement 10–20 Hz | baseline retenue |
| Recalage global | initialisation RTK puis scan-to-map robuste NDT/GICP/ICP | 1–10 Hz **À valider** | candidat à benchmarker |
| Fusion de localisation | filtre d'erreur ou graphe local borné entre PX4, LIO et recalage | 20–100 Hz **À valider** | interface à figer avant implémentation |
| Terrain local | grille d'élévation autour du drone | ≥ 10 Hz **À valider** | baseline géométrique |
| Obstacles | retrait sol, clustering 3D, suivi et fusion vision | ≥ 10 Hz **À valider** | géométrie d'abord, IA en complément |
| Sémantique locale | inférence TensorRT légère | 5–15 Hz **À valider** | modèle à sélectionner |
| Carte locale | occupation/ESDF roulante | ≥ 10 Hz **À valider** | nvblox ou équivalent à benchmarker |
| Corridor drone + bras | collision par volumes dilatés et distance signée | ≥ 20 Hz **À valider** | déterministe, retenu |
| Plan local | suivi de spline nominale avec évitement borné | ≥ 20 Hz **À valider** | spline/MPC ou optimisation locale à comparer |
| Interface PX4 | consignes position/vitesse Offboard et watchdog | ≥ 20 Hz **À valider** | socle du lot A validé |
| Sécurité applicative | machine à états et règles de fraîcheur/cohérence | indépendante, ≥ 20 Hz **À valider** | aucune IA autorisée |
| Ciblage | association entité carte–observation et temps avant cible | cadence perception | baseline déterministe |
| Dose | anticipation vitesse/latence puis régulation débit/pression | cadence actionneur **À valider** | feedforward + PID, sur banc d'abord |

La VIO reste une source complémentaire ou un mode dégradé à étudier si le LiDAR devient insuffisant. Elle ne sera pas ajoutée à la première chaîne uniquement parce qu'une caméra est disponible.

## 9. Autorités et repères

| Information | Autorité |
|---|---|
| Attitude, armement, commande moteur et failsafes | PX4 |
| Odométrie locale continue du compagnon | `localization_manager` à partir du LIO |
| Correction globale `map -> odom` | module de recalage/fusion |
| Géométrie et sémantique de référence | `VineyardMapPackage` approuvé |
| Autorisation de traitement | `safety_supervisor` et machine de mission ; PX4 peut toujours interrompre le vol |
| Prescription et cibles | `TreatmentMissionPackage` approuvé |

La chaîne TF cible reste :

```text
earth -> map -> odom -> base_link -> capteurs / bras / buses
```

`map -> odom` peut évoluer lentement avec le recalage. `odom -> base_link` doit rester continu. Une correction globale ne doit jamais introduire directement un saut de consigne dangereux.

## 10. Classes temporelles

1. **Vol critique** : PX4 et ses capteurs, hors ROS 2.
2. **Temps réel compagnon borné** : localisation, obstacle, corridor, trajectoire et sécurité. Files bornées, watchdog et mode dégradé obligatoires.
3. **Temps réel souple** : sémantique locale, visualisation et journalisation. Une perte ne commande jamais directement le drone.
4. **Hors ligne** : optimisation globale, entraînement, reconstruction dense, carte finale, analyse et rapports.

Un algorithme neuronal ne ferme aucune boucle critique. Il fournit une observation et une confiance à une logique déterministe qui applique les marges et décide de l'inhibition.

## 11. Cycle de vie des modèles IA

```text
annotation -> entraînement RTX -> validation séparée -> export ONNX
-> optimisation TensorRT pour la cible -> benchmark Jetson
-> paquet modèle versionné -> inférence seule sur le drone
```

Un moteur TensorRT est lié à sa cible et à la version de runtime ; il est reconstruit et testé pour chaque combinaison JetPack/Jetson. Le modèle conserve son jeu de validation, ses classes, son prétraitement, ses seuils et son checksum.

## 12. Stratégie de développement des algorithmes

Chaque fonction suit le même ordre :

1. figer son contrat d'entrée/sortie et ses repères ;
2. produire un oracle ou un jeu de données de validation ;
3. implémenter une baseline simple et explicable ;
4. mesurer précision, latence, ressources, confiance et modes d'échec ;
5. n'introduire une solution plus complexe que si la baseline échoue à un critère ;
6. valider sur rejeu, simulation, Jetson, puis capteurs réels selon sa criticité ;
7. versionner configuration, test et résultat avant de passer au module suivant.

Cette règle évite de développer simultanément une chaîne de recherche difficile à diagnostiquer.

## 13. Lots de développement révisés

| Lot | Résultat attendu | Algorithmes développés |
|---|---|---|
| A — PX4/ROS 2 | liaison, état, trajectoire Offboard et failsafe | réalisé |
| B1 — Contrats et acquisition cartographe | `SurveyMissionPackage`, `SurveyRunPackage`, synchronisation et contrôle qualité | règles de données avant perception |
| B2 — Géométrie de carte | trajectoire globale, nuage maître et fusion LiDAR–caméra | FAST-LIO2 initial, graphe de facteurs, projection calibrée |
| B3 — Carte métier | terrain, classes, entités, graphe et confiance | géométrie puis segmentation IA |
| B4 — Carte approuvée et mission | paquets carte/mission, planification et simulation | graphe, spline, corridor et portes qualité |
| C1 — Localisation agricole | chargement carte, LIO et recalage carte/réel | FAST-LIO2 + NDT/GICP/ICP à comparer |
| C2 — Navigation locale | terrain, obstacles, ESDF, corridor et plan local | géométrie temps réel puis perception IA |
| C3 — Mission autonome | exécution PX4, transitions, reprises et défauts | machine à états et superviseur |
| D1 — Bras sans liquide | enveloppe, déploiement, blocage et navigation | commande déterministe sur banc puis SITL/HITL |
| D2 — Eau/traceur | ciblage, dose, débit et compte rendu | anticipation + régulation |
| D3 — Agronomie autorisée | compensation air/downwash et protocole réel | après toutes les portes précédentes |

Le prochain développement autorisé est donc **B1**, pas encore la segmentation ou le planificateur local.

## 14. Portes de validation

| Porte | Condition de sortie minimale |
|---|---|
| G0 — Acquisition | synchronisation mesurée, calibration connue, pertes explicites et package intègre |
| G1 — Géométrie | trajectoire et nuage reproductibles, géoréférencement et incertitude disponibles |
| G2 — Sémantique | métriques par classe, confiance calibrée et zones inconnues conservées |
| G3 — Carte | schéma compatible, graphe cohérent, couverture suffisante et revue opérateur |
| G4 — Mission | aucune collision simulée, contraintes et failsafes testés, version approuvée |
| G5 — Navigation | tenue temps réel sur Jetson, localisation/corridor valides et défauts injectés |
| G6 — Traitement | vannes sûres, bras qualifié, eau/traceur conforme et traçabilité complète |

Les seuils numériques non encore mesurés restent **À valider** dans le cahier des charges.

## 15. Traçabilité principale

| Exigences | Étapes du workflow | Composants principaux | Porte |
|---|---|---|---|
| `MAP-FUN-001`, `SYS-FUN-002` | acquisition cartographe | `sensor_manager`, `logger_recorder` | G0 |
| `MAP-FUN-002`, `MAP-FUN-003` | trajectoire et géométrie | `lio_adapter`, optimisation station, `map_builder` | G1 |
| `MAP-FUN-004` à `MAP-FUN-008` | carte métier et confiance | `semantic_perception`, `terrain_model`, `map_builder` | G2–G3 |
| `TRT-FUN-001`, `SAFE-REQ-007` | chargement carte et mission | `map_server_vineyard`, `mission_manager` | G4 |
| `TRT-FUN-002` à `TRT-FUN-005` | localisation et corridor | `localization_manager`, `local_planner`, `safety_supervisor` | G5 |
| `TRT-FUN-006` à `TRT-FUN-012` | bras, ciblage et dose | contrôleurs de traitement et journalisation | G6 |
| `SAFE-REQ-001` à `SAFE-REQ-003` | toutes les phases de vol | PX4, `px4_bridge`, `safety_supervisor` | chaque porte |

## 16. Décisions encore ouvertes

- capteurs physiques et méthode de synchronisation matérielle ;
- format binaire de la géométrie 3D et de l'ESDF ;
- méthode finale d'optimisation globale et de fermeture de boucle ;
- architecture du modèle de segmentation et jeu d'annotations ;
- algorithme de recalage carte/réel ;
- backend de carte locale et planificateur local ;
- budgets Jetson et choix Orin Nano/Orin NX ;
- seuils de qualité de chaque porte.

Ces points sont volontairement laissés ouverts : le workflow et les interfaces sont définis avant la sélection expérimentale des implémentations.

## 17. Prochaine action

Créer les schémas versionnés des trois premiers contrats (`SurveyMissionPackage`, `SurveyRunPackage`, `VineyardMapPackage`), puis auditer dans BotanicGarden `1006-03` les flux caméra, leurs timestamps et leurs extrinsèques. Cette étape fournit la base mesurable du lot B1 sans encore entraîner ni choisir un modèle IA.

## 18. Références techniques

- FAST-LIO2, implémentation officielle : `https://github.com/hku-mars/FAST_LIO` ;
- LIO-SAM, implémentation officielle et notes sur GNSS/boucles : `https://github.com/TixiaoShan/LIO-SAM` ;
- NVIDIA Isaac ROS nvblox : `https://nvidia-isaac-ros.github.io/repositories_and_packages/isaac_ros_nvblox/isaac_ros_nvblox/index.html` ;
- NVIDIA TensorRT : `https://docs.nvidia.com/deeplearning/tensorrt/latest/` ;
- DOC-00, DOC-01, DOC-02, DOC-17 et ADR-0003 du projet.
