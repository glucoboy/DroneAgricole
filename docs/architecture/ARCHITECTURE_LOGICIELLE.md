# Architecture logicielle

| Champ | Valeur |
|---|---|
| Référence | `DOC-SW` |
| Nature | document vivant |
| Dernière mise à jour | 24 septembre 2026 |
| Statut | station C++17/Qt 6 implémentée partiellement ; logiciel embarqué cible **À valider** |

## 1. Objet

Ce document décrit l'ensemble du logiciel du système : station desktop, outils
headless, adaptateurs de données et de calcul, environnements ROS 2, intégration
PX4, déploiement et tests. Il distingue systématiquement les capacités
**planifiées**, **implémentées** et **qualifiées**.

Le fonctionnement système est défini dans [DOC-HLD](HLD.md). Les interfaces
physiques sont détaillées dans [DOC-ELEC](ARCHITECTURE_ELECTRIQUE_RESEAUX.md).

## 2. Principes d'architecture

- Toute logique exécutable propriétaire est écrite en C++17.
- L'interface desktop utilise Qt 6 Widgets ; sa structure est placée au maximum
  dans des fichiers `.ui`.
- Présentation, application, domaine, algorithmes et adaptateurs sont séparés par
  des dépendances de compilation explicites.
- L'UI appelle les services ; elle ne contient ni logique métier, ni lancement
  concret de processus, ni finalisation de résultat.
- Les mêmes règles applicatives sont utilisables par l'UI et la CLI.
- Les variantes de datasets, runtimes et algorithmes sont des adaptateurs, pas
  des branches ajoutées dans `MainWindow`.
- Les fonctions critiques de vol restent dans PX4. ROS 2 publie des consignes
  avancées et supervise leur validité.
- Configuration, résultats et interfaces sont versionnés ; les files et délais
  critiques sont bornés.

Ces principes constituent la référence active pour les évolutions logicielles.

## 3. Contexte et déploiement

```text
 Application Qt / CLI sur la station
        |
        +-- services applicatifs et domaine C++17
        +-- adaptateurs stockage, processus, HTTP, ROS 2 et cartographie
        +-- Docker Compose : LIO, télémétrie, PX4 SITL, Gazebo
                           |
                           v
 Jetson Orin NX 16 Go / ROS 2 -- uXRCE-DDS/MAVLink -- Pixhawk 6X / PX4
        |                                    même porteuse Holybro
        +-- capteurs, localisation, perception, mission, traitement
```

| Cible | Organisation | État |
|---|---|---|
| Windows 11 | station Qt 6 et outils C++17 natifs | implémenté et testé localement |
| Docker `amd64` | ROS 2 Humble/Jazzy, LIO et PX4/Gazebo isolés | implémenté préliminaire |
| Jetson Orin NX 16 Go `arm64` | JetPack, pilotes hôte et conteneurs ROS 2 sur porteuse Holybro Pixhawk Jetson | déploiement **Planifié** ; exécution et thermique **À valider** |
| Pixhawk 6X module seul | PX4 et failsafes indépendants du compagnon sur la même porteuse | SITL partiel ; intégration matérielle **À valider** |

Compose sépare trois environnements : Ubuntu 22.04 / ROS 2 Humble pour données,
LIO et télémétrie ; Ubuntu 24.04 / ROS 2 Jazzy pour les ponts et la simulation ;
et l'image PX4/Gazebo épinglée dans `compose.yaml`. Les données brutes sont
montées en volume et ne sont jamais incorporées aux images. Le banc utilise
actuellement PX4 `v1.18.0-beta2`, uniquement à titre expérimental ; une version
stable épinglée est requise avant qualification formelle. Le domaine ROS de
banc est `42`.

La cible matérielle réunit le module Pixhawk 6X et le Jetson Orin NX 16 Go
sur la **Holybro Pixhawk Jetson Baseboard**. Le partage de porteuse ne modifie
pas la frontière d'autorité : PX4 reste autonome pour le vol critique, et ROS 2
ne transmet que des consignes de haut niveau. L'interface physique retenue pour
uXRCE-DDS ou MAVLink, ses ports, débits, redémarrages et pertes restent
**À valider**. Le PM08-CAN alimente POWER1 et POWER2 par deux BEC distincts,
avec mesure DroneCAN séparée sur CAN1 ; CA01 possède son 5 V local protégé
pour la radio et la porteuse reçoit un 12 V candidat par XT30. Les brochages,
protections et essais de défaut relèvent de
[DOC-ELEC](ARCHITECTURE_ELECTRIQUE_RESEAUX.md). Une perte ou un redémarrage
du Jetson ne doit pas empêcher les failsafes PX4 ; ce comportement doit être
démontré sur la configuration matérielle finale.

