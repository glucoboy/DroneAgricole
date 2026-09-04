# Software Architecture Document (SAD)

| Champ | Valeur |
|---|---|
| Référence | DOC-02 |
| Version | V0.2 |
| Date | 18 août 2026 |
| Statut | Préliminaire |
| Système | Drone Agricole — cartographie et traitement viticole |

## 1. Objet du document

Ce SAD décrit l'organisation logicielle cible, les responsabilités des composants, leurs interfaces, le déploiement et les mécanismes de sûreté. Les noms de topics, fréquences et budgets sont des propositions de travail tant qu'ils ne sont pas validés par un ADR et des essais.

L'ADR-0007 précise que l'application Qt constitue la station de mission métier unifiée. Le shell graphique compose les modules du workflow, tandis que leurs algorithmes restent headless et indépendants de Qt Widgets.

## 2. Attributs de qualité prioritaires

| Priorité | Attribut | Conséquence architecturale |
|---:|---|---|
| 1 | Sûreté | séparation PX4/ROS 2, états sûrs, supervision indépendante |
| 2 | Déterminisme temporel | fréquences et latences surveillées, files bornées |
| 3 | Observabilité | diagnostics, journaux, identifiant de configuration |
| 4 | Reproductibilité | conteneurs, paramètres versionnés, rejeu rosbag |
| 5 | Modularité | adaptateurs d'algorithmes et interfaces stables |
| 6 | Portabilité | images `amd64` et `arm64`, abstraction matériel |
| 7 | Maintenabilité | responsabilités courtes, tests et ADR |

## 3. Contexte logiciel

```text
                    +----------------------+
                    | Station sol / pilote |
                    +-----------+----------+
                                |
                         MAVLink / radio
                                |
+-------------+      +----------v----------+      +----------------+
| Capteurs    +----->+ Logiciel compagnon  +----->+ PX4 / FCU       |
| LiDAR/RGB/  |      | ROS 2               |      | contrôle de vol |
| RTK/IMU     |      +----------+----------+      +----------------+
+-------------+                 |
                                v
                    +----------------------+
                    | Bras, pompe, vannes, |
                    | capteurs de débit    |
                    +----------------------+
```

## 4. Frontière d'autorité

### 4.1 PX4 est responsable de

- acquisition des capteurs de vol et estimation primaire ;
- boucles d'attitude, vitesse et position ;
- mixage et commande moteurs ;
- armement/désarmement ;
- limites et failsafes de vol ;
- comportement minimal en cas de perte du compagnon.

### 4.2 ROS 2 est responsable de

- perception et fusion multi-capteurs avancée ;
- LIO/VIO/SLAM et carte sémantique ;
- planification globale et locale ;
- génération de trajectoires ou consignes acceptées par PX4 ;
- mission, bras et traitement ;
- supervision applicative et journalisation.

ROS 2 publie des consignes haut niveau ; PX4 conserve le droit de les refuser ou de basculer vers un comportement de secours.

## 5. Architecture en couches

```text
+-------------------------------------------------------+
| Mission et station sol                                |
+-------------------------------------------------------+
| Navigation | Cartographie | Traitement | Sécurité     |
+-------------------------------------------------------+
| Localisation | Perception | Modèle environnement      |
+-------------------------------------------------------+
| Adaptateurs capteurs | PX4 bridge | Actionneurs       |
+-------------------------------------------------------+
| ROS 2 / DDS | système Linux | NVIDIA runtime          |
+-------------------------------------------------------+
| Jetson / réseau / stockage / capteurs / FCU           |
+-------------------------------------------------------+
```

Les dépendances métier doivent aller vers les interfaces de couche inférieure, jamais vers l'implémentation concrète d'un algorithme tiers.

### 5.1 Architecture interne de la station desktop

La station utilise une architecture ports/adaptateurs : shell Qt `.ui`, couche application de workflow, domaine des paquets et adaptateurs de calcul, stockage ou communication. La bibliothèque `drone_agricole_station` ne dépend que de Qt Core. `MainWindow` ne contient ni construction de carte, ni signature, ni transfert, ni génération de rapport.

Le catalogue initial comprend réception cartographe, compilation, construction/édition/approbation de carte, préparation/simulation/transfert de mission, réception du retour et compilation du rapport. Seul le module de simulation possède actuellement un niveau opérationnel préliminaire ; les autres restent planifiés ou prototypes.

