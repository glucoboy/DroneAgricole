# DOC-25 — Migration C++17 / Qt 6 du tableau de bord desktop

- Version : V0.1
- Date : 31 août 2026
- Statut : migration source terminée ; qualifications complémentaires **À valider**
- Décision associée : ADR-0006
- Remplace : l'interface Web décrite dans DOC-12 et ses extensions T0, sans invalider les résultats archivés

## 1. Objet

Ce document trace l'application de la contrainte suivante : la logique exécutable propriétaire cible C++17 et les interfaces graphiques ciblent Qt 6 Widgets. La mise en page doit résider au maximum dans des fichiers `.ui` modifiables avec Qt Designer, Qt Creator ou une extension Qt pour Visual Studio Code.

La première livraison portait le point d'entrée principal du projet : le tableau de bord de simulation. La migration couvre désormais également l'adaptateur BotanicGarden, les analyses et campagnes LIO ainsi que le pont PX4–ROS 2. L'ancien couple serveur HTTP/page Web n'est plus présent.

## 2. Architecture livrée

Le projet CMake racine construit :

- `drone-agricole-dashboard`, application Qt 6 Widgets ;
- `drone-agricole-px4-client`, client réseau C++ verrouillé pour les deux essais PX4 SITL autorisés ;
- `drone-agricole-tools`, outil C++ des datasets, analyses et campagnes LIO ;
- `drone_agricole_core`, bibliothèque C++ des contrats, runners, archives, rechargements, comparaisons et télémétrie ;
- douze tests CTest/Qt Test, dont le contrat de télémétrie, la carte adaptative, la carte 3D et un démarrage de l'application sans écran.

Le paquet `software/src/drone_agricole_px4_bridge` ajoute trois exécutables ROS 2 C++ : `state_bridge`, `offboard_test` et `runner_server`.

La fenêtre principale est décrite dans `software/cpp/ui/main_window.ui`. Elle contient les trois espaces validés par T0 : exécution, historique et comparaison. Les formulaires, boutons, tableaux, onglets, menus, splitters et panneaux statiques sont déclaratifs. Le C++ reste limité aux comportements, aux paramètres réellement dynamiques et aux deux widgets spécialisés de tracé.

La télémétrie ROS 2 est intégrée directement au processus Qt lorsque les dépendances ROS 2 sont disponibles. Sur le poste Windows MSYS2, où `rclcpp` n'est pas présent, le service Docker C++ `telemetry-bridge` porte les abonnements ROS 2 et expose des instantanés JSON bornés sur `127.0.0.1:8092`; Qt les lit avec Qt Network. Il consomme les poses LIO, la vérité terrain, la carte LiDAR voxelisée cumulative, les métriques de ressources, les compteurs de pipeline et l'état PX4. `TrajectoryView` affiche ces données dans une carte 3D métrique navigable. Il ne s'agit pas d'une application Web et aucun navigateur ni WebSocket n'est requis.

La séparation de sûreté reste inchangée : l'application demande un essai autorisé ; ROS 2 transmet les consignes avancées ; PX4 conserve le vol critique, les failsafes et l'atterrissage. L'application ne commande jamais directement les actionneurs.

## 3. Compatibilité T0 démontrée

La migration lit les archives existantes sans les réécrire. Les tests exécutés dans l'image ROS 2 Humble / Qt 6.2.4 vérifient :

| Chaîne | Composant C++ | Test | Résultat du 30 août 2026 |
|---|---|---|---|
| Contrats et catalogue T0.1/T0.2 | `ContractRegistry` | `test_contract_registry` | réussi |
| Runners approuvés et arrêt PX4 | `RunnerRegistry`, client PX4 | `test_runner_registry` | réussi |
| Historique T0.3 | `ResultRepository`, adaptateurs | `test_result_repository` | 59 résultats, 0 invalide |
| Comparaison T0.4 | `ComparisonService` | `test_comparison_service` | dix métriques communes reproduites |
| Construction `.ui` et initialisation | `MainWindow` | `test_dashboard_smoke` | réussi |