## 4. Architecture de la station

### 4.1 Couches et sens des dépendances

```text
 presentation (Qt Widgets/.ui)
          |
          v
 application --------> domain/ports
          ^                 ^
          |                 |
 composition ------ adapters/process/storage/runtime/mapping/runners
          |
       support
```

Le point de composition construit les implémentations concrètes. Les services
applicatifs ne dépendent pas des classes techniques. `Qt Widgets` reste confiné
à la présentation ; `Qt Network` reste dans les adaptateurs réseau.

### 4.2 Modules compilés et tests associés

| Cible CMake | Responsabilité | Dépendances principales | Tests directs |
|---|---|---|---|
| `drone_agricole_station` | description des capacités et modules de la station | Qt Core | `test_station_architecture` |
| `drone_agricole_support` | types communs, JSON, métriques de benchmark | Qt Core/Gui | `test_benchmark_support` |
| `drone_agricole_algorithms` | carte de points, trajectoire, rangs, projection caméra, reconstruction | support | `test_adaptive_point_map`, `test_trajectory_analysis`, `test_row_detection`, `test_camera_color_fusion`, `test_scan_reconstruction` |
| `drone_agricole_storage` | résultats, rosbag ROS 1 et normalisation des datasets | support | `test_ros1_bag` et tests de dépôts |
| `drone_agricole_mapping` | modèle viticole et adaptation/reconstruction FriûlBot | storage, algorithms, TIFF, YAML | `test_vineyard_map` et tests cartographiques d'intégration |
| `drone_agricole_runtime` | télémétrie, orchestration LIO, accès ROS 2 ou adaptateurs HTTP/stubs | storage, algorithms, Qt Network | `test_telemetry_bridge` |
| `drone_agricole_catalog` | contrats et catalogue des définitions | support | `test_contract_registry` |
| `drone_agricole_runners` | résolution des runners et commandes approuvées | catalog, YAML | `test_runner_registry` |
| `drone_agricole_data_services` | dépôt de résultats et comparaison | catalog, mapping, runtime | `test_result_repository`, `test_comparison_service` |
| `drone_agricole_application` | cycle commun de tâche via ports | Qt Core | `test_run_service` |
| `drone_agricole_process` | exécution et annulation de processus derrière un port | application | `test_process_backend` |
| `drone_agricole_composition` | assemblage des services et commandes UI/CLI | services, runners, process | tests station et dashboard |
| `drone_agricole_presentation` | navigation, pages, rendu trajectoire/3D et interactions | application, support, Qt Widgets | `test_trajectory_view`, `test_dashboard_mapping`, `test_station_navigation`, `test_dashboard_smoke` |

`drone_agricole_core` est une cible de compatibilité sans source propre. Elle ne
doit pas redevenir un noyau universel.

### 4.3 Exécutables

VS Code peut ouvrir la racine ou `software/cpp`. Dans ce dernier cas,
`software/cpp/.vscode/settings.json` fixe la racine CMake à `../..` ; les tâches
et le lancement utilisent les profils centraux et le même répertoire `build/`.
Il n'y a pas de deuxième projet CMake autonome ni de copie des profils.

| Exécutable | Rôle | UI |
|---|---|---|
| `drone-agricole-dashboard` | station de mission desktop | Qt 6 Widgets |
| `drone-agricole-tools` | accès headless aux mêmes capacités applicatives | CLI |
| `drone-agricole-px4-client` | diagnostic du service PX4 distant | CLI |

Le client PX4 desktop vérifie l'API locale avant un essai et peut démarrer les
services Compose explicitement approuvés du banc s'ils sont absents. Les API
restent publiées sur la boucle locale. Cette préparation ne déclenche jamais
l'essai Offboard : requête validée, runner autorisé et verrou SITL restent
obligatoires.

### 4.4 Paquets ROS 2 implémentés

| Paquet/cible | Fonctionnement | Test |
|---|---|---|
| `drone_agricole_px4_bridge/px4_bridge_support` | conversions de repères, plan Offboard et contrat du runner | `test_frames`, `test_offboard_plan`, `test_runner_contract` |
| `drone_agricole_px4_bridge/state_bridge` | traduit l'état PX4 vers les messages ROS 2 et diagnostics, sans commander le vol | scénarios SITL et intégration **À valider** au-delà des tests de support |
| `drone_agricole_px4_bridge/offboard_test` | exécute uniquement le scénario Offboard SITL doublement verrouillé | carré et perte Offboard historiques ; régression active **À valider** |
| `drone_agricole_px4_bridge/runner_server` | expose le lancement contrôlé des scénarios au service local de station | contrat unitaire et test d'intégration du runner |
| `livox_ros_driver2_msgs_compat` | fournit les messages officiels nécessaires au rejeu Livox hors ligne | construction ROS 2 et rejeu ; pas de logique métier |