## 6. Composants et responsabilités

| Composant | Responsabilité | Criticité applicative |
|---|---|---|
| `sensor_manager` | démarrage, validation, timestamps et diagnostics capteurs | élevée |
| `calibration_manager` | charger et publier les calibrations versionnées | élevée |
| `px4_bridge` | états PX4 et consignes de trajectoire | critique à l'interface |
| `lio_adapter` | normaliser l'odométrie du LIO sélectionné | élevée |
| `localization_manager` | fusionner les sources et publier l'état autoritatif | élevée |
| `semantic_perception` | produire classes, objets et confiances | élevée |
| `terrain_model` | surface locale, pente et ruptures | élevée |
| `obstacle_tracker` | obstacles et prédictions locales | élevée |
| `map_builder` | construire carte 3D et sémantique | moyenne/élevée |
| `map_server_vineyard` | versionner et servir la carte de parcelle | élevée |
| `route_planner` | plan global et ordre des segments | moyenne |
| `local_planner` | corridor et trajectoire locale | élevée |
| `trajectory_controller` | convertir la trajectoire en consignes PX4 | élevée |
| `arm_controller` | séquencer, commander et surveiller le bras | élevée |
| `treatment_targeter` | associer cible et fenêtre temporelle | élevée |
| `spray_controller` | dose, pompe, vannes et retours capteurs | élevée |
| `airflow_controller` | assistance d'air et compensation | moyenne/élevée |
| `mission_manager` | machine à états de mission | élevée |
| `safety_supervisor` | invariants, préconditions, abandon applicatif | très élevée |
| `logger_recorder` | enregistrement et manifeste d'essai | élevée |
| `benchmark_runner` | campagnes reproductibles hors vol | non embarquée |

## 7. Processus et isolation

Le déploiement initial privilégie plusieurs processus ROS 2 afin qu'une panne de perception ne termine pas la mission ou le superviseur. La composition intra-processus pourra ensuite être appliquée aux flux lourds lorsque les gains et risques auront été mesurés.

Groupes pressentis :

```text
process_sensor       sensor_manager + pilotes qualifiés
process_localization lio_adapter + localization_manager
process_perception   semantic_perception + obstacle_tracker
process_mapping      terrain_model + map_builder/map_server
process_navigation   route_planner + local_planner
process_control      trajectory_controller + px4_bridge
process_treatment    arm + targeter + spray + airflow
process_safety       safety_supervisor seul
process_mission      mission_manager
process_logging      logger_recorder
```

Le superviseur doit pouvoir détecter la disparition d'un processus sans dépendre du processus surveillé.

## 8. Interfaces ROS 2 préliminaires

### 8.1 Topics capteurs normalisés

| Topic logique | Type indicatif | Fréquence indicative | QoS pressentie |
|---|---|---:|---|
| `/sensors/lidar/points` | `sensor_msgs/PointCloud2` | 10–20 Hz | sensor data, best effort |
| `/sensors/imu/data` | `sensor_msgs/Imu` | 100–400 Hz | sensor data, best effort |
| `/sensors/gnss/fix` | `sensor_msgs/NavSatFix` | 5–20 Hz | reliable, depth faible |
| `/sensors/gnss/status` | message projet | 5–20 Hz | reliable |
| `/sensors/camera/front/image` | `sensor_msgs/Image` | 15–30 Hz | sensor data |
| `/sensors/camera/front/info` | `sensor_msgs/CameraInfo` | à la connexion | transient local |

### 8.2 État et navigation

| Topic/action | Type indicatif | Producteur | Consommateur |
|---|---|---|---|
| `/localization/odom` | `nav_msgs/Odometry` | localisation | navigation, PX4 bridge |
| `/localization/status` | message projet | localisation | sécurité, mission |
| `/map/semantic` | message projet | map server | planification, station sol |
| `/terrain/local` | grille/élévation projet | terrain model | local planner |
| `/perception/obstacles` | objets 3D projet | obstacle tracker | planner, sécurité |
| `/navigation/trajectory` | trajectoire projet | local planner | trajectory controller |
| `/px4/state` | message adapté PX4 | px4 bridge | mission, sécurité |
| `/mission/execute` | action projet | station sol | mission manager |

