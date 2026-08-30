# Cahier des charges système

## Système autonome de cartographie et de traitement de vignobles à forte pente

| Champ | Valeur |
|---|---|
| Référence | DOC-00 |
| Version | V0.2 |
| Date | 18 août 2026 |
| Statut | Préliminaire |
| Portée | Système complet : cartographe, traitement et station sol |

## 1. Objet

Le projet vise à développer un système de drones destiné à la cartographie, à l'analyse et au traitement ciblé de vignobles difficiles d'accès. Il cible en priorité les fortes pentes, les terrasses, les rangs irréguliers, les espacements variables et les environnements comportant des poteaux, fils, murs, talus, arbres et ruptures de relief.

Le concept repose sur deux aéronefs complémentaires :

1. un drone cartographe construit une représentation 3D géoréférencée et sémantique de la parcelle ;
2. un drone de traitement utilise cette carte et ses capteurs locaux pour traiter la végétation depuis l'inter-rang.

Le système n'est pas une simple adaptation d'un drone pulvérisant depuis le dessus. L'organe de traitement pressenti descend verticalement sous le drone et applique le produit latéralement, face aux murs végétaux.

## 2. Périmètre

### 2.1 Inclus

- acquisition LiDAR, caméra, IMU et GNSS RTK ;
- reconstruction et géoréférencement 3D ;
- détection du terrain, de la végétation, des pieds, poteaux, fils et obstacles ;
- génération d'une carte sémantique et d'un graphe de parcelle ;
- planification de mission et navigation locale ;
- suivi du relief et maintien des distances de sécurité ;
- commande du bras, des étages d'atomisation, de la pompe et des vannes ;
- calcul de dose et synchronisation temporelle du traitement ;
- supervision de sécurité, journalisation et station sol ;
- simulation, rejeu de datasets, SITL, HITL, essais sur banc et validation en vol.

### 2.2 Hors périmètre de la première phase

- certification d'un produit commercial ;
- traitement autonome avec produit phytosanitaire avant validation complète sur eau/traceur ;
- conception définitive des cartes électroniques et pièces mécaniques industrialisées ;
- entraînement de modèles agronomiques de diagnostic non nécessaires à la navigation ;
- automatisation de toutes les opérations logistiques de remplissage et recharge.

## 3. Architecture opérationnelle

```text
Cartographie de la parcelle
          |
          v
Carte 3D géoréférencée et sémantique
          |
          v
Préparation et validation de mission
          |
          v
Drone de traitement
          |
          +--> localisation sur la carte
          +--> perception locale
          +--> corridor 3D sûr
          +--> traitement ciblé
          |
          v
Compte rendu et traçabilité
```

Le drone de traitement ne doit jamais dépendre exclusivement d'une trajectoire GNSS prédéfinie. La localisation globale, la carte et la perception locale sont complémentaires.

## 4. Environnement cible

Le système devra supporter, après qualification progressive :

- terrain plat, pente continue et fortes pentes ;
- terrasses et ruptures de niveau ;
- sol irrégulier ;
- rangs courbes, non parallèles ou discontinus ;
- végétation clairsemée ou dense ;
- motifs géométriques répétitifs ;
- mouvement des feuilles et branches sous l'effet du vent ;
- poteaux, fils de palissage et obstacles naturels ou artificiels ;
- couverture GNSS dégradée ou temporairement perdue ;
- variations de luminosité et conditions météorologiques compatibles avec le vol autorisé.

Les limites nominales de pente, vent, température, pluie, visibilité et écartement entre rangs restent **à valider** à partir de la plateforme physique.

## 5. Exigences fonctionnelles système

### 5.1 Fonctions communes

| ID | Exigence |
|---|---|
| SYS-FUN-001 | Le système doit séparer les fonctions critiques de vol, exécutées par PX4, des fonctions avancées exécutées par ROS 2. |
| SYS-FUN-002 | Le système doit horodater et enregistrer les données capteurs brutes utiles à la reproduction d'un essai. |
| SYS-FUN-003 | Le système doit fournir à l'opérateur l'état de la mission, de la navigation, de l'énergie, des communications et des fonctions de sécurité. |
| SYS-FUN-004 | Le système doit permettre l'arrêt, l'abandon de mission et le retour à un état sûr depuis la station sol et depuis le superviseur embarqué. |
| SYS-FUN-005 | Le système doit détecter les données périmées, incohérentes ou indisponibles et adapter son comportement. |
| SYS-FUN-006 | Le système doit conserver une traçabilité reliant mission, configuration logicielle, paramètres, données et résultats. |

### 5.2 Drone cartographe