### 4.5 Navigation

La navigation est organisée autour des activités et objets métier. Les pages
actuelles couvrent vue d'ensemble, exécution, résultats, comparaison et détail
d'un résultat. Une nouvelle fonction n'ajoute pas automatiquement une
destination principale : elle fournit contrats, services, actions contextuelles
et vues spécialisées. Une tâche active reste observable lors d'un changement de
page. La fermeture de la station demande l'annulation d'un traitement actif et
attend sa fin ; aucun détachement implicite n'est autorisé. Une reprise après
fermeture n'est pas présumée.

Les formulaires principaux sont :

- `ui/main_window.ui` ;
- `ui/execution_page.ui` ;
- `ui/results_page.ui` ;
- `ui/comparison_page.ui` ;
- `ui/result_view_page.ui`.

## 5. Contrats et données

Le catalogue décrit séparément datasets, simulations et runners. Les schémas
JSON sous `configs/visualization/schemas/` valident leurs structures. Les
adaptateurs historiques normalisent les résultats LIO et PX4 en lecture seule.

Objets métier cibles :

| Objet | Rôle | État |
|---|---|---|
| définition de dataset/simulation | paramètres, capacités et provenance | implémenté |
| exécution et résultat | cycle, état, artefacts, métriques et erreurs | implémenté |
| `SurveyMissionPackage` | demande et configuration d'acquisition | planifié |
| `SurveyRunPackage` | acquisition reçue et contrôlée | planifié |
| `VineyardMap` | carte versionnée, repère, géométrie et qualité | modèle partiel implémenté |
| paquet de mission de traitement | carte liée, trajectoires et prescription | planifié |
| rapport de traitement | réalisé, événements et écarts | planifié |

Une carte approuvée est immuable. Toute édition produit une nouvelle version.
La preuve d'approbation lie au minimum identité, version du manifeste et
empreinte du contenu. Le transfert vérifie manifeste, empreintes, compatibilité,
cible et accusé de réception. Signature cryptographique, identités, transport
et migrations restent **À valider**.

Les paquets inter-étapes contiennent au minimum :

- `SurveyMissionPackage` : parcelle, repère, couverture, géofence, trajectoire
  de relevé, configuration attendue, critères qualité et empreinte ;
- `SurveyRunPackage` : manifeste, calibrations, données brutes, aperçu de
  trajectoire non autoritatif, santé, événements et empreintes ;
- `VineyardMapPackage` : géoréférence, trajectoire optimisée, géométrie, terrain,
  sémantique, entités, topologie, données de navigation, qualité et empreintes ;
- `TreatmentMissionPackage` : carte exacte, prescription, ordre des rangs,
  trajectoire, corridor, paramètres autorisés, résultat de simulation et état ;
- `MissionReportPackage` : trajectoires commandée/réelle, localisation, sûreté,
  obstacles, bras, débits, zones traitées, événements PX4 et configuration.

Le modèle de carte représente terrain, terrasses, rangs, pieds, poteaux, fils,
murs, obstacles, zones interdites et confiance. Les géométries lourdes peuvent
être référencées par URI et empreinte plutôt qu'imbriquées dans les messages.

## 6. Chaîne cartographique

```text
 adaptateur capteurs
   -> synchronisation et calibration
   -> localisation LiDAR/IMU
   -> accumulation de points colorisés
   -> reconstruction de surface
   -> scène viticole versionnée
   -> détection de rangs et étude de trajectoire
```

État actuel : l'adaptateur FriûlBot, la projection caméra, une odométrie ICP
LiDAR bornée, l'accumulation et une triangulation locale sont implémentés à un
niveau préliminaire. Ils publient diagnostics et état partiel en cas d'échec.
Ils ne constituent ni un LIO qualifié, ni une carte globale qualifiée pour les
collisions. EscaYard est conservé comme régression historique, pas comme nouveau
parcours actif.

La composition RGB issue de bandes visibles multispectrales reste un diagnostic,
pas une couleur radiométriquement calibrée. Le sol demeure dans la scène ; le
masque de végétation sert uniquement à la détection des rangs. Le rendu courant
reste un `QWidget` natif. Pour toute simulation future, enveloppe visuelle,
géométrie de collision et paramètres physiques sont des modèles distincts.

Les poses de référence, RTK, roues ou SLAM d'un dataset ne sont pas utilisées
comme entrées cachées de prédiction. Une absence de pose n'est jamais compensée
par une trajectoire inventée.

### 6.1 Détection des rangs et trajectoires hors ligne

