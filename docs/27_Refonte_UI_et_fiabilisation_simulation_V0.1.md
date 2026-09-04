# Refonte de l'interface et fiabilisation du lancement des simulations

- Version : V0.1
- Date : 2 septembre 2026
- Statut : opérationnel préliminaire
- Décisions associées : ADR-0006, ADR-0008

## Objectif

Cette évolution rapproche l'application desktop Qt du niveau de finition de l'ancien prototype Web, améliore la lisibilité de tous les états et supprime le démarrage Docker manuel comme prérequis d'un essai PX4 lancé depuis le tableau de bord.

## Interface Qt 6

La structure statique reste concentrée dans `software/cpp/ui/main_window.ui`, donc éditable avec Qt Designer, Qt Creator ou une extension Qt pour Visual Studio Code. La refonte apporte :

- une hiérarchie visuelle claire entre l'en-tête, la préparation, la vue opérationnelle, l'historique et la comparaison ;
- des cartes et contrôles plus espacés, avec états de survol, focus, sélection et désactivation explicites ;
- une palette sombre à texte principal clair et texte secondaire renforcé ;
- des couleurs de succès, d'erreur et de sélection qui imposent leur couleur de texte ;
- une harmonisation des vues de trajectoire et de métriques avec la même palette ;
- une barre de progression d'exécution définie dans le fichier `.ui`, alimentée par les étapes du runner LIO ;
- une capture de diagnostic C++ par l'option `--screenshot`, sans ajouter de dépendance ou de logique métier hors C++17.

Les contrastes ont été contrôlés sur une capture Qt rendue à 1480 × 920. La validation d'accessibilité formelle avec plusieurs écrans et facteurs d'échelle reste **À valider**.

## Lancement PX4 depuis l'application native

Trois défauts indépendants empêchaient ou fragilisaient le lancement :

1. le conteneur `px4-runner-api` encore présent provenait de l'ancienne image et tentait de lancer le serveur Python supprimé ;
2. l'URL `http://px4-runner-api:8091` n'était résoluble que dans le réseau Compose, pas depuis l'application Windows ;
3. les valeurs ROS 2 de type `double` qui avaient une valeur entière étaient sérialisées sous la forme `1` ou `2`, puis refusées comme paramètres de type entier.

Les corrections durables sont les suivantes :

- image `drone-agricole/px4-ros:1.0.0` et serveur C++ `runner_server` ;
- publication limitée à `127.0.0.1:8091` et URL native par défaut `http://127.0.0.1:8091` ;
- résolution du client PX4 à côté de l'exécutable du dashboard ;
- vérification de l'API par le client C++ et démarrage automatique du profil Docker SITL local si nécessaire ;
- sérialisation ROS 2 conservant explicitement le type décimal, par exemple `1.0`.

Le double verrou reste inchangé : l'environnement impose `DRONE_AGRICOLE_SITL=1` et l'essai Offboard exige toujours `execute:=true` dans le runner autorisé. PX4 conserve le vol critique et les failsafes ; ROS 2 fournit les consignes avancées.

## Lancement LIO depuis l'application native

Le message `Structure inattendue dans la configuration LIO` provenait du parcours mutable des nœuds `yaml-cpp`. L'affectation utilisée pour descendre dans l'arbre YAML pouvait modifier un nœud partagé au lieu de seulement déplacer le curseur de parcours. La première substitution de paramètre réussissait, puis la structure attendue n'était plus disponible pour les suivantes.

Deux défauts supplémentaires apparaissaient ensuite au lancement effectif depuis le dashboard :

1. l'interface créait le dossier final et y écrivait `run_request.json` avant de lancer le runner, alors que le contrat du runner interdit d'écraser un dossier existant ;
2. les valeurs décimales entières des configurations LIO, notamment `blind: 1.0` et `det_range: 100.0`, étaient réémises comme des entiers et refusées par ROS 2.

Les corrections durables sont les suivantes :

- parcours récursif des nœuds YAML sans réaffectation du nœud parent ;
- diagnostic indiquant désormais le chemin exact d'une clé absente ou d'une section non structurée ;
- création du dossier final réservée au runner ; la requête et les contrats T0 ne sont écrits qu'après une exécution réussie ;
- absence d'archivage T0 trompeur après un code de sortie en échec ;
- conservation du type numérique défini par la configuration YAML de base, y compris lorsque la valeur décimale est entière ;
- décodage UTF-8 des sorties du runner dans le journal Qt sous Windows ;
- remontée d'une étape et d'un pourcentage toutes les cinq secondes pendant le rejeu, puis pendant le drainage, la production des artefacts et l'analyse ;
- test de génération de la configuration d'exécution pour FAST-LIO2, Point-LIO et LIO-SAM ;
- images LIO alignées sur les références `1.0.0` déclarées dans `compose.yaml` ;
- accès aux dépôts GitHub forcé en HTTP/1.1 pendant les builds Docker, le transport HTTP/2 du poste interrompant les clonages ;
- republication périodique des compteurs Point-LIO afin que le contrôle de fin de pipeline puisse lire l'état final après le rejeu.