| ID | Exigence |
|---|---|
| MAP-FUN-001 | Le drone cartographe doit acquérir de manière synchronisée LiDAR, IMU, GNSS RTK et images nécessaires à la mission. |
| MAP-FUN-002 | Il doit estimer sa trajectoire même pendant une dégradation temporaire du GNSS. |
| MAP-FUN-003 | Il doit produire un nuage 3D géoréférencé de la zone couverte. |
| MAP-FUN-004 | Il doit segmenter au minimum terrain, végétation, poteaux et obstacles structurants. |
| MAP-FUN-005 | Il doit identifier ou estimer les pieds, rangs, terrasses, murs, talus et ruptures de terrain utiles à la planification. |
| MAP-FUN-006 | Il doit associer à chaque entité cartographique un identifiant, une géométrie, une confiance et une date d'observation. |
| MAP-FUN-007 | Il doit produire un graphe de déplacement représentant la géométrie réelle des rangs, et non de simples lignes idéales. |
| MAP-FUN-008 | Il doit signaler les zones insuffisamment observées ou présentant une incertitude incompatible avec une mission de traitement. |

### 5.3 Drone de traitement

| ID | Exigence |
|---|---|
| TRT-FUN-001 | Le drone de traitement doit charger et vérifier la compatibilité d'une carte de parcelle avant mission. |
| TRT-FUN-002 | Il doit se recaler sur la carte en combinant GNSS/IMU, LIO/VIO et perception locale. |
| TRT-FUN-003 | Il doit construire en continu un corridor libre tenant compte du corps du drone et de l'enveloppe du bras. |
| TRT-FUN-004 | Il doit maintenir des distances de sécurité aux vignes, au sol, aux poteaux, aux fils et aux obstacles. |
| TRT-FUN-005 | Il doit suivre le relief et anticiper les pentes et ruptures de terrasse compatibles avec sa dynamique. |
| TRT-FUN-006 | Il doit déployer le bras uniquement lorsque les conditions de mission et de sécurité sont satisfaites. |
| TRT-FUN-007 | Il doit identifier la cible à traiter et l'associer à la carte avec une confiance mesurable. |
| TRT-FUN-008 | Il doit commander indépendamment les étages de traitement lorsque l'architecture matérielle le permet. |
| TRT-FUN-009 | Il doit compenser la vitesse du drone et les latences pompe/vanne afin d'aligner l'application avec la cible. |
| TRT-FUN-010 | Il doit calculer ou appliquer une consigne de dose en fonction de la mission, de la vitesse, de la distance et de la végétation. |
| TRT-FUN-011 | Il doit interrompre immédiatement l'application en dehors de la zone autorisée ou en cas d'anomalie critique. |
| TRT-FUN-012 | Il doit produire une carte ou un journal des zones réellement traitées et des quantités appliquées. |

### 5.4 Station sol

| ID | Exigence |
|---|---|
| GCS-FUN-001 | La station sol doit permettre de préparer, visualiser, valider, lancer et interrompre une mission. |
| GCS-FUN-002 | Elle doit afficher la carte 2D/3D, les rangs, pieds, obstacles, zones interdites et zones traitées. |
| GCS-FUN-003 | Elle doit présenter les alarmes, l'état du bras, le niveau de produit et les marges de sécurité pertinentes. |
| GCS-FUN-004 | Elle doit exporter les journaux et rapports nécessaires à l'analyse et à la traçabilité. |

## 6. Exigences de sûreté

| ID | Exigence |
|---|---|
| SAFE-REQ-001 | ROS 2 ne doit pas commander directement les moteurs ; PX4 reste responsable des boucles de vol et failsafes. |
| SAFE-REQ-002 | Toute perte de consigne ROS 2, de communication ou de perception critique doit déclencher un comportement PX4 ou mission explicitement défini. |
| SAFE-REQ-003 | Le système doit surveiller la fraîcheur, la fréquence et la cohérence des flux critiques. |
| SAFE-REQ-004 | Les fils de palissage doivent être traités comme un danger multimodal ; aucun capteur unique ne constitue une garantie de détection. |
| SAFE-REQ-005 | Le bras doit disposer d'états sûrs, d'une confirmation de position et d'une stratégie en cas de blocage. |
| SAFE-REQ-006 | La pompe et les vannes doivent revenir à l'état fermé en cas de perte d'alimentation, arrêt d'urgence ou perte de commande. |
| SAFE-REQ-007 | Une géofence, des limites d'altitude/vitesse et des zones interdites doivent être imposées avant la mission. |
| SAFE-REQ-008 | Les essais doivent progresser de la simulation vers le réel selon des portes de validation documentées. |
| SAFE-REQ-009 | Le traitement doit être inhibé tant que localisation, carte, corridor libre et état du bras ne sont pas tous valides. |

