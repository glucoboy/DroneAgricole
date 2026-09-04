# Contexte de référence

Dernière mise à jour : 5 septembre 2026.

## Vision

Développer deux drones complémentaires pour des vignobles à forte pente, en terrasses ou à géométrie irrégulière :

- un **drone cartographe** construit une carte 3D et sémantique de la parcelle ;
- un **drone de traitement** exploite cette carte et sa perception locale pour naviguer dans l'inter-rang et traiter latéralement la végétation au moyen d'un organe vertical rétractable.

L'application desktop Qt est la **station de mission métier unifiée**. Elle doit accompagner tout le cycle hors vol : réception des acquisitions du cartographe, compilation et construction de la carte, édition des informations métier, approbation/signature, préparation et transfert vers le drone de traitement, récupération de ses données puis génération du rapport de traitement.

## Décisions actives

- PX4 conserve les boucles de vol, la stabilisation et les fonctions critiques.
- ROS 2 gère perception, cartographie, navigation avancée, mission et traitement, sans commander directement les moteurs.
- L'ADR-0006 impose C++17 à la logique exécutable propriétaire et Qt 6 Widgets aux interfaces graphiques, avec un maximum de structure dans des fichiers `.ui`.
- L'ADR-0007 définit l'application desktop comme la station de mission unifiée. La simulation devient l'un de ses modules ; elle n'est plus la finalité unique de l'application.
- La coque Qt orchestre les workflows et les portes opérateur. Les importateurs, compilateurs, constructeurs de carte, validateurs, transferts et générateurs de rapport restent des modules C++17 headless indépendants de Qt Widgets.
- Une carte approuvée est immuable. Toute édition crée une nouvelle version candidate ; son approbation doit être liée à l'empreinte du contenu. Le mécanisme de signature et le transport vers le drone restent **À valider**.
- Le poste de développement est sous Windows 11, avec WSL2 et Docker Desktop.
- Le poste Windows/WSL/Docker et l'accès GPU depuis un conteneur CUDA ont été validés le 18 août 2026.
- Le PC dispose d'une NVIDIA RTX 5060 Ti pour la perception, l'entraînement et les benchmarks.
- La cible embarquée est la famille Jetson Orin ; Orin Nano Super 8 Go sert de référence prototype et Orin NX 16 Go reste une option pour le cartographe.
- L'environnement de référence est conteneurisé et multiarchitecture `linux/amd64` / `linux/arm64`.
- ROS 2 Humble/Ubuntu 22.04 est isolé pour les LIO et les datasets ; ROS 2 Jazzy/Ubuntu 24.04 est isolé pour les ponts de simulation modernes.
- PX4 SITL et Gazebo Harmonic s'exécutent dans une troisième image officielle séparée, provisoirement épinglée à `v1.18.0-beta2`.
- Les bases ROS Humble et Jazzy, PX4/Gazebo `x500` et le transport UDP vers Windows ont été validés le 18 août 2026.
- Les candidats LIO initiaux sont FAST-LIO2, Point-LIO et LIO-SAM.
- FAST-LIO2, Point-LIO et LIO-SAM sont intégrés à des révisions figées dans les images ROS 2 Humble `drone-agricole/fast-lio2:1.0.0`, `drone-agricole/point-lio:1.0.0` et `drone-agricole/lio-sam:1.0.0`.
- Le passage FAST-LIO2 corrigé du 19 août 2026 reçoit et synchronise `5 762 / 5 762` scans, puis publie `5 758` odométries. Il obtient `0,3592 m` d'ATE translation, `1,6716°` d'ATE orientation et une RPE à 1 s de `0,04825 m / 0,59370°`. Il consomme `0,391` cœur en moyenne et `307,0 Mio` de RSS, à `0,9992×` effectif. Ces valeurs restent préliminaires.
- Le passage Point-LIO comparable reçoit et synchronise également `5 762 / 5 762` scans et publie `5 758` odométries. Il obtient `0,4994 m`, `1,5562°` et `0,04642 m / 0,58981°`, pour `0,337` cœur, `315,7 Mio` et `0,9980×`. FAST-LIO2 est meilleur en cohérence globale ; Point-LIO est légèrement meilleur localement et en orientation.
- À `0,8×`, la séquence complète produit 5 214 odométries pour 5 762 scans, soit 90,49 %, seulement +1,44 point par rapport à `1×`. Sur trois fenêtres dynamiques par vitesse, les moyennes sont 87,47 % à `0,8×` et 87,70 % à `1×`. La saturation CPU n'explique donc pas l'essentiel des sorties manquantes.
- La campagne `0,8×` comporte 16 essais complets. Le voxel 1,00 m dégrade l'ATE moyenne de 91 % ; le voxel 0,25 m l'améliore de 10 % mais coûte environ 19 % de CPU et 21 % de mémoire supplémentaires. Le réglage de référence reste 0,50 m.
- La sensibilité préliminaire montre qu'un voxel de 1,00 m double l'ATE par rapport à 0,50 m. Un voxel de 0,25 m coûte environ 24 % de CPU supplémentaire sans gain supérieur à la variabilité observée.
- L'application desktop Qt 6 affiche en temps réel le nuage 3D, la trajectoire estimée, la vérité terrain alignée, le CPU, la mémoire, l'ATE et l'état PX4 directement depuis ROS 2. Son interface principale est déclarée dans un fichier `.ui`. Les exécutions graphiques restent séparées des mesures headless de référence.
- FAST-LIO2 est instrumenté par un patch reproductible qui compte scans reçus, prétraités, synchronisés, rejetés, mises à jour d'état et odométries publiées. Le topic `/fast_lio2/pipeline_counters` est enregistré avec chaque nouveau résultat.
- La QoS de benchmark FAST-LIO2 est harmonisée avec Point-LIO : profondeur `100`, livraison fiable, délai DDS et contrôle de vidange. Le passage complet corrigé confirme `5 762 / 5 762` scans reçus et zéro perte inexpliquée.
- LIO-SAM ROS 2 officiel est figé au commit `08af3f32f01725372d4269838dc44c19c6d9e76b`, instrumenté et calibré pour le VLP-16/Xsens. Son passage complet reçoit `5 762 / 5 762` scans, publie `5 758` odométries, obtient `0,4121 m / 1,1383°` d'ATE et une RPE de `0,04174 m / 0,57086°`. Il consomme `1,601` cœur et `617,6 Mio`, à `0,99785×` effectif.
- Le début exact du passage complet contient sept IMU Xsens initiales dont le quaternion est nul. LIO-SAM les ignore désormais avec un avertissement, sans modifier le dataset. Le test de régression de 5 s reçoit `50 / 50` scans et publie `46` odométries. Le lanceur interrompt aussi immédiatement le rosbag si un composant critique s'arrête et nettoie proprement un arrêt manuel.
- La comparaison finale BotanicGarden à QoS harmonisée retient FAST-LIO2 comme baseline principale : meilleure ATE translation (`0,3592 m`) pour `0,391` cœur et `306,9 Mio`. LIO-SAM est le candidat précision grâce aux meilleures orientation et RPE, mais coûte `4,09×` le CPU et `2,01×` la mémoire de FAST-LIO2. Point-LIO reste la référence de sobriété calcul avec `0,337` cœur. Cette sélection de travail doit encore être répétée et validée sur Jetson et d'autres scènes.
- Le tableau de bord desktop archive les contrats T0 après chaque exécution et propose le bilan ATE/RPE/pipeline dans la fenêtre.
- Un rejeu ralenti est un outil diagnostique qui accorde davantage de temps processeur ; il n'est pas représentatif d'une navigation embarquée temps réel. Le passage opérationnel doit être obtenu à `1×` sur PC, puis à `1×` sur Jetson et enfin sur capteurs réels.
- BotanicGarden `1006-03` est le premier dataset retenu ; des sous-ensembles ROS 2 MCAP de cinq secondes ont été générés pour Velodyne/Xsens et Livox/BMI088.
- Le LiDAR RoboSense Airy est le candidat principal du cartographe ; Livox Mid-360/Mid-360S reste un candidat pour le drone de traitement. Ces choix ne sont pas encore figés.
- Les fils de palissage sont un danger critique et ne doivent jamais dépendre d'un seul capteur.
- La station de traitement produit hors ligne la carte de référence et les missions approuvées ; les drones conservent uniquement les fonctions nécessaires en temps réel.
- Le module de simulation de la station est le point d'entrée principal de toutes les simulations : lancement, arrêt, paramètres, direct, résultats, historique, rechargement et comparaison.
- Le lot T0.1 est implémenté : sept contrats métier versionnés, dont une définition de dataset séparée, sont publiés avec huit documents JSON Schema. Le registre choisit les séquences par capacités et prépare l'ajout d'autres datasets sans branche codée en dur.
- Les résultats LIO historiques et les résultats PX4 du lot A sont normalisés en lecture seule vers les contrats T0.1. Les adaptateurs ont été validés sur des résultats réels FAST-LIO2, Point-LIO, LIO-SAM et PX4 perte Offboard.
- Le lot T0.2 est opérationnel préliminaire : le tableau de bord consomme le catalogue générique, applique le profil `botanicgarden_velodyne_xsens` et résout uniquement cinq runners approuvés pour les trois LIO, le carré PX4 SITL et la perte Offboard. Tous les paramètres, chemins et entrées sont validés côté serveur, avec une seule exécution active.
- Les nouvelles exécutions écrivent nativement `run_request.json`, `t0_run_manifest.json`, `t0_metrics.json`, `artifacts.json` et `events.jsonl`. Les 15 tests T0.1/T0.2 de l'implémentation historique avaient validé les contrats avant le port ; leur couverture active est désormais reprise par la suite CTest/Qt Test C++ décrite dans DOC-26.
- La régression T0.2 intégrée du 30 août 2026 est réussie : le smoke test FAST-LIO2 reçoit et synchronise `49 / 49` scans et publie 45 odométries ; le carré PX4 atteint ses quatre segments puis atterrit ; la perte Offboard déclenche le failsafe et l'atterrissage automatique. Les cinq artefacts contractuels sont présents dans les trois résultats.
- Le lot T0.3 est opérationnel préliminaire. L'index reconstruisible retrouve 59 résultats, dont 52 LIO et 7 PX4, sans modifier les archives. Les neuf résultats LIO sans métriques restent visibles comme archives incomplètes.
- Le tableau de bord filtre l'historique par domaine, dataset, scénario, algorithme, date, statut et tag, ouvre une fiche avec métriques/événements/artefacts, puis recharge sans calcul les trajectoires LIO ou le parcours PX4. Une configuration n'est duplicable que si ses paramètres exacts sont archivés, et sa duplication ne lance aucun runner.
- Le lot T0.4 est opérationnel préliminaire. Le tableau de bord sélectionne deux à quatre archives, vérifie domaine, simulation, groupe, dataset/séquence ou scénario, puis compare métriques, paramètres, runners et versions disponibles. Il superpose les trajectoires et courbes compatibles et affiche ou exporte un rapport Markdown sans relancer les algorithmes.
- La comparaison historique des passages complets `2a31bc7f`, `6feb6ccc` et `7f42a0fa` retrouve les dix métriques communes et reproduit le classement du DOC-17. Les trois trajectoires et courbes sont lues séquentiellement pour borner la mémoire, puis conservées dans un cache mémoire.
- La porte T0 du DOC-20 est fermée au niveau opérationnel préliminaire : trois LIO et deux scénarios PX4 pilotables, historique rechargeable, comparaison compatible et rapport reproductible depuis le tableau de bord.
- La migration du code propriétaire actif est terminée au niveau source : application desktop Qt 6, contrats T0, historique, comparaison, adaptateur BotanicGarden, analyses et orchestration LIO, pont PX4 et runner SITL sont en C++17. Les sources Web/Python et les lanceurs shell/PowerShell remplacés ont été supprimés. La qualification `linux/arm64`, le vol SITL complet du nouveau pont et les campagnes LIO complètes restent **À valider** ; la traçabilité de clôture est dans DOC-26.
- SW0 est lancé et suivi dans DOC-29. Les presets CI Windows/Linux et le workflow de consolidation sont versionnés ; la suite Windows réussit 12/12 tests. Les images courantes FAST-LIO2, Point-LIO, LIO-SAM et Qt/ROS 2 ont été reconstruites et contrôlées en `linux/amd64`. L'exécution sur une forge reste **À valider**, car aucun dépôt distant n'est configuré.
- Les rejeux SW0 du carré et de la perte Offboard avec le port C++ sont réussis en SITL. Le second observe l'action PX4 environ 1,050 s après l'arrêt des consignes, puis l'atterrissage. Les archives T0 natives relient désormais explicitement la requête, ses paramètres exacts et le résultat. Ces résultats ne qualifient pas le vol réel.
- SW0 possède désormais une preuve exécutable `linux/arm64` du noyau propriétaire C++/ROS 2 : image `sha256:1901e9e1095eae4290e596b1f63a7af9b9769366763f8d42c4a32e54dbfc769a`, architecture inspectée et CLI exécutée. Le patch reproductible LIO-SAM déclare `rcutils` directement et franchit la configuration qui échouait auparavant.
- La compilation LIO-SAM arm64 isolée avec un seul travail CMake porte encore WSL à environ 7,2 Go et coupe Docker sous QEMU. Après redémarrage, l'environnement a été récupéré sans perte de données par renommage réversible des répertoires de sockets, désactivation de Docker AI et conservation d'une sauvegarde de configuration. L'image Qt/LIO arm64 et JetPack doivent être qualifiées sur un hôte arm64 natif. Le recontrôle Windows reste conforme à 12/12 tests.
- Trois rejeux courts post-migration de FAST-LIO2 et trois de LIO-SAM ont été exécutés à `1×` dans les images `linux/amd64` courantes. Tous terminent et produisent des métriques ; la variabilité d'initialisation et de comptage observée sur cinq secondes interdit toutefois de considérer la répétabilité quantitative comme acquise. La campagne longue et ses seuils restent **À valider**.