La baseline reste géométrique et explicable : contrôle CRS/unités, estimation
du sol, normalisation des hauteurs, sélection de végétation/structures,
projection 2D, composantes ou densité locale, estimation robuste des axes puis
ajustement de courbes/splines. Les axes sont ordonnés dans un graphe de parcelle ;
les limites observées et zones inconnues contraignent le corridor. La trajectoire
nominale est issue du centre libre, lissée avec courbure, pente, vitesse et
accélération bornées.

Une baseline par lignes droites peut servir au test initial, mais ne satisfait
pas `MAP-FUN-007` sur rangs courbes ou irréguliers. Les métriques attendues sont
erreur latérale des axes, rappel des rangs, ruptures, topologie, largeur libre,
distance aux obstacles et respect dynamique. LaMole/Grospoli reste le cas
difficile sous autorisation ; EscaYard sert de baseline géospatiale publique et
FriûlBot de baseline temporelle LiDAR–caméra.

### 6.2 Assemblage des scans et surface observée

Dans **Essais → Cartographie 3D LiDAR–caméra**, la variante
**Assemblage des scans et surface 3D** (`scan_surface_v1`) utilise le même
service UI/CLI que la capture locale. Les paramètres sont l'instant de départ,
la durée, l'intervalle entre scans, la portée, la cellule de fusion et la
longueur maximale des arêtes. Les réglages initiaux sont **À valider**.

`algorithms/ScanReconstruction` fournit le recalage rigide ICP à six degrés de
liberté, la triangulation du voisinage angulaire des anneaux LiDAR et la fusion
des sommets. `adapters/mapping/FriulBotReconstruction` décode les scans,
applique la sélection temporelle, associe les captures caméra et archive les
produits. La variante traite une fenêtre de 1 à 60 s ; les limites de travail
sont 350 scans réguliers, 400 scans avec captures, 256 Mio de messages,
100 000 sommets et 150 000 faces. Atteindre la capacité de surface interrompt
l'accumulation avec résultat partiel explicite.

Le premier scan définit le repère de carte. Les poses expriment
`p_carte = R_carte_lidar × p_lidar + t_carte_lidar`. Les horodatages du bag
sont conservés en nanosecondes sous forme de chaînes, sans perte de précision.
Les scans caméra proches remplacent le scan régulier dans la sélection ; leurs
couleurs ne sont projetées qu'avec leurs propres images. Un désaccord entre
nombres de déclenchements et jeux d'images désactive la couleur.

L'ICP emploie deux résolutions et des correspondances tronquées. Les contrôles
préliminaires comprennent convergence, recouvrement ≥ 50 %, résidu ≤ 0,25 m,
translation ≤ 2 m et rotation ≤ 20° entre scans. Une géométrie colinéaire, une
interruption temporelle ou un recalage insuffisant ne génère pas de pose de
remplacement. Avec moins de deux scans acceptés, le traitement échoue ; sinon
la portion acceptée est archivée comme carte partielle. Ces seuils ne sont pas
une qualification de précision absolue et restent **À valider**.

La surface conserve les discontinuités : arêtes trop longues, triangles
dégénérés et cellules angulaires sans mesure sont exclus. Les faces observées
des différents scans sont recalées et dédupliquées par sommets voxelisés.
L'espace inconnu n'est pas fermé artificiellement. Le résultat est une surface
triangulée ouverte, avec une couleur grise là où aucune image n'est projetée.

Chaque archive contient `map_prediction.json`, `map_replay.json`,
`estimated_poses.json` (poses et diagnostics par recalage) et `surface.ply`.
Le contrat de rejeu ajoute un objet `surface` (sommets, triplets d'indices et
couleurs), en conservant la lecture des archives antérieures. L'UI affiche la
surface ou le nuage, et peut masquer la trajectoire d'acquisition superposée.
Cette superposition ne constitue pas un contrôle de collision.

Limites : odométrie LiDAR sans fusion IMU, correction intra-scan ni fermeture
de boucle ; appariement temporel/calibration à qualifier, dérive possible et
triangulation locale des mesures. L'assemblage complet d'une parcelle, la
surface qualifiée pour les collisions et la simulation dynamique du drone de
traitement restent à valider ou à développer.

## 7. Logiciel embarqué cible

| Domaine ROS 2 | Responsabilité | État |
|---|---|---|
| acquisition/calibration | pilotes, timestamps, diagnostics et extrinsèques | planifié/intégrations tierces |
| localisation | LIO/VIO/GNSS et état autoritatif | benchmarks réalisés ; sélection embarquée **À valider** |
| perception/cartographie | végétation, terrain, obstacles, fils et carte locale | planifié, briques station préliminaires |
| navigation | route, corridor, trajectoire et interface PX4 | SITL partiel puis planifié |
| mission/sûreté | machines à états, gardes, abandon applicatif | planifié |
| traitement | bras, ciblage, pompe, vannes, débit et air | planifié |
| journalisation | manifeste, événements et données nécessaires au rapport | planifié |

