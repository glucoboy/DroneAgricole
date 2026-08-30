# ADR-0002 — Séparation des environnements ROS, simulation et LIO

- Statut : accepté pour le premier socle
- Date : 18 août 2026

## Contexte

Les implémentations LIO retenues restent plus simples à intégrer sous Ubuntu 22.04 / ROS 2 Humble, tandis que la combinaison officiellement recommandée pour une simulation ROS/Gazebo moderne est Ubuntu 24.04 / ROS 2 Jazzy / Gazebo Harmonic. PX4 publie par ailleurs une image SITL Gazebo Harmonic versionnée.

Installer tous ces composants dans une même distribution créerait des conflits de versions et réduirait la reproductibilité.

## Décision

Maintenir trois environnements isolés :

1. `ros-humble` sur Ubuntu 22.04 pour les adaptateurs de datasets et les algorithmes FAST-LIO2, Point-LIO et LIO-SAM ;
2. `ros-jazzy-sim` sur Ubuntu 24.04 pour les ponts ROS/Gazebo et les composants de simulation modernes ;
3. `px4-sitl` basé provisoirement sur l'image officielle `px4io/px4-sitl-gazebo:v1.18.0-beta2`, épinglée par le digest `sha256:bcf8278e3321948be2266568528107dbfd94eb6fa703171cb013bc4d54dc8ef8`, pour le contrôleur de vol et Gazebo Harmonic.

La documentation PX4 cite des tags stables tels que `v1.17.0`, mais ce tag n'était pas publié dans le registre de l'image Gazebo au 18 août 2026. La version bêta est donc admise uniquement pour amorcer le banc SITL ; elle devra être remplacée par une version stable épinglée avant les campagnes de validation formelles.

Docker Compose constitue le point d'entrée commun. Les données brutes sont montées en volume et ne sont jamais incorporées aux images.

Sous Docker Desktop, l'image PX4 officielle résout `host.docker.internal` et cible directement Windows pour MAVLink et uXRCE-DDS. Compose ne publie donc pas les ports UDP 14550, 14540 et 8888, afin de les laisser disponibles à QGroundControl, MAVSDK et au Micro XRCE-DDS Agent sur l'hôte.

## Conséquences

- les dépendances LIO historiques n'imposent pas leur version de ROS à la simulation ;
- PX4 reste isolé des fonctions avancées ROS, conformément à la séparation de sûreté ;
- un pont uXRCE-DDS sera ajouté entre PX4 et ROS 2 lorsque les premiers messages de vol seront nécessaires ;
- les images `amd64` seront d'abord validées sur le PC, puis les composants compatibles seront construits en `arm64` pour Jetson ;
- le coût disque est supérieur à une image unique, mais les environnements sont reproductibles et remplaçables indépendamment.

## Alternatives rejetées

- Tout installer directement dans WSL : environnement difficile à reproduire et à transférer sur Jetson.
- Forcer Gazebo Harmonic dans ROS 2 Humble : combinaison possible mais non recommandée, avec paquets non standards et risques de conflits.
- Migrer immédiatement tous les LIO vers Jazzy : risque important avant même d'avoir établi les résultats de référence.
- Utiliser uniquement l'image PX4 : elle ne contient pas les outils ROS et dataset nécessaires au reste du projet.