## Workflow système accepté

Le DOC-19 maintient une station de traitement distincte sur le plan logique :

- le cartographe acquiert, contrôle et enregistre les données, avec FAST-LIO2 comme odométrie locale de travail ;
- la station produit hors ligne la trajectoire optimisée, la carte 3D/sémantique approuvée et la mission simulée ;
- le drone agricole charge cette carte, se relocalise et calcule en temps réel le corridor, la trajectoire locale et le traitement ;
- cinq contrats versionnés séparent les phases : `SurveyMissionPackage`, `SurveyRunPackage`, `VineyardMapPackage`, `TreatmentMissionPackage` et `MissionReportPackage`.

L'application Qt matérialise cette station logique sur le poste opérateur. Elle présente un workflow commun sans absorber les algorithmes dans le processus graphique : chaque étape reste exécutable et testable en mode headless derrière une interface C++.

Cette répartition et l'ADR-0004 ont été validées le 28 août 2026. L'ADR-0005 impose l'intégration au tableau de bord comme critère de fin de chaque lot.

## Banc de simulation initial

`VINEYARD_BENCH_V01` comporte dix scénarios : terrain plat régulier, rangs courbes, forte pente, terrasse, végétation dense, poteaux, fils, perte RTK, mouvement rapide et géométrie pauvre.