## 7. Objectifs de performance préliminaires

Les valeurs ci-dessous sont des objectifs de conception et restent **à valider**.

| ID | Indicateur | Objectif préliminaire |
|---|---|---|
| PERF-001 | Erreur de localisation locale en traitement | compatible avec le maintien du corridor ; cible initiale ≤ 10 cm |
| PERF-002 | Disponibilité de l'odométrie locale | aucune interruption non gérée pendant une séquence qualifiée |
| PERF-003 | Fréquence du contrôle de trajectoire locale | ≥ 20 Hz |
| PERF-004 | Fréquence de perception d'obstacles | ≥ 10 Hz, latence bornée |
| PERF-005 | Décalage longitudinal du traitement | cible initiale ≤ 10 cm à vitesse nominale |
| PERF-006 | Erreur de dose par segment | cible initiale ≤ 10 % sur banc |
| PERF-007 | Taux de collision | 0 sur tous les scénarios acceptés |
| PERF-008 | Perte non signalée d'un flux critique | 0 |
| PERF-009 | Reproductibilité d'un benchmark | même configuration, résultats archivés et comparables |

Les distances de sécurité, vitesses, accélérations, masse, autonomie, charge utile et dimensions seront fixées après choix de la plateforme et essais dynamiques.

## 8. Contraintes techniques

- Développement principal sous Windows 11 + WSL2 + Docker.
- Accélération GPU disponible sur PC via NVIDIA RTX 5060 Ti.
- Déploiement cible sur Jetson Orin avec JetPack et NVIDIA Container Runtime.
- Environnement logiciel conteneurisé et reproductible sur `amd64` et `arm64`.
- ROS 2, C++ et Python ; C++ privilégié pour les chemins embarqués critiques en latence.
- PX4 sur contrôleur de vol dédié ; liaison ROS 2/MAVLink ou interface PX4 qualifiée.
- QGroundControl comme base de station sol, avec personnalisation métier envisagée.
- Réseau Ethernet embarqué dimensionné pour le LiDAR et les caméras ; unicast privilégié.
- Conservation des données brutes et calibrations indépendamment des algorithmes testés.

## 9. Données de la carte

La carte doit pouvoir représenter au minimum :

```text
Parcelle
├── référentiel géographique et version
├── surface terrain / modèle d'élévation
├── terrasses et ruptures
├── rangs et segments navigables
├── pieds ou zones végétales
│   ├── identifiant et position 3D
│   ├── dimensions / volume / confiance
│   └── voisinage et orientation locale
├── poteaux et fils connus
├── murs, talus et obstacles
├── zones interdites ou incertaines
└── historique d'observation
```

## 10. Validation

La stratégie de validation suit cinq niveaux :

1. tests unitaires et rejeu de données enregistrées ;
2. simulation algorithmique et PX4 SITL ;
3. HITL et bancs capteurs/actionneurs ;
4. vols sans bras, puis avec bras sans liquide ;
5. eau avec traceur, puis essais réglementairement autorisés.

Chaque exigence approuvée devra être reliée à au moins une procédure de test et à un critère d'acceptation mesurable.

## 11. Risques principaux

- fils fins peu ou mal détectés par le LiDAR ;
- motifs répétitifs et végétation mouvante dégradant le SLAM ;
- perte RTK et erreurs de recalage carte/réel ;
- interaction aérodynamique entre rotors, bras, végétation et atomisation ;
- collision du bras lors d'un mouvement latéral ou d'une rupture de pente ;
- surcharge CPU/GPU, latence ou échauffement de l'ordinateur compagnon ;
- masse, autonomie et rigidité du système de traitement ;
- dérive de produit et contraintes réglementaires ;
- dépendance à des pilotes capteurs insuffisamment maintenus.

## 12. Décisions ouvertes

- plateforme aérienne et dimensions définitives ;
- LiDAR et caméras de série ;
- Orin Nano ou Orin NX pour le cartographe ;
- mécanisme de bras et nombre d'étages ;
- type d'atomisation et assistance d'air ;
- objectifs définitifs de précision et de vitesse ;
- messages ROS 2, QoS et fréquences finales ;
- stratégie exacte de détection des fils ;
- cadre réglementaire et procédures opérationnelles.

## 13. Critère de sortie de la phase préliminaire

Le cahier des charges pourra passer au statut **Candidat** lorsque :

- les scénarios d'usage et limites d'environnement auront été relus ;
- les dimensions et masses de référence seront connues ;
- les seuils de sécurité et performances auront une justification ;
- l'architecture capteurs/calcul aura été testée au moins en rejeu et sur banc ;
- chaque exigence critique possédera un test et un propriétaire.
