# DOC-26 — Clôture de la migration C++17 / Qt 6

- Version : V0.1
- Date : 31 août 2026
- Statut : migration source terminée ; qualification `arm64` et essais longs **À valider**
- Décision associée : ADR-0006

## 1. Résultat

Tout le code exécutable propriétaire actif est en C++17. L'unique interface opérateur est l'application desktop Qt 6 Widgets `drone-agricole-dashboard` ; il ne s'agit pas d'une application Web. La structure statique principale réside dans `software/cpp/ui/main_window.ui`, modifiable avec Qt Designer, Qt Creator ou une extension Qt pour Visual Studio Code. Seuls les widgets de trajectoire et de courbes, dont le rendu est dynamique, sont construits en C++.

Les implémentations Python/Web, les lanceurs shell et PowerShell, leurs tests remplacés, le dossier `.venv` et les caches associés ont été supprimés. Le dossier temporaire `.runtime`, qui contenait 6 048 632 903 octets de journaux PX4 et une copie d'inspection fournisseur, a également été retiré sans toucher à `datasets/` ni `results/`. Un audit des fichiers actifs, hors dépendances et sorties de construction, retrouve 66 fichiers C/C++ et aucun fichier `.py`, `.js`, `.ts`, `.html`, `.css`, `.sh` ou `.ps1`.

Les outils Python installés par ROS 2 ou `colcon` dans les images Docker restent des dépendances amont. Ils ne contiennent aucune logique métier propriétaire et ne remettent pas en cause l'ADR-0006.

## 2. Arborescence active

```text
DroneAgricole/
├── CMakeLists.txt                 projet C++17 racine
├── CMakePresets.json             presets desktop Debug/Release
├── .vscode/                      configuration CMake et lancement direct GDB
├── software/
│   ├── cpp/
│   │   ├── include/              API de la bibliothèque métier
│   │   ├── src/core/             contrats, résultats, datasets, analyses et runners
│   │   ├── src/ui/               comportement de l'interface Qt
│   │   ├── src/cli/              outils headless et client PX4
│   │   ├── ui/main_window.ui     mise en page principale éditable
│   │   └── tests/                tests CTest/Qt Test
│   ├── src/
│   │   ├── drone_agricole_px4_bridge/    paquet ROS 2 C++/rclcpp
│   │   └── livox_ros_driver2_msgs_compat/ messages déclaratifs
│   └── docker/Dockerfile         matrices ROS 2, LIO, Qt et PX4
├── configs/                      catalogues et contrats déclaratifs
├── docs/                         exigences, résultats et décisions
└── tools/datasets/               ressources déclaratives liées aux données
```

Les documents DOC-09 à DOC-24 conservent les protocoles et résultats historiques. Leurs références à des scripts supprimés ne sont plus des commandes actives ; leur remplacement est l'exécutable `drone-agricole-tools` décrit ci-dessous.

## 3. Exécutables

| Exécutable | Responsabilité |
|---|---|
| `drone-agricole-dashboard` | application desktop Qt 6 : exécution, direct, historique et comparaison |
| `drone-agricole-tools` | inspection/conversion BotanicGarden, analyse ATE/RPE, campagnes et orchestration LIO |
| `drone-agricole-tools telemetry-server` | pont local C++ en lecture seule entre ROS 2 Docker et Qt Windows |
| `drone-agricole-px4-client` | client C++ des deux scénarios PX4 SITL approuvés |
| `state_bridge` | pont d'état PX4 en lecture seule, conversions NED/FRD vers ENU/FLU |
| `offboard_test` | carré ou perte Offboard, doublement verrouillé et réservé à SITL |
| `runner_server` | API locale Qt Network pour lancer/arrêter les essais PX4 autorisés |

La séparation de sûreté est inchangée : PX4 assure le vol critique et ses failsafes ; ROS 2 fournit des consignes et fonctions avancées. Le dashboard ne commande jamais directement les moteurs.

## 4. Utilisation depuis Visual Studio Code

La configuration `.vscode` sélectionne `C:\msys64\ucrt64\bin\cmake.exe`, les presets CMake et `gdb.exe`. Dans **Exécuter et déboguer**, sélectionner `Dashboard Qt 6 — Debug` ou `Dashboard Qt 6 — Release`. La configuration lance le binaire via l'adaptateur C++ de VS Code, sans lanceur PowerShell propriétaire.

Une stratégie Windows de contrôle d'applications peut néanmoins bloquer n'importe quel exécutable local non approuvé, quel que soit le lanceur utilisé. `Set-ExecutionPolicy` ne modifie pas cette politique. Ce cas est distinct d'une erreur Qt, CMake ou VS Code et doit être autorisé par la politique de sécurité de la machine.

Équivalent en ligne de commande :

```powershell
C:\msys64\ucrt64\bin\cmake.exe --preset desktop-debug
C:\msys64\ucrt64\bin\cmake.exe --build --preset desktop-debug --parallel
& .\build\desktop-debug\software\cpp\drone-agricole-dashboard.exe --workspace .
```