## État exécutable

- Point d'entrée : `compose.yaml`.
- Images de référence : `drone-agricole/ros-humble:1.0.0`, `drone-agricole/fast-lio2:1.0.0`, `drone-agricole/point-lio:1.0.0`, `drone-agricole/lio-sam:1.0.0`, `drone-agricole/qt-dashboard:1.0.0`, `drone-agricole/ros-jazzy-sim:0.1.0` et `drone-agricole/px4-ros:1.0.0`.
- Simulation : service `px4-sitl`, modèle `gz_x500`, monde `default`, mode headless.
- Adaptateur : exécutable C++ `drone-agricole-tools` avec commandes `inspect`, `prepare` et `export-tum`.
- L'adaptateur effectue une vraie conversion ROS 1 vers ROS 2, normalise les temps par point du VLP-16 et migre explicitement `livox_ros_driver/msg/CustomMsg` vers `livox_ros_driver2/msg/CustomMsg`.
- Station de mission : application desktop `drone-agricole-dashboard` — nom technique provisoire —, interface `software/cpp/ui/main_window.ui`, couche métier `software/cpp/include/drone_agricole/station/` et catalogue de simulations `configs/visualization/`. Les configurations `.vscode` lancent directement le binaire avec GDB ; aucun lanceur PowerShell n'est requis. Le service Compose `qt-dashboard-toolchain` fournit la construction Linux reproductible.
- Pont PX4–ROS 2 : Agent uXRCE-DDS 2.4.3, `px4_msgs` compatible, pont d'état ENU/FLU et essai Offboard doublement verrouillé. Le carré SITL et l'atterrissage PX4 sur perte Offboard ont été validés dans le lot A.
- Guides de reprise : DOC-09 à DOC-28 dans `docs/`. Les commandes de scripts conservées dans DOC-09 à DOC-24 sont historiques et sont remplacées par les commandes C++ de DOC-26.
- Contrats génériques du tableau de bord : `configs/visualization/schemas/`, registre datasets/simulations dans `configs/visualization/`, validateur C++ `ContractRegistry`, tests CTest et guide DOC-21.

