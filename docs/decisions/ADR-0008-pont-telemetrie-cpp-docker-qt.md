# ADR-0008 — Pont de télémétrie C++ entre ROS 2 Docker et Qt Windows

- Statut : accepté
- Date : 2 septembre 2026
- Complète : ADR-0006 et ADR-0007

## Contexte

Le dashboard Web T0 recevait les données ROS 2 par un nœud intermédiaire exécuté dans Docker. Ce nœud s'abonnait aux trajectoires, au nuage enregistré, aux compteurs des pipelines LIO, aux métriques de ressources et à l'état PX4, puis diffusait des instantanés JSON au navigateur.

Pendant la migration vers l'application desktop, les abonnements ont été portés en C++ dans `LiveTelemetry`, mais le client Qt natif Windows ne peut pas les utiliser : la distribution MSYS2 du projet ne fournit ni `rclcpp` ni `rosbag2_cpp`. CMake sélectionne donc l'implémentation de repli, sans télémétrie. La progression textuelle du runner ne remplace pas les données opérationnelles en direct.

## Décision

La frontière ROS 2 reste dans Docker. Un service propriétaire **C++17**, `drone-agricole-tools telemetry-server`, s'exécute dans l'image ROS 2 Humble du projet et utilise l'implémentation ROS 2 de `LiveTelemetry`.

Le service expose uniquement sur le réseau Compose :

- `GET /api/health`, pour diagnostiquer la disponibilité du pont ;
- `GET /api/snapshot`, pour lire un instantané borné de télémétrie ;
- `POST /api/reset`, pour vider l'état d'une exécution précédente ;
- `POST /api/replay`, pour relire à la demande les trajectoires d'un résultat
  LIO archivé avec `rosbag2_cpp`.

Docker Compose publie le port du service sur `127.0.0.1:8092`. L'application Qt Windows interroge l'instantané au maximum quatre fois par seconde avec `Qt6::Network`. Une seule requête peut être active à la fois. Les réponses obsolètes, invalides, surdimensionnées ou hors contrat sont rejetées.

Le contrat `drone_agricole.telemetry_snapshot.v1` transporte :

- la trajectoire LIO estimée ;
- la vérité terrain alignée dans le repère de l'estimation ;
- le dernier nuage enregistré, décimé et borné ;
- la trajectoire PX4 ;
- les métriques LIO et de ressources ;
- l'état PX4 en lecture seule ;
- l'horodatage UTC de l'instantané.

La relecture historique utilise le contrat distinct
`drone_agricole.replay.v1`. L'application transmet uniquement un chemin de
rosbag relatif au workspace. Le service refuse les chemins absolus, les
sorties du dossier `results`, les dossiers inexistants et les résolutions de
liens symboliques hors de `results`. La réponse contient les trajectoires
estimée et de référence décimées, la courbe d'erreur bornée et les notes de
relecture. Cette opération est strictement en lecture seule.

Le pont ne lance aucune mission, ne publie aucune consigne de vol et ne commande aucun actionneur. PX4 conserve le vol critique et les failsafes ; ROS 2 fournit les fonctions avancées. L'unique écriture réseau, `reset`, ne modifie que les buffers d'affichage du pont.

Le transport HTTP JSON est un canal IPC local, pas une interface Web. L'interface opérateur reste une application Qt 6 Widgets et sa structure demeure dans les fichiers `.ui`.

## Conséquences

- la parité de télémétrie avec le dashboard Web est rétablie sans Python, JavaScript, HTML ni CSS ;
- aucune installation ROS 2 native n'est requise sur Windows ;
- l'historique LIO reste rechargeable depuis l'application Windows : la
  désérialisation ROS 2 est exécutée par le pont C++ dans Docker ;
- le service est partagé par les conteneurs LIO et PX4 sur le domaine ROS 2 `42` ;
- l'état visuel `DIRECT` ne peut être affiché que lorsque le client reçoit un instantané récent et conforme ;
- la fréquence, la taille des nuages et les longueurs de trajectoire sont bornées pour éviter de saturer l'interface ;
- le résultat final archivé reste la preuve de référence ; la télémétrie en direct est informative ;
- les couches Docker contenant PCL et les algorithmes LIO sont construites depuis
  une base de dépendances stable ; le binaire propriétaire C++ est injecté dans
  leur couche finale afin qu'une évolution du pont ne reconstruise pas les
  dépendances algorithmiques lourdes.

## Alternatives rejetées

- Installer ROS 2 natif dans MSYS2 : paquets indisponibles dans la chaîne actuelle et dépendance forte au poste Windows.
- Faire traverser directement DDS entre Docker Desktop et Windows : découverte et multicast moins reproductibles que le canal local explicite.
- Restaurer le serveur Python/WebSocket : contraire à la contrainte C++17.
- Réintroduire une interface HTML embarquée : contraire au choix Qt 6 Widgets et aux fichiers `.ui` éditables.