Les processus critiques sont isolés initialement. Le superviseur doit détecter
la disparition d'un processus sans dépendre de celui-ci. La composition
intra-processus des flux lourds n'est admise qu'après mesure.

### 7.1 Composants logiques cibles

| Composant | Responsabilité | Validation principale |
|---|---|---|
| `sensor_manager` | pilotes, démarrage, timestamps et diagnostics | pertes, fréquences, redémarrage et données invalides |
| `calibration_manager` | calibrations versionnées et arbre de repères | cohérence, empreintes et reprojection |
| `px4_bridge` | état PX4 et consignes bornées | SITL, perte Offboard et conversions de repères |
| `lio_adapter` | normaliser l'odométrie du moteur LIO retenu | ATE/RPE, complétude, ressources et rejeu |
| `localization_manager` | état local continu et correction globale | perte GNSS, sauts, covariance et fraîcheur |
| `semantic_perception` | classes, objets et confiances | précision/rappel/IoU, calibration et latence |
| `terrain_model` | surface, pente, rugosité et ruptures | erreur d'altitude et détection des ruptures |
| `obstacle_tracker` | obstacles locaux et prédiction | rappel, distance, faux libres et latence |
| `map_builder` | géométrie 3D, fusion et qualité | cohérence des surfaces, couverture et incertitude |
| `map_server_vineyard` | versions de carte et tuiles embarquées | compatibilité, immutabilité et migration |
| `route_planner` | ordre global des segments | coût, atteignabilité et contraintes |
| `local_planner` | corridor et trajectoire locale | collisions, marges, dynamique et temps réel |
| `trajectory_controller` | convertir la trajectoire en consignes PX4 | cadence, bornes, expiration et refus PX4 |
| `arm_controller` | déploiement, rétraction et défauts du bras | banc, timeouts, blocages et état sûr |
| `treatment_targeter` | associer cible, carte et fenêtre temporelle | erreur d'association et décalage temporel |
| `spray_controller` | débit, pompe, vannes et mesure | banc eau/traceur, dose et fermeture sûre |
| `airflow_controller` | assistance d'air et compensation | banc puis essais agronomiques autorisés |
| `mission_manager` | machine à états applicative | transitions, annulation, reprise et défauts |
| `safety_supervisor` | invariants et inhibition applicative | injection de chaque défaut critique |
| `logger_recorder` | manifeste, événements et données de rejeu | intégrité, stockage plein et rejeu déterministe |
| `benchmark_runner` | campagnes reproductibles hors vol | contrats, empreintes et comparaison multi-runs |

### 7.2 Allocation algorithmique

| Étape | Baseline/candidat | Statut et test attendu |
|---|---|---|
| odométrie cartographe | FAST-LIO2 derrière `lio_adapter` | baseline PC ; Jetson et multi-scènes **À valider** |
| trajectoire globale | graphe LiDAR–IMU–GNSS avec boucles, LIO-SAM/GTSAM candidat | ATE, boucles et covariance **À valider** |
| fusion LiDAR–caméra | projection calibrée, visibilité et association temporelle | tests synthétiques implémentés ; matériel **À valider** |
| terrain | normales, voisinage local, grille 2,5D/maillage robuste | oracle terrain et ruptures **À valider** |
| poteaux/murs/talus | classes visuelles et primitives 3D robustes | précision, rappel et erreur 3D **À valider** |
| fils | fusion vision, géométrie et relation aux poteaux | non-détection prioritaire ; aucun capteur seul |
| rangs/pieds | végétation, axes locaux et graphe spatial | baseline géométrique partielle implémentée |
| carte de navigation | occupation 3D/ESDF, `nvblox` ou équivalent candidat | mémoire, latence et marges **À valider** |
| mission nominale | graphe, splines 3D et corridor conservatif | simulation et revue opérateur **À valider** |
| recalage carte/réel | initialisation RTK puis NDT/GICP/ICP robuste | multi-scènes et pertes GNSS **À valider** |
| plan local | suivi de spline, évitement borné, MPC/optimisation à comparer | ≥20 Hz et scénarios d'obstacles **À valider** |
| ciblage/dose | anticipation des latences, feedforward et PID | banc sec puis eau/traceur **À valider** |

Les baselines restent simples et explicables. Une solution plus complexe n'est
introduite que si une mesure démontre l'insuffisance de la baseline.

### 7.3 Classes temporelles et IA

1. **Vol critique** : PX4 et ses capteurs, hors ROS 2.
2. **Temps réel compagnon borné** : localisation, obstacles, corridor,
   trajectoire et sûreté avec files bornées et watchdog.