## 5. Traçabilité de migration

| Exigence | Composant ou algorithme | Test | Résultat consolidé au 5 septembre 2026 |
|---|---|---|---|
| `ARCH-CPP17-001` — logique propriétaire en C++17 | projet CMake, `software/cpp`, paquet PX4 | audit d'extensions | 0 source propriétaire dans un langage exécutable hérité |
| `UI-QT6-001` — interface desktop Qt 6 | `MainWindow`, `main_window.ui` | `test_dashboard_smoke` | réussi sur Windows natif et dans l'image Qt/ROS 2 `linux/amd64` courante ; rendu OpenGL réel en conteneur **À valider** |
| `T0-CONTRACT-001` — contrats et catalogue compatibles | `ContractRegistry` | `test_contract_registry` | réussi sur Windows natif |
| `T0-HISTORY-001` — archives rechargeables | `ResultRepository`, `ResultAdapter` | `test_result_repository` | réussi sur Windows natif |
| `T0-COMPARE-001` — résultats comparables | `ComparisonService` | `test_comparison_service` | réussi sur Windows natif |
| `DATA-BG-001` — conversion BotanicGarden | `Ros1Bag`, `DatasetAdapter` | `test_ros1_bag`, conversion réelle de 0,5 s | test réussi et 210 messages MCAP produits |
| `LIO-TOOLS-001` — analyses et campagnes C++ | `TrajectoryAnalysis`, `BenchmarkSupport`, `LioOrchestrator` | tests trajectoire/benchmark, constructions ROS 2 et six smokes post-migration | tests Windows réussis et trois rejeux courts par moteur FAST-LIO2/LIO-SAM terminés ; campagne longue **À valider** |
| `OBS-TELEM-001` — télémétrie LIO visible pendant le rejeu | `LiveTelemetry`, `TelemetryBridge`, client Qt Network | `test_telemetry_bridge`, rejeu FAST-LIO2 de 5 s à 0,5× | conforme le 2 septembre 2026 : nuage, poses, compteurs, CPU et RSS reçus en direct |
| `OBS-MAP-001` — carte LiDAR cumulative, adaptative et navigable | `AdaptivePointMap`, `LiveTelemetry`, `TelemetryBridge`, `TrajectoryView`, `main_window.ui` | tests de carte, capture native, rejeux FAST-LIO2 de 5 et 30 s | conforme le 2 septembre 2026 : deux compactions sur 294 trames et couverture du début comme de la fin |
| `PX4-SAFE-001` — frontière PX4/ROS 2 préservée | `StateBridge`, `OffboardPlan`, `OffboardTest` | gtests PX4, carré et perte Offboard | tests Docker et deux scénarios SITL du port C++ réussis ; transposition hors SITL **À valider** |

## 6. Validations et limites

- configuration et compilation Release natives MSYS2 UCRT64 : réussies ;
- suite desktop Windows : douze tests sur douze réussis en Debug et Release ;
- image `drone-agricole/ros-humble:1.0.0` et commande `drone-agricole-tools help` : réussies ;
- conversion réelle BotanicGarden de 0,5 s : 210 messages, dont 200 IMU, 5 VLP-16 et 5 poses de vérité terrain ;
- image `drone-agricole/px4-ros:1.0.0` : construite, huit entrées de test réussies ;
- endpoint de santé du runner PX4 : réussi en conteneur.

La première reconstruction finale de `drone-agricole/qt-dashboard:1.0.0` avait
été interrompue par Docker Desktop sous un pic mémoire d'environ 7,7 Go. Cet
incident est conservé comme historique environnemental ; les cibles doivent être
construites séquentiellement sur cet hôte.

Mise à jour du 2 septembre 2026 : les images `ros-humble`, `fast-lio2`,
`point-lio` et `lio-sam` `1.0.0` ont été reconstruites séquentiellement avec le
pont C++. Le service local répond sur le port 8092 et un rejeu FAST-LIO2 a
fourni en direct 2 839 points, 46 poses estimées, 49 références, 49 scans,
46 odométries, la charge CPU et 155,3 Mio de RSS. Cette preuve remplace la
limite de reconstruction `linux/amd64` décrite au paragraphe précédent ;
`linux/arm64` reste **À valider**.

Mise à jour du 5 septembre 2026 : après récupération de Docker Desktop sans
suppression de données, les images FAST-LIO2, Point-LIO, LIO-SAM et Qt/ROS 2 ont
été reconstruites à l'état source courant en `linux/amd64`. Leurs exécutables ont
été contrôlés, l'application Qt a terminé son smoke hors écran et le pont de
télémétrie répond de nouveau `status=ok` sur le port 8092. Trois rejeux courts à
`1×` de FAST-LIO2 et trois de LIO-SAM terminent avec des métriques analysables ;
leur variabilité est détaillée dans DOC-29.

Restent **À valider** : l'image Qt/LIO `linux/arm64` sur hôte natif, les campagnes
LIO longues et leurs seuils, les performances Jetson, HITL et tout vol réel.
