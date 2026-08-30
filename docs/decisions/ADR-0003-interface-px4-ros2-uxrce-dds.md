# ADR-0003 — Interface PX4–ROS 2 par uXRCE-DDS

- Statut : accepté pour le lot A expérimental
- Date : 20 août 2026

## Contexte

Le système complet sépare le drone cartographe, qui construit une carte géoréférencée, du drone agricole, qui exécute ensuite un plan de vol. Le lot A doit d'abord valider sans matériel la liaison entre PX4 SITL, ROS 2, QGroundControl et le tableau de bord, tout en maintenant PX4 comme autorité de vol et de sécurité.

PX4 publie ses états par son client uXRCE-DDS. ROS 2 Jazzy et Gazebo Harmonic constituent l'environnement moderne de simulation, alors que les algorithmes LIO historiques restent isolés dans ROS 2 Humble selon l'ADR-0002.

## Décision

1. Utiliser le client uXRCE-DDS intégré à PX4 et un Micro XRCE-DDS Agent conteneurisé en UDP sur le port 8888.
2. Épingler `px4_msgs` sur la branche compatible avec le firmware et vérifier les définitions de messages avant chaque changement de version.
3. Utiliser le domaine ROS `42` pour le banc de projet.
4. Séparer deux composants ROS :
   - `state_bridge`, toujours en lecture seule vis-à-vis de PX4, pour l'état, l'odométrie, TF et le tableau de bord ;
   - `offboard_test`, absent du profil normal et activable seulement par deux verrous explicites pour les essais SITL.
5. Convertir les repères PX4 NED/FRD vers les repères ROS ENU/FLU dans le pont, sans modifier les données natives échangées avec PX4.
6. Conserver MAVLink et QGroundControl comme canal distinct de supervision. La connexion ROS ne remplace ni QGroundControl ni les mécanismes de sécurité PX4.
7. N'émettre que des consignes de trajectoire de haut niveau. Aucun composant du lot A ne publie de commande directe de moteur ou d'actionneur.

L'image PX4 `v1.18.0-beta2` reste admise pour ce banc expérimental parce qu'elle était la version officielle Gazebo disponible lors de l'amorçage. Elle devra être remplacée par une version stable épinglée avant toute qualification formelle ou transfert matériel.

Cette décision met à jour le point de déploiement de l'ADR-0002 : l'Agent n'est plus exécuté directement sur Windows, mais dans Compose avec publication du port UDP 8888. PX4 continue de le joindre par `host.docker.internal` sous Docker Desktop.

## Conséquences

- PX4 demeure responsable des modes, de l'armement, des asservissements et des réactions de sécurité.
- Le tableau de bord peut afficher le même état ROS que les futurs modules de planification.
- La chaîne est reproductible sur le poste Windows sans installation ROS native.
- Les tests Offboard ne peuvent pas être lancés accidentellement par le profil de visualisation ou de simulation courant.
- La compatibilité du triplet firmware, `px4_msgs` et Agent devient une donnée versionnée du banc.
- Le passage au matériel exigera un profil de paramètres de sécurité distinct et une nouvelle validation des transports, horloges, repères et latences.

## Alternatives rejetées

- Utiliser MAVROS comme interface ROS principale : ajoute une traduction MAVLink alors que PX4 fournit nativement l'interface uXRCE-DDS pour ROS 2.
- Mettre l'Agent sur Windows : fonctionnement possible, mais installation et versions moins reproductibles que le service Docker.
- Autoriser les commandes Offboard dans le pont d'état : mélange la télémétrie passive et une fonction critique, et augmente le risque d'activation involontaire.
- Commander directement les actionneurs depuis ROS : contraire à l'architecture de sûreté retenue et inutile pour la planification de trajectoire.
