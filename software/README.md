# Logiciel

Ce dossier contient exclusivement le code exécutable propriétaire C++17, l'interface desktop Qt 6, les paquets ROS 2 C++ et leurs images Docker.

Avec VS Code, ouvrir la racine du projet ou seulement `software/cpp` est pris
en charge. La configuration locale de `cpp/.vscode/` pointe vers la racine
CMake, deux niveaux plus haut, et utilise les mêmes profils et dossiers de
compilation. Sous Windows, `Ctrl+Maj+B` configure et compile en Debug ; `F5`
lance le dashboard avec le débogueur. Les extensions CMake Tools et C/C++ sont
nécessaires pour leurs fonctions respectives. Le fichier CMake de `cpp` reste
un sous-projet : les commandes de terminal utilisant `--preset` doivent être
exécutées depuis la racine du dépôt.

La cible `drone-agricole-dashboard` construit également ses exécutables de
traitement et le client PX4 dans le même profil. Cela évite de lancer un outil
Release ancien depuis une interface récemment recompilée.

Depuis la refonte du 9 septembre 2026, les sources de `cpp/src/` sont séparées en
`application/`, `algorithms/`, `adapters/`, `composition/`, `support/` et `ui/`.
Les pages Qt consomment les services ; le cycle des traitements est partagé
avec la commande `drone-agricole-tools station-run --request chemin.json`.
Les en-têtes historiques `core/` et la cible de compatibilité du même nom
restent disponibles. [DOC-SW](../docs/architecture/ARCHITECTURE_LOGICIELLE.md)
décrit les frontières, l'ajout d'une fonction, les tests et les limites.

L'interface propose une navigation latérale, un historique de navigation et
un suivi permanent du traitement. Le shell et chaque page possèdent leur
fichier `.ui` ; les styles communs sont dans `cpp/resources/station.qss`.

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

FAST-LIO2 est figé dans `third_party/fast_lio2.yaml`. Son protocole BotanicGarden et ses résultats synthétiques sont tenus dans `DOC-VAL`.

L'analyse ATE/orientation/RPE, les synthèses de campagne et l'orchestration sont fournies par l'exécutable C++ `drone-agricole-tools`. La qualification répétée à `0,8×` est décrite dans `DOC-VAL`.

L'adaptateur migre explicitement le message LiDAR du dataset depuis `livox_ros_driver/msg/CustomMsg` vers `livox_ros_driver2/msg/CustomMsg`. Le paquet `livox_ros_driver2_msgs_compat` fournit dans le conteneur FAST-LIO2 les définitions ROS 2 officielles nécessaires aux rejeux hors ligne.

La station est l'exécutable natif `drone-agricole-dashboard`. Le shell se trouve dans `cpp/ui/main_window.ui` et les pages dans les fichiers voisins, modifiables avec Qt Designer, Qt Creator ou une extension Qt pour Visual Studio Code. Les widgets spécialisés de trajectoire et de métriques restent en C++. `TrajectoryView` fournit une carte 3D métrique navigable ; le pont C++ accumule `/cloud_registered` dans une carte voxelisée bornée pour conserver les observations LiDAR pendant le direct. Sous Windows, `adapters/runtime/HttpLiveTelemetry.cpp` interroge ce pont avec Qt Network et `HttpTrajectoryReader.cpp` relit les trajectoires historiques sans installation ROS 2 native. `DOC-SW` décrit l'arborescence active et `DOC-VAL` tient les preuves et limites de qualification.