3. **Temps réel souple** : sémantique, visualisation et journalisation ; une
   perte ne commande jamais directement le drone.
4. **Hors ligne** : optimisation globale, entraînement, reconstruction dense,
   carte finale et rapports.

Un modèle neuronal produit une observation et une confiance, jamais une commande
directe de moteur. Son cycle est : annotation, entraînement station, validation
séparée, export ONNX, optimisation TensorRT pour une cible JetPack/Jetson,
benchmark embarqué et paquet versionné avec classes, prétraitement, seuils et
empreinte.

### 7.4 Machines à états cibles

```text
Cartographe : BOOT -> SELF_TEST -> READY -> TAKEOFF -> MAPPING
                                                   -> PAUSE/RETURN/ABORT -> LAND

Traitement : BOOT -> SELF_TEST -> READY -> TAKEOFF -> TRANSIT -> APPROACH
          -> DEPLOY_ARM -> TREATMENT -> RETRACT_ARM -> NEXT_ROW/RETURN
          -> PAUSE/ABORT selon les gardes
```

Le produit n'est autorisé que dans `TREATMENT`. Les transitions exactes et leur
répartition PX4/ROS 2 restent **À valider**.

## 8. Interfaces PX4 et ROS 2

PX4 produit l'état de vol et applique les consignes autorisées. Le compagnon
porte perception, planification et mission applicative. Les échanges cibles
comprennent :

- états PX4, mode, armement et failsafes ;
- odométrie/localisation avec covariance et fraîcheur ;
- trajectoire ou consigne de haut niveau avec durée de validité ;
- états des capteurs, du bras, de la pompe et des vannes ;
- diagnostics et événements horodatés.

uXRCE-DDS est l'interface retenue pour le lot expérimental. Le banc emploie le
domaine ROS `42` et l'Agent Micro XRCE-DDS sur UDP 8888. `px4_msgs` doit
rester compatible avec la version du firmware. Le pont convertit explicitement
NED/FRD vers ENU/FLU sans altérer les données natives PX4. Port embarqué, débit,
QoS, fréquences et définitions finales `.msg/.srv/.action` sont **À valider**
sur le matériel exact.

### 8.1 Interfaces logiques préliminaires

| Interface | Producteur | Consommateurs | Cadence de travail |
|---|---|---|---:|
| points LiDAR / IMU / GNSS / images | adaptateurs capteurs | localisation, perception, enregistreur | capteur, **À valider** |
| `/localization/odom` et état | localisation | navigation, sûreté, pont PX4 | 20–100 Hz **À valider** |
| carte sémantique et terrain local | cartographie | planification, station | selon produit / ≥10 Hz local **À valider** |
| obstacles | perception | planificateur, sûreté | ≥10 Hz **À valider** |
| trajectoire | planificateur local | contrôleur/PX4 | ≥20 Hz **À valider** |
| états bras/pulvérisation | contrôleurs dédiés | mission, sûreté, station | cadence actionneur **À valider** |
| événements et diagnostics | tous composants | superviseur, enregistreur, station | événementiel + heartbeat |

Les flux continus utilisent des topics, les opérations longues et annulables des
actions, et les opérations atomiques des services. Toute commande d'actionneur
porte mission, origine, horodatage et durée de validité.

### 8.2 Repères

```text
earth -> map -> odom -> base_link
                          +-- fcu_link
                          +-- imu_link
                          +-- lidar_link
                          +-- camera_front_link
                          +-- gnss_link
                          +-- arm_base_link -> arm_tool_link -> buses
```

`map -> odom` porte la correction globale et ne doit pas créer un saut de
consigne dangereux ; `odom -> base_link` reste continu. Les extrinsèques sont
versionnées par configuration matérielle.

## 9. Configuration, observabilité et résultats

- Les configurations partagées résident dans `configs/` et utilisent unités SI
  et noms explicites.
- Un lancement archive commit, image, paramètres, calibrations, modèles et
  empreintes utiles.
- Un composant critique publie état, fraîcheur, fréquence, latence, identifiant
  de configuration et code défaut.
- Les résultats volumineux et rosbags restent hors Git ; leurs manifestes et
  empreintes assurent la traçabilité.
- Les secrets et clés ne sont jamais stockés dans le dépôt.

Le pont local de télémétrie expose `/api/health`, `/api/snapshot`, `/api/reset`
et `/api/replay` sur `127.0.0.1:8092`. Qt interroge au plus quatre fois par seconde
avec une seule requête active ; réponses obsolètes, invalides ou surdimensionnées
sont rejetées. Le contrat `drone_agricole.telemetry_snapshot.v1` borne
trajectoires, nuage, métriques, état PX4 et horodatage. Le rejeu est en lecture
seule et n'accepte que des chemins relatifs résolus sous `results/`, sans
traversée ni lien symbolique sortant. Ce pont n'arme ni ne lance aucune mission ;
`/api/reset` vide uniquement les buffers d'affichage et ne modifie ni PX4, ni les
résultats archivés.

