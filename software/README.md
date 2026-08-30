# Logiciel

Ce dossier contient le socle ROS 2, les images Docker, les adaptateurs de datasets et leurs tests.

```text
software/
├── docker/
│   └── Dockerfile
├── src/
│   ├── drone_agricole_dataset_adapter/
│   └── livox_ros_driver2_msgs_compat/
├── visualization/ tableau de bord WebGL/ROS 2 local
├── tests/
├── third_party/     versions et licences des dépendances intégrées
└── launch/          lancements propres au projet, à ajouter au besoin
```

Les principales cibles du Dockerfile sont :

- `ros-humble` : base Ubuntu 22.04 / ROS 2 Humble pour BotanicGarden et les LIO ;
- `ros-humble-fastlio2` : FAST-LIO2 ROS 2 figé, ses dépendances et les messages Livox requis ;
- `ros-humble-fastlio2-visual` : extension locale avec le serveur du tableau de bord 3D ;
- `ros-jazzy-sim` : base Ubuntu 24.04 / ROS 2 Jazzy avec `ros_gz_bridge` pour la simulation.

Validation rapide :

```powershell
docker compose build ros-humble ros-jazzy-sim
docker compose run --rm ros-humble bash tools/verify/verify_ros2.sh
docker compose run --rm ros-jazzy-sim bash tools/verify/verify_ros2.sh
docker compose build fast-lio2
docker compose run --rm fast-lio2 bash -lc "ros2 pkg prefix fast_lio; ros2 pkg executables fast_lio"
```

FAST-LIO2 est figé dans `third_party/fast_lio2.yaml`. Son protocole BotanicGarden est décrit dans les documents DOC-10 et DOC-11.

L'image FAST-LIO2 contient également `rosbags==0.11.3` afin d'exécuter l'analyse ATE/orientation/RPE dans la même campagne Docker. La qualification répétée à `0,8×` est décrite dans DOC-13.

L'adaptateur migre explicitement le message LiDAR du dataset depuis `livox_ros_driver/msg/CustomMsg` vers `livox_ros_driver2/msg/CustomMsg`. Le paquet `livox_ros_driver2_msgs_compat` fournit dans le conteneur FAST-LIO2 les définitions ROS 2 officielles nécessaires aux rejeux hors ligne.

Le tableau de bord est lancé par `tools/visualization/start_fastlio_dashboard.ps1`. Le serveur valide un catalogue versionné, génère la configuration FAST-LIO2 effective et gère un unique essai lancé ou arrêté depuis la page. Son architecture, ses topics et la séparation entre rendu graphique et benchmark formel sont décrits dans DOC-12 V0.2.