Bilan initial du tableau de bord : **5/5 tests réussis** sur `linux/amd64 + ROS 2 Humble + Qt 6.2.4` et Windows 11 natif. La suite globale contient désormais douze tests desktop et trois cibles gtest PX4. Les résultats de clôture actualisés sont consignés dans DOC-26 et DOC-27. La construction `linux/arm64` reste **À valider**.

## 4. Construction et édition de l'interface

Les presets `desktop-debug` et `desktop-release` sont exposés dans `CMakePresets.json`. Qt Creator peut ouvrir le `CMakeLists.txt` racine et sélectionner directement un preset. Dans Visual Studio Code, une extension Qt/Designer peut ouvrir le fichier `.ui`, tandis que CMake Tools utilise les mêmes presets.

Prérequis natifs :

- compilateur C++17 et CMake 3.22 ou supérieur ;
- Qt 6 avec Widgets et OpenGLWidgets ;
- `yaml-cpp` ;
- ROS 2 et ses messages pour le service Docker de télémétrie et le rechargement rosbag complets ; la construction Windows utilise le client Qt Network du pont local.

Qt 6.2.4 est la version effectivement compilée et testée dans l'image Linux reproductible. Sous Windows, la chaîne validée utilise les paquets MSYS2 UCRT64 et Qt 6.11.2. Le lanceur détecte automatiquement l'installation standard `C:\msys64\ucrt64`. La version minimale sur Windows et `linux/arm64` reste **À valider**.

## 5. Lancement

Depuis Visual Studio Code, choisir `Dashboard Qt 6 — Debug` dans **Exécuter et déboguer**. La tâche versionnée configure et compile avec MSYS2, puis l'adaptateur C++ lance directement l'application avec GDB.

Depuis un terminal :

```powershell
C:\msys64\ucrt64\bin\cmake.exe --preset desktop-debug
C:\msys64\ucrt64\bin\cmake.exe --build --preset desktop-debug --parallel
& .\build\desktop-debug\software\cpp\drone-agricole-dashboard.exe --workspace .
```

La fermeture s'effectue normalement avec la fenêtre. Les backends Docker restent séparés de l'application ; le runner autorisé peut les démarrer automatiquement lorsqu'une simulation le nécessite.

La construction Linux/ROS 2 reproductible est portée par le service Compose `qt-dashboard-toolchain` et l'image `drone-agricole/qt-dashboard:1.0.0`. Ce service sert à construire et tester ; il ne remplace pas la fenêtre desktop native.

## 6. État de la migration globale

Le tableau de bord, ses contrats, son historique, sa comparaison, son client PX4, sa télémétrie, l'adaptateur BotanicGarden, l'analyse de trajectoire, les synthèses de campagne, l'orchestration LIO et le pont PX4–ROS 2 sont portés en C++17. L'ancienne interface Web, les modules Python, les environnements virtuels et les lanceurs propriétaires remplacés ont été retirés.

Le dépôt ne contient plus de fichier source propriétaire `.py`, `.js`, `.ts`, `.html`, `.css`, `.sh` ou `.ps1`. Les outils Python éventuellement installés dans les images ROS restent des dépendances de construction amont et ne portent aucune logique métier du projet.

La migration est donc terminée au niveau source. Cela ne valide pas automatiquement les campagnes longues, `linux/arm64`, le matériel Jetson ou un vol réel ; ces qualifications restent **À valider** dans DOC-26.

## 7. Critères de fermeture

La fermeture au niveau source est acquise. Les critères de qualification restants sont :

- rejouer les campagnes de référence longues et confirmer les mêmes contrats et métriques ;
- valider `linux/arm64` et le poste Jetson retenu ;
- rejouer les essais PX4 en SITL avec le paquet C++ avant toute étape HITL ;
- conserver la traçabilité `exigence -> composant/algorithme -> test -> résultat` de DOC-26.