La carte LiDAR directe est remise à zéro pour chaque exécution. Elle compacte
adaptativement l'ensemble des voxels au lieu d'abandonner la fin du trajet, puis
publie taille de voxel et nombre de compactions. Les repères initiaux de 8 cm,
250 000 voxels mémorisés et 16 000 points affichés restent **À valider**.

Chaque composant critique publie au minimum `STARTING`, `OK`, `DEGRADED`,
`ERROR` ou `STALE`, l'instant de sa dernière donnée valide, sa fréquence, sa
latence, l'identifiant de configuration et un code défaut borné. Le superviseur
évalue localisation, état PX4, fraîcheur de trajectoire, corridor, carte, bras,
actionneurs et géofence avant d'autoriser une action.

## 10. Stratégie de test

Les campagnes, mesures et statuts de qualification transversaux sont tenus dans
[DOC-VAL](../VALIDATION_QUALIFICATION.md). La présente section définit comment
les modules logiciels doivent être testés.

### 10.1 Niveaux

| Niveau | But | Exemples |
|---|---|---|
| unitaire | règle ou algorithme déterministe | projection, rangs, reconstruction, cycle de tâche |
| contrat | schémas, compatibilité et erreurs | catalogue, runners, résultats historiques |
| intégration | assemblage des modules | cartographie dashboard, télémétrie, processus |
| interface | navigation et rendu hors écran | pages Qt, fumée de l'exécutable |
| simulation | comportement ROS 2/PX4 et défauts | Offboard, perte liaison, délais, surcharge |
| embarqué | temps réel, ressources et thermique | rejeu 1× sur Jetson, capteurs réels |
| système | mission et retour à l'état sûr | simulation, banc sec, eau/traceur, vol progressif |

### 10.2 Règles

- Un module nouveau déclare ses entrées, sorties, erreurs, dépendances et tests.
- Les tests UI vérifient l'orchestration et la présentation, pas les calculs
  métier déjà testés en headless.
- Les campagnes sont reproductibles et liées à une configuration précise.
- Les tests d'architecture vérifient les dépendances de compilation interdites.
- Une réussite de processus et une finalisation correcte du résultat sont deux
  états distincts.
- La qualification `amd64` ne vaut pas qualification `arm64`.

### 10.3 Traçabilité active

| Exigence | Composant/algorithme | Test | Résultat |
|---|---|---|---|
| `SW-ARC-001` séparer UI et orchestration | application, process, presentation | `test_run_service`, `test_process_backend`, `test_station_navigation` | implémenté sous Windows |
| `SW-EXT-001` ajouter une capacité par contrat | catalog, runners, composition | `test_contract_registry`, `test_runner_registry` | implémenté |
| `SW-MAP-001` projeter la couleur sans masquer les erreurs | camera color fusion | `test_camera_color_fusion` | implémenté préliminaire |
| `SW-MAP-002` reconstruire avec diagnostics bornés | scan reconstruction, adaptateur FriûlBot, rejeu | `test_scan_reconstruction`, `test_vineyard_map`, `test_dashboard_mapping:surface` | 23 scans / 61 903 triangles sur une fenêtre réelle ; préliminaire, voir DOC-VAL |
| `SW-SAFE-001` ne pas usurper l'autorité PX4 | pont PX4/ROS 2 sur porteuse commune | scénarios SITL perte Offboard/compagnon, puis banc perte/redémarrage Orin NX et défaut d'alimentation selon DOC-ELEC | SITL partiel ; cible matérielle **À valider** |
| `SW-PORT-001` construire et exécuter sur ARM | conteneurs et runtime Orin NX 16 Go | CI `arm64`, rejeu 1×, ressources et thermique sur porteuse cible | **À valider** |

### 10.4 Portefeuille de données de validation

| Dataset | Usage | État |
|---|---|---|
| BotanicGarden `1006-03` | pipeline LIO et compatibilité historique | téléchargé, inspecté ; licence commerciale **À valider** |
| Newer College | référence LIO/SLAM extérieure | accès et licence non commerciale à traiter |
| ARD-VO | vignoble avec LiDAR/IMU/RTK | séquence et licence **À valider** |
| BACCHUS Long-Term | évolution saisonnière | accès et licence **À valider** |
| TEMPO-VINE | futur benchmark viticole Mid-360 | publication des données en attente |
| LaMole/Grospoli | pentes, terrasses, murs et rangs irréguliers | autorisation requise |
| EscaYard B7 | rangs et évaluation RTK sur produits géospatiaux | baseline intégrée ; historique pour les nouveaux parcours |
| FriûlBot Test 2 | fusion temporelle LiDAR–multispectral en vigne | baseline active de perception/cartographie |
| VineLiDAR | géométrie UAV LiDAR multi-date | public, non téléchargé |