Les paramètres algorithmiques et les commits amont figés restent inchangés.

## Pont de télémétrie C++ pour l'application Windows

La première migration Qt avait porté les abonnements ROS 2 en C++, mais la
construction Windows MSYS2 sélectionnait encore un adaptateur vide car elle ne
dispose pas de `rclcpp`. La progression textuelle du runner restait visible,
mais elle ne remplaçait ni le nuage, ni les trajectoires, ni les compteurs en
direct.

Le service Compose `telemetry-bridge` exécute désormais
`drone-agricole-tools telemetry-server` dans ROS 2 Humble. Son API HTTP JSON
locale est limitée à `127.0.0.1:8092` : santé, instantané et remise à zéro des
buffers d'affichage. Le client Qt Network interroge au plus quatre fois par
seconde, refuse un schéma inconnu, borne les tableaux et marque la liaison
indisponible après 1,5 seconde sans réponse. Le badge de l'interface affiche
`DIRECT` seulement lorsque ces instantanés sont frais ; sinon il affiche
`EN ATTENTE` avec un contraste distinct.

Le pont est passif vis-à-vis du véhicule : il ne publie aucune consigne de vol
et ne commande aucun actionneur. La route de remise à zéro ne touche qu'aux
buffers d'affichage. PX4 conserve le vol critique et ses failsafes.

## Carte 3D interactive et accumulation LiDAR

La vue opérationnelle utilise désormais une caméra perspective persistante.
L'opérateur peut tourner autour de la carte, se déplacer dans son plan, zoomer,
revenir au cadrage automatique ou choisir une vue de dessus. La grille
métrique, la boussole, l'échelle, les axes, les extrémités de trajectoire et les
halos contrastés rendent la géométrie lisible même lorsque le nuage est dense.
Les boutons statiques de cadrage et de vue de dessus restent déclarés dans
`main_window.ui`.

Le pont ne remplace plus le nuage précédent. Il intègre chaque
`/cloud_registered` dans une carte voxelisée et bornée, remise à zéro au début
d'une exécution. Le rejeu de validation
`map_accumulation_validation_20260902` a intégré 46 trames dans 39 543 voxels
et transmis 13 181 points représentatifs au widget. Les seuils de l'ADR-0009
restent **À valider** sur une séquence longue et sur Jetson.

Une première exécution longue a ensuite atteint exactement 250 000 points
après 1 649 trames : l'ancienne protection refusait alors tous les nouveaux
points et privilégiait le début du trajet. La stratégie a été remplacée par
une compaction adaptative testée avec
`map_adaptive_compaction_validation_20260902`. Sur la fenêtre dynamique de
30 secondes, la carte a compacté deux fois, de 8 à 16 puis 32 cm, et terminé à
103 290 représentants après 294 trames. L'instantané final conserve 993 points
à moins de 8 m du départ et 869 à moins de 8 m de la dernière pose : le début
et la fin restent donc tous les deux représentés.

## Traçabilité