## Principes non négociables

- Séparer clairement fonctions critiques PX4 et fonctions avancées ROS 2.
- Conserver les données capteurs brutes et horodatées.
- Tester d'abord en rejeu, puis SITL, HITL, banc physique et enfin en vol.
- Introduire progressivement le bras et le liquide : navigation seule, bras sans liquide, eau avec traceur, puis produit autorisé.
- Mesurer les performances au lieu de figer prématurément le calculateur ou l'algorithme.
- Piloter les simulations depuis le tableau de bord et conserver des résultats rechargeables, comparables et reproductibles.
- Conserver les paquets validés immuables et relier chaque approbation, transfert et rapport à leurs empreintes et versions sources.

## Prochaines actions

1. Terminer la consolidation SW0 suivie dans DOC-29 : état Git récupérable, CI Windows/Linux et documentation active alignée.
2. Terminer la matrice Qt/LIO `linux/arm64`, puis qualifier séparément JetPack sur Jetson.
3. Répéter FAST-LIO2 et LIO-SAM après migration avec des résultats comparables.
4. Organiser la migration existante en commits Git revus et raccorder le dépôt à une forge afin d'exécuter la CI distante.
5. Définir les schémas `SurveyMissionPackage`, `SurveyRunPackage` et `VineyardMapPackage` du lot B1 derrière les interfaces de la station.
6. Ajouter à l'interface Qt la navigation de la station : acquisitions, cartes, missions, transferts, opérations/rapports et simulations.
7. Auditer les flux caméra, timestamps et extrinsèques de BotanicGarden `1006-03` depuis la station.
8. Construire le premier `SurveyRunPackage` reproductible à partir du dataset.
9. Conserver en tâche de qualification les essais Jetson avant sélection matérielle définitive.
10. Valider manuellement l'apparition du `x500` dans QGroundControl.

## Questions ouvertes principales

- Géométrie définitive, masse et rétraction du bras vertical.
- Détection fiable des fils et définition du corridor de sécurité.
- Choix final des LiDAR, caméras et synchronisation temporelle.
- Suffisance de l'Orin Nano pour le cartographe complet.
- Modèle de dose, assistance d'air et compensation vent/downwash.
- Cadre réglementaire exact applicable à chaque phase d'essai et produit utilisé.
- Mécanisme de signature des cartes, gestion des identités et magasin de confiance.
- Transport et protocole définitifs entre la station et chacun des drones.