M2DGR et Hilti restent différés jusqu'à stabilisation du banc. Les futurs
imports géospatiaux pourront s'appuyer sur GDAL, PROJ et PDAL derrière un
adaptateur explicite. Aucun flux, timestamp, repère ou pose manquant ne doit être
fabriqué pour rendre un dataset compatible. Les droits LaMole/Grospoli, les
rangs courbes, les corridors et les critères SITL restent **À valider**.

Le catalogue machine-lisible `datasets/manifests/catalogue_datasets.yaml` porte
URLs, licences, empreintes, sous-ensembles et politiques d'isolation. Il prévaut
sur ce résumé. Un dataset n'est `ready` que si source, droits, taille,
empreinte, capteurs, calibration, vérité terrain et préparation reproductible
sont connus.

## 11. Extension d'une capacité

Une évolution suit ce chemin :

1. compléter le besoin et le scénario dans `DOC-HLD` si le comportement système
   change ;
2. mettre à jour le module, ses contrats et ses tests dans ce document ;
3. intégrer les choix structurants, alternatives utiles et conséquences dans le
   document vivant concerné ;
4. implémenter domaine/service/adaptateur puis présentation ;
5. lier l'exigence au test et au résultat ;
6. actualiser l'état `planifié`, `implémenté` ou `qualifié` ici, sans créer un
   compte rendu séparé.

Une extension n'introduit pas de plugin dynamique, bus global ou service réseau
supplémentaire sans besoin démontré. Une exécution réussie et la finalisation
correcte de son archive restent deux états distincts.

## 12. Feuille de route capacitaire

| Lot | Résultat attendu | État |
|---|---|---|
| T0 | contrats génériques, runners, historique, comparaison et rapports | implémenté préliminaire |
| B1 | `SurveyMissionPackage`, `SurveyRunPackage`, synchronisation et qualité d'acquisition | prochain lot ; planifié |
| B2 | trajectoire globale, nuage maître et fusion LiDAR–caméra | briques locales préliminaires |
| B3 | terrain, sémantique, entités, graphe et confiance | planifié |
| B4 | carte approuvée, mission, planification et simulation | planifié |
| C1 | chargement carte, LIO et recalage du drone de traitement | planifié |
| C2 | terrain local, obstacles, ESDF, corridor et plan local | planifié |
| C3 | mission autonome, transitions, reprise et défauts | planifié |
| D1 | bras sans liquide, déploiement et blocage | planifié |
| D2 | ciblage, eau/traceur, débit, dose et compte rendu | planifié |
| D3 | protocole agronomique autorisé et compensation air/downwash | planifié |
| E1 | campagnes système et qualification | planifié |

Chaque lot franchit une porte mesurable : acquisition intègre, géométrie
reproductible, sémantique qualifiée, carte cohérente, mission sans collision,
temps réel Jetson, puis traitement sûr. Les critères détaillés et résultats de
campagne relèvent de [DOC-VAL](../VALIDATION_QUALIFICATION.md).

## 13. Références et historique consolidés

- Les principes d'évolutivité et de navigation sont définis aux sections 2, 4
  et 11 ; la chaîne cartographique et la scène 3D le sont à la section 6.
- Les résultats et limites des anciennes campagnes sont consolidés dans
  [DOC-VAL](../VALIDATION_QUALIFICATION.md).
- La configuration de compilation effective dans `software/cpp/CMakeLists.txt`
  prévaut sur les anciennes arborescences décrites dans les documents gelés.

## Journal de modifications

| Date | Modification |
|---|---|
| 24 septembre 2026 | cible de déploiement Orin NX 16 Go et Pixhawk 6X module sur porteuse Holybro ; frontière PX4/ROS 2 maintenue, interface et défauts à valider sur matériel |
| 13 septembre 2026 | consolidation des décisions actives de déploiement, contrats, télémétrie, PX4, cartographie et extension ; retrait du registre ADR |
| 10 septembre 2026 | configuration VS Code pour ouvrir `software/cpp` directement ; configuration et compilation Debug vérifiées via les tâches locales |
| 10 septembre 2026 | consolidation des architectures, contrats, algorithmes, modules/tests, datasets et feuille de route historiques |
| 10 septembre 2026 | variante d'assemblage et surface : contrats, limites, contrôles ICP, export PLY et parcours de rejeu documentés après essai réel |