| Exigence | Composant / algorithme | Test | Résultat |
|---|---|---|---|
| UI-REQ-027 — interface moderne et lisible | `main_window.ui`, `MainWindow`, `TrajectoryView`, `MetricsPlotWidget` | génération UIC, compilation native, test smoke hors écran, capture 1480 × 920 | Conforme sur le poste de développement |
| UI-REQ-028 — structure éditable dans les outils Qt | `main_window.ui` | génération automatique UIC pendant le build CMake | Conforme |
| UI-REQ-029 — naviguer dans une carte 3D métrique et garder les trajectoires lisibles | `TrajectoryView`, `main_window.ui` | `test_trajectory_view`, capture native 960 × 620, rotation/déplacement/zoom/cadrage/vue de dessus | Conforme : perspective, grille, boussole, échelle, altitude LiDAR et halos de trajectoire visibles |
| SIM-REQ-027 — lancement PX4 depuis l'application Windows | `RunnerRegistry`, `drone-agricole-px4-client`, `compose.yaml`, `runner_server` | arrêt volontaire du runner, redémarrage automatique, essai SITL `autostart-20260831t233124` | Conforme |
| SIM-REQ-028 — préserver le type des paramètres ROS 2 | `rosDoubleParameterValue` | `Px4RunnerContract.PreservesDoubleTypeForRosArguments` | Conforme |
| SIM-REQ-029 — générer et lancer les trois configurations LIO depuis Qt | `RunnerRegistry`, `yaml-cpp`, images `fast-lio2`, `point-lio`, `lio-sam` | `TestRunnerRegistry.preparesConfigurationsForAllLioRunners`, builds Docker, trois rejeux de 5 s | Conforme : 49 scans reçus, 0 manquant et 46 poses associées par moteur |
| SIM-REQ-030 — rendre la reconstruction Docker compatible avec le réseau du poste | `software/docker/Dockerfile` | clonages des dépôts amont et builds des trois images `1.0.0` | Conforme en HTTP/1.1 |
| SIM-REQ-031 — ne jamais préempter le dossier de résultat du runner | `MainWindow`, `RunnerRegistry`, `ResultAdapter` | assertion d'absence du dossier après `prepare()`, suite desktop, rejeu FAST-LIO2 de 5 s | Conforme : création par le runner, code de sortie 0 |
| SIM-REQ-032 — préserver les types YAML attendus par ROS 2 | `RunnerRegistry`, `yaml-cpp` | vérification des tags décimaux `blind` et `det_range`, rejeu FAST-LIO2 de 5 s | Conforme : 49 scans reçus, 45 odométries publiées |
| OBS-REQ-005 — rendre observable un rejeu LIO long | `LioOrchestrator`, `MainWindow`, `main_window.ui` | calcul de progression unitaire, rejeu de 5 s et contrôle des étapes 2–100 % | Conforme : mise à jour au plus toutes les 5 s pendant le rejeu |
| OBS-REQ-006 — restituer la télémétrie ROS 2 à Qt Windows pendant le rejeu | `TelemetryBridge`, `LiveTelemetry`, `BenchmarkTelemetryPublisher`, `telemetry-bridge` | `test_telemetry_bridge`, santé API, rejeu FAST-LIO2 de 5 s à 0,5× et lecture pendant l'exécution | Conforme : 2 839 points, 46 poses, 49 références, compteurs, CPU et 155,3 Mio RSS reçus en direct |
| OBS-REQ-007 — recharger une trajectoire LIO historique depuis Qt Windows sans ROS 2 natif | `ResultRepository`, `RosbagTrajectoryReaderStub`, `TelemetryBridge`, `rosbag2_cpp` dans Docker | aller-retour du contrat `drone_agricole.replay.v1`, client Windows réel, refus d'un chemin hors de `results` | Conforme : 46 poses, 49 références et 46 points de courbe relus ; chemin hors archive refusé avec HTTP 409 |
| OBS-REQ-008 — construire la carte LiDAR pendant le direct sans croissance mémoire non bornée et sans privilégier le début du trajet | `AdaptivePointMap`, `LiveTelemetry`, `telemetry-bridge`, `TrajectoryView` | `test_adaptive_point_map`, rejeu FAST-LIO2 dynamique 30 s, compteurs de voxel et de compaction | Conforme : deux compactions, 294 trames, 103 290 représentants, points présents autour du départ et de la fin |
| OBS-REQ-004 — conserver l'état final Point-LIO observable | patch de diagnostic Point-LIO | rejeu court et `pipeline_drain.json` | Conforme : état `complete`, 49 scans observés sur 49 |
| SAFE-REQ-008 — progresser d'abord en simulation | runner PX4 SITL et verrou d'environnement | scénario `failsafe`, observation de `offboard_loss_land_observed` | Conforme pour cet essai SITL |

## Résultats vérifiés

- configuration et compilation CMake desktop : réussies ;
- suite desktop : 12 tests sur 12 réussis ;
- suite du paquet PX4 dans l'image Docker : 9 résultats de test, aucune erreur ni défaillance ;
- services `micro-xrce-dds-agent`, `px4-sitl`, `px4-state-bridge` et `px4-runner-api` : actifs ;
- API locale : état `idle` et message `Runner PX4 SITL C++ prêt.` ;
- essai de perte Offboard : terminé avec succès, failsafe observé et atterrissage confirmé ;
- rejeux LIO courts FAST-LIO2, Point-LIO et LIO-SAM : code de sortie 0, pipeline complet, 49 scans observés sur 49 et 46 poses associées pour chaque moteur ;
- rejeu de non-régression du lancement dashboard FAST-LIO2 : code de sortie 0, 49 scans reçus et 45 odométries publiées ;
- rejeu complet dashboard `dashboard_20260902T115931Z_dcbb3e5d` : code de sortie 0, 5 762 scans reçus, 5 758 odométries publiées et contrats T0 archivés ;
- validation du pont C++ `telemetry_validation_cpp_bridge_final` : code de sortie 0 et instantané lu pendant le rejeu avec nuage, trajectoires, compteurs, CPU et RSS ;
- validation de carte `map_accumulation_validation_20260902` : code de sortie 0, pipeline complet, 46 trames LiDAR intégrées dans 39 543 voxels ;
- validation adaptative `map_adaptive_compaction_validation_20260902` : code de sortie 0, deux compactions, 294 trames et couverture du début comme de la fin ;
- preuves locales non versionnées : `results/simulation/px4_lot_a/failsafe_20260831t232826_ui_check/result.json` et `results/simulation/px4_lot_a/failsafe_20260831t233124_autostart/result.json`.

Cette validation reste limitée au SITL du poste de développement. Elle ne qualifie ni le matériel, ni un comportement en vol réel.
