# Logiciel

Ce dossier contient exclusivement le code exécutable propriétaire C++17, l'interface desktop Qt 6, les paquets ROS 2 C++ et leurs images Docker.

```text
software/
├── cpp/             application Qt 6, outils C++17 et tests CTest/Qt Test
├── docker/
│   └── Dockerfile
├── src/
│   ├── drone_agricole_px4_bridge/       paquet ament_cmake/rclcpp
│   └── livox_ros_driver2_msgs_compat/
└── third_party/     versions, correctifs et licences des dépendances intégrées
```

Les principales cibles du Dockerfile sont :

- `ros-humble` : base Ubuntu 22.04 / ROS 2 Humble pour BotanicGarden et les LIO ;
- `telemetry-bridge` : service C++ ROS 2 local qui alimente l'application Qt
  Windows sur `127.0.0.1:8092` ;
- `ros-humble-fastlio2` : FAST-LIO2 ROS 2 figé, ses dépendances et les messages Livox requis ;
- `ros-humble-qt-dashboard` : toolchain Qt 6/C++17, télémétrie ROS 2 et lecture des archives ;
- `ros-jazzy-sim` : base Ubuntu 24.04 / ROS 2 Jazzy avec `ros_gz_bridge` pour la simulation ;
- `ros-jazzy-px4` : pont, essai Offboard et runner PX4 en C++17/rclcpp.

Validation rapide :

```powershell
docker compose build telemetry-bridge fast-lio2 point-lio lio-sam qt-dashboard-toolchain
docker compose --profile lio run --rm botanicgarden-adapter drone-agricole-tools help
docker compose build px4-runner-api
```

La consolidation SW0 ajoute les presets `ci-windows` et `ci-linux` ainsi que le
workflow `.github/workflows/sw0-ci.yml`. Les résultats natifs d'un runner PX4
peuvent être contrôlés et archivés avec `drone-agricole-tools archive-result` :

```powershell
& .\build\ci-windows\software\cpp\drone-agricole-tools.exe archive-result `
  --request .\chemin\run_request.json `
  .\chemin\resultat
```

La commande valide la requête avant d'écrire les contrats T0 et refuse par
défaut d'écraser une archive native existante. Les résultats restent locaux et
ne doivent pas être ajoutés à Git.

FAST-LIO2 est figé dans `third_party/fast_lio2.yaml`. Son protocole BotanicGarden est décrit dans les documents DOC-10 et DOC-11.

L'analyse ATE/orientation/RPE, les synthèses de campagne et l'orchestration sont fournies par l'exécutable C++ `drone-agricole-tools`. La qualification répétée à `0,8×` est décrite dans DOC-13.

L'adaptateur migre explicitement le message LiDAR du dataset depuis `livox_ros_driver/msg/CustomMsg` vers `livox_ros_driver2/msg/CustomMsg`. Le paquet `livox_ros_driver2_msgs_compat` fournit dans le conteneur FAST-LIO2 les définitions ROS 2 officielles nécessaires aux rejeux hors ligne.

Le tableau de bord est l'exécutable natif `drone-agricole-dashboard`. La structure statique de la fenêtre se trouve dans `cpp/ui/main_window.ui` et reste modifiable avec Qt Designer, Qt Creator ou une extension Qt pour Visual Studio Code. Les widgets spécialisés de trajectoire et de métriques restent en C++. `TrajectoryView` fournit une carte 3D métrique navigable ; le pont C++ accumule `/cloud_registered` dans une carte voxelisée bornée pour conserver les observations LiDAR pendant le direct. Sous Windows, `LiveTelemetryStub.cpp` interroge ce pont avec Qt Network, et `RosbagTrajectoryReaderStub.cpp` l'utilise aussi pour relire les trajectoires historiques sans installation ROS 2 native. DOC-26 décrit l'arborescence active ; DOC-12 V0.2 reste la référence historique des besoins temps réel.