### 8.3 Traitement

| Topic/action | Type indicatif | Rôle |
|---|---|---|
| `/arm/set_state` | action | déployer/rétracter avec résultat |
| `/arm/state` | message projet | position, courant, défaut, confiance |
| `/treatment/target` | message projet | pied/segment, côté, fenêtre temporelle |
| `/spray/setpoint` | message projet | débit par étage, pression, activation |
| `/spray/state` | message projet | débit mesuré, pression, défauts |
| `/airflow/setpoint` | message projet | puissance/orientation par étage |
| `/treatment/report` | message projet | dose et zone réellement appliquées |

Les noms définitifs, définitions `.msg/.srv/.action`, unités et tolérances seront figés après le premier prototype de simulation.

## 9. Services et actions

- Les flux continus utilisent des topics.
- Les opérations longues, annulables ou avec retour progressif utilisent des actions.
- Les lectures/écritures atomiques de configuration utilisent des services.
- Une action doit être annulable et posséder un timeout connu.
- Les commandes d'actionneur incluent identifiant de mission, horodatage, durée de validité et origine.

## 10. Repères TF préliminaires

```text
earth
└── map
    └── odom
        └── base_link
            ├── fcu_link
            ├── imu_link
            ├── lidar_link
            ├── camera_front_link
            ├── gnss_link
            └── arm_base_link
                └── arm_tool_link
                    ├── nozzle_left_1 ... n
                    └── nozzle_right_1 ... n
```

- `earth -> map` porte le géoréférencement.
- `map -> odom` corrige la dérive globale sans introduire de discontinuité locale non gérée.
- `odom -> base_link` fournit l'odométrie continue.
- Les extrinsèques capteurs sont statiques, versionnées et liées au numéro de configuration du drone.
- La position réelle du bras doit apparaître dans TF si le mécanisme n'est pas strictement binaire.

## 11. Modèle de carte

Entités minimales :

| Entité | Champs principaux |
|---|---|
| `VineyardMap` | version, repère, emprise, date, source, qualité globale |
| `TerrainPatch` | maillage/grille, pente, rugosité, confiance |
| `RowSegment` | géométrie 3D, largeur libre, sens autorisé, voisins |
| `VinePlant` | ID, pose, dimensions, volume, poteau associé, confiance |
| `Post` | ID, géométrie, matériau si connu, confiance |
| `WireZone` | segment/volume conservatif, hauteur, confiance |
| `Obstacle` | géométrie, classe, permanence, marge |
| `NoFlyZone` | géométrie, raison et période de validité |
| `TreatmentPrescription` | cible, dose, côtés/étages, contraintes |

Les formats de stockage doivent être versionnés et migrables. Les données volumineuses 3D peuvent être référencées par URI et checksum plutôt qu'imbriquées dans un seul message.

## 12. Machines à états

### 12.1 Cartographe

```text
BOOT -> SELF_TEST -> READY -> TAKEOFF -> MAPPING
                                      /    |    \
                                     v     v     v
                                  PAUSE  RETURN ABORT
                                           |
                                           v
                                         LAND
```

### 12.2 Traitement

```text
BOOT -> SELF_TEST -> READY -> TAKEOFF -> TRANSIT -> APPROACH
                                                     |
                                               DEPLOY_ARM
                                                     |
                                                 TREATMENT
                                                /    |    \
                                           ROW_END PAUSE ABORT
                                                \    |    /
                                                RETRACT_ARM
                                                     |
                                            NEXT_ROW / RETURN
```

Le traitement liquide n'est autorisé que dans `TREATMENT` et si toutes les gardes de sécurité sont vraies.

## 13. Contrats de santé et supervision

Chaque composant critique publie :

- état `STARTING`, `OK`, `DEGRADED`, `ERROR` ou `STALE` ;
- instant de la dernière donnée valide ;
- fréquence observée et latence estimée ;
- identifiant de configuration ;
- code défaut et détail borné.

Le `safety_supervisor` évalue notamment :

```text
localisation valide
AND état PX4 compatible
AND trajectoire fraîche
AND corridor libre
AND carte compatible
AND bras connu
AND actionneurs sains
AND géofence respectée
```

Si une condition nécessaire au traitement devient fausse, les vannes sont fermées avant toute autre action de mission.

## 14. Modes de défaillance principaux

| Défaillance | Détection | Réponse préliminaire |
|---|---|---|
| perte RTK | statut GNSS/innovations | poursuivre en local si qualifié, sinon pause/retour |
| odométrie LIO invalide | sauts, covariance, fréquence | geler traitement, stabiliser via PX4, abort |
| perception périmée | timestamp/fréquence | réduire vitesse ou arrêter l'approche |
| obstacle dans corridor | perception/carte | replanifier, stopper ou remonter selon stratégie |
| fil possible non confirmé | fusion multimodale/incertitude | corridor conservatif, interdiction de passage |
| bras non déployé | capteur position/courant | interdire traitement, rétracter ou atterrir |
| bras bloqué déployé | timeout/courant | arrêter produit, trajectoire d'urgence dédiée |
| perte pompe/pression | débit/pression | fermer vannes et journaliser |
| perte compagnon | heartbeat PX4 | failsafe PX4 configuré |
| température/calcul saturé | télémétrie système | dégrader perception, arrêter mission avant limite |

## 15. Configuration

- Paramètres communs dans `configs/` et packages ROS 2 dédiés.
- Aucun paramètre critique modifiable silencieusement en mission.
- Chaque lancement génère un manifeste avec commit Git, image Docker, paramètres, calibrations et hashes des modèles.
- Les paramètres physiques utilisent unités SI et noms explicites.
- Les secrets et clés ne sont jamais stockés dans le dépôt.

## 16. Journalisation et données d'essai

Un enregistrement de référence contient :

```text
run_manifest.yaml
configuration/
calibration/
rosbag/
events.jsonl
metrics/
report/
```

Le manifeste porte au minimum l'identifiant du drone, du scénario, du dataset, du logiciel, de la carte, de la mission et de l'opérateur/automate d'essai.

## 17. Conteneurs et construction

Images pressenties :

```text
drone-agricole-base:<ros-distro>
├── benchmark-lio
├── simulation-px4
├── cartographer-runtime
└── treatment-runtime
```

Chaque image cible `linux/amd64` pour le PC et `linux/arm64` pour Jetson lorsque les dépendances le permettent. Les composants liés à JetPack sont construits depuis une base NVIDIA compatible avec la version du pilote hôte.

## 18. Budgets préliminaires

Les budgets exacts seront mesurés par nœud. Les seuils de conception initiaux sont :

- aucune file critique non bornée ;
- aucune boucle de contrôle locale dépendante d'un traitement IA à latence non bornée ;
- marge CPU/GPU/RAM et thermique conservée en mission nominale ;
- arrêt ou dégradation avant saturation durable ;
- trajectoire locale mise à jour au moins à 20 Hz ;
- détection d'obstacle utile au moins à 10 Hz ;
- horodatage capteurs vérifié avant chaque mission.

## 19. Tests architecturaux obligatoires

- perte et retour de chaque flux capteur ;
- redémarrage d'un processus non critique ;
- arrêt du compagnon et vérification du failsafe PX4 ;
- surcharge CPU/GPU et température élevée simulées ;
- délais réseau, paquets perdus et données hors ordre ;
- perte GNSS en pente et dans un rang répétitif ;
- obstacle tardif avec bras déployé ;
- défaut pompe/vanne et fermeture sûre ;
- incompatibilité de version de carte ;
- rejeu déterministe d'un incident.

## 20. Organisation cible du logiciel

```text
software/
├── src/
│   ├── common_interfaces/
│   ├── sensing/
│   ├── localization/
│   ├── perception/
│   ├── mapping/
│   ├── navigation/
│   ├── treatment/
│   ├── safety/
│   └── mission/
├── third_party/
├── docker/
├── launch/
└── tests/
```

## 21. Décisions restant à formaliser par ADR

1. version Ubuntu/ROS 2 et DDS ;
2. méthode d'intégration PX4 ;
3. algorithme LIO de référence ;
4. format de carte et stockage 3D ;
5. stratégie de composition/processus ROS 2 ;
6. LiDAR/caméras et synchronisation ;
7. calculateur du cartographe ;
8. protocole d'actionneurs du bras et de pulvérisation ;
9. politique de détection des fils et marges ;
10. stratégie de mise à jour logicielle embarquée.
