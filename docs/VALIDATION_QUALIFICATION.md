# Validation et qualification

| Champ | Valeur |
|---|---|
| Référence | `DOC-VAL` |
| Nature | document vivant transversal |
| Dernière mise à jour | 25 novembre 2026 |
| Statut | stratégie active ; qualification du système complet **À valider** |
| Politique documentaire | [Index documentaire](INDEX.md) |

## 1. Objet et frontières

Ce document est la source de vérité pour la stratégie de validation, les
campagnes, les résultats synthétiques et le reste à qualifier. Les architectures
et leurs critères de conception restent décrits dans [DOC-HLD](architecture/HLD.md),
[DOC-SW](architecture/ARCHITECTURE_LOGICIELLE.md),
[DOC-MEC](architecture/ARCHITECTURE_MECANIQUE.md) et
[DOC-ELEC](architecture/ARCHITECTURE_ELECTRIQUE_RESEAUX.md).

Les journaux, données brutes, captures, modèles et résultats volumineux ne sont
pas versionnés. Ils sont conservés dans `results/`, `datasets/`, `.runtime/` ou
les répertoires `verification/` concernés. Le présent registre ne conserve que
les conditions nécessaires à l'interprétation, les mesures de synthèse, le lien
vers la preuve et les limites connues.

Un résultat est qualifié seulement si l'entrée, la configuration, le logiciel,
l'environnement, le protocole et le critère d'acceptation sont identifiés. Une
valeur préliminaire ou un seuil non approuvé porte la mention **À valider**.

## 2. Progression des essais

L'ordre de validation est obligatoire :

1. tests unitaires et de contrats hors matériel ;
2. rejeu de datasets et simulation déterministe ;
3. PX4 SITL et scénarios de défaillance ;
4. banc matériel sans vol ;
5. vol captif ou zone contrôlée, sans traitement ;
6. vol avec organe de traitement sans liquide ;
7. eau et traceur ;
8. produits autorisés, seulement avec protocole approuvé.

Un niveau ne compense jamais l'absence de validation du niveau précédent. PX4
reste responsable du vol critique et des sécurités ; ROS 2 ne fournit que des
consignes et fonctions avancées. Aucun résultat cartographique ne constitue à
lui seul une autorisation d'envoyer une mission au drone.

## 3. Règles de preuve

Chaque exécution qualifiante doit identifier au minimum :

- l'exigence et le composant ou algorithme vérifié ;
- les empreintes des données, de la configuration et de l'image ou du binaire ;
- l'architecture d'exécution (`amd64`, `arm64`, PC ou cible embarquée) ;
- les versions des dépendances et les paramètres effectifs ;
- les métriques, événements, artefacts et motifs d'échec ;
- les données exclues de la prédiction, notamment les vérités terrain ;
- le critère d'acceptation et la conclusion `conforme`, `non conforme`,
  `préliminaire` ou **À valider**.

Les nouvelles exécutions logicielles utilisent les contrats T0
`run_request.json`, `t0_run_manifest.json`, `t0_metrics.json`, `artifacts.json`
et `events.jsonl`. Un runner doit échouer explicitement si un dataset, une
calibration, une vérité terrain ou une image ne correspond pas à l'empreinte
attendue. Les conversions d'unité, de temps, de repère ou de format sont
déclarées ; elles ne sont jamais corrigées silencieusement.

## 4. Bancs et matrices de campagne

### 4.1 Banc virtuel `VINEYARD_BENCH_V01`

| ID | Scénario | But principal | Variantes initiales |
|---|---|---|---|
| `VB01` | terrain plat régulier | référence répétable | 0,5 / 1 / 2 m/s |
| `VB02` | rangs courbes | perception et planification | courbures faible / forte |
| `VB03` | forte pente | relief et dynamique | 15 / 25 / 35°, **À valider** |
| `VB04` | terrasse | ruptures de niveau | mur, talus, bout de terrasse |
| `VB05` | végétation dense | LIO et perception | statique / mouvement simulé |
| `VB06` | poteaux | détection et évitement | bois / métal / occultation |
| `VB07` | fils | danger critique et politique conservatrice | diamètres, hauteurs, contrastes |
| `VB08` | perte RTK | continuité et reprise | coupure courte / longue / biais |
| `VB09` | mouvement rapide | latence, deskew et dynamique | accélérations / rotations |
| `VB10` | géométrie pauvre | robustesse en environnement répétitif | peu de repères |

Chaque scénario versionné doit fournir sa définition, son monde, sa mission, sa
vérité terrain, ses événements attendus et ses critères d'acceptation.

### 4.2 Campagne physique future `VINEYARD_DATASET_V1`

La campagne doit couvrir au minimum : plat régulier et irrégulier, pentes 15°,
25° et 35° **À valider**, terrasse, feuillage dense et clairsemé, vent, poteaux
et fils, perte RTK, mouvement rapide, vol stationnaire et fermeture de boucle.

Les acquisitions conservent les données LiDAR brutes, timestamps par point,
IMU LiDAR et PX4, GNSS/RTK brut et solution, états PX4, images brutes,
calibrations, synchronisation, transformations, actionneurs, conditions d'essai
et vérité terrain disponible.

### 4.3 Mesures communes

| Domaine | Mesures attendues |
|---|---|
| Localisation | ATE, RPE translation/rotation, erreur finale, resets, sauts, durée sans solution |
| Temps réel | latence médiane/P95/P99, fréquence, backlog et vitesse effective |
| Ressources | CPU, GPU, RAM, VRAM, température et puissance |
| Perception | précision, rappel, F1, IoU, portée, latence, stabilité et confiance |
| Navigation | erreur latérale/verticale, distances minimales, collisions, violations de corridor |
| Traitement | position du bras, décalage buse/cible, débit, dose, dépôt, pertes au sol et hors-zone |
| Reproductibilité | répétitions, variance, empreintes et comparabilité des fenêtres |

Le volume traité hors zone autorisée a pour objectif zéro. Les autres seuils
d'acceptation numériques restent **À valider** tant qu'ils ne sont pas approuvés.

## 5. Portes de validation

| Porte | Critères de sortie | État au 10 septembre 2026 |
|---|---|---|
| `GATE-01` Infrastructure | construction reproductible, données/calibrations identifiées, rapports automatiques, seconde machine | partiel : PC et `amd64` validés ; CI distante et runtime complet `arm64` **À valider** |
| `GATE-02` Localisation | aucun échec silencieux, ATE/RPE, perte RTK, classement justifié et répétable | partiel : BotanicGarden qualifie le banc PC ; multi-scènes et Jetson **À valider** |
| `GATE-03` Navigation SITL | missions sans collision, fils conservatifs, perte RTK maîtrisée, limites dynamiques | partiel : carré et perte Offboard validés ; `VB01` à `VB10` **À valider** |
| `GATE-04` Banc actionneurs | états sûrs, défauts injectés, temporisation, débit et dose eau/traceur | non exécuté |
| `GATE-05` Vol progressif | risques/procédure approuvés, géofence et arrêt d'urgence, données rejouables | non exécuté |
| `GATE-06` Traitement autorisé | portes précédentes fermées, cadre réglementaire et protocole produit approuvés | non exécuté |

## 6. Qualification des environnements

### 6.1 Poste de développement

Le contrôle du 18 août 2026 a validé : WSL `2.7.11.0`, noyau
`6.18.33.2`, Ubuntu `24.04.4 LTS`, Docker Desktop `4.87.0`, moteur Docker
`29.7.2`, Compose `5.4.0`, accès au workspace et NVIDIA GeForce RTX 5060 Ti
de 16 311 Mio depuis Windows, WSL et l'image
`nvidia/cuda:12.8.1-base-ubuntu24.04`.

Les bases ROS 2 Humble/Ubuntu 22.04, ROS 2 Jazzy/Ubuntu 24.04 et PX4/Gazebo
`gz_x500` ont été construites et exécutées sur le poste. Ces preuves ne
qualifient pas la cible embarquée.

Le banc PX4 utilise encore l'image expérimentale `v1.18.0-beta2` épinglée dans
`compose.yaml`. Elle ne peut pas servir de base à une qualification formelle :
une version stable épinglée, compatible avec `px4_msgs`, doit d'abord être
construite et rejouée.

### 6.2 Logiciel et architectures cibles

- baseline locale `sw0-v0.1` fermée le 5 septembre 2026 ; les 12 suites CTest
  de ce jalon passent sous Windows en 2,46 s et sous Linux Qt 6.2.4 en 35,54 s ;
- cinq images Humble/LIO/Qt reconstruites en `linux/amd64` ;
- noyau propriétaire C++/ROS 2 construit, inspecté et exécuté en
  `linux/arm64`, empreinte
  `sha256:1901e9e1095eae4290e596b1f63a7af9b9769366763f8d42c4a32e54dbfc769a` ;
- runtime Qt/LIO complet, JetPack, CI distante, rendu OpenGL conteneurisé et
  stabilité des redémarrages Docker sur cible : **À valider**.

La refonte de la station du 9 septembre a porté la suite à 18 tests CTest sous
Windows et 14 sans interface. L'évolution cartographie RGB l'a portée à 19,
puis le parcours surface à 20 suites CTest Windows réussies, comme détaillé en
section 11. Linux/ROS 2, nouveaux rejeux LIO/SITL et ARM de cette révision
restent **À valider**.

### 6.3 Contrôles avant intégration Git — 17 novembre 2026

La sauvegarde et la réunion des branches demandées par le responsable portent
sur le workspace courant, avec ses travaux en cours. Elles ne changent pas
la priorité de §14. Les contrôles Windows amd64 de cette passe sont consignés
dans [la preuve structurée](verification/integration_git.json).

| Périmètre | Résultat observé |
|---|---|
| Station Qt | compilation réussie ; 22/25 tests réussis, deux assertions en échec, `test_dashboard_mapping` interrompu après 208,95 s et donc incomplet |
| Simulation hors ligne | compilation réussie ; six tests réussis, `self-test-sitl` dépasse la limite CTest de 30 s puis réussit en exécution directe ; génération du modèle exclue pour préserver les dérivés courants |
| Moteurs L1–L5 | compilations et tests C++ locaux réussis ; L3 rejoué isolément après un timeout initial ; L4 : six réussites et un test natif ignoré ; L5 : deux réussites |
| Moteur électromécanique Python | 64 tests réussis et 13 tests natifs ignorés |
| Fichiers et configuration | configurations Compose de base et cartographe valides, dix formulaires UI XML lisibles, JSON inspectés lisibles ; aucun motif de secret détecté par le contrôle ciblé |

Les assertions station concernent le libellé de masse désormais explicite
dans `SystemPage` et le décompte des domaines du dépôt de résultats (155
attendus contre 169 indexés). Elles restent à reprendre ; l'interruption de
la cartographie ne démontre pas un défaut fonctionnel. La passe conserve
ces sources et les preuves antérieures, sans correction métier ni nouvelle
qualification. Les avertissements d'espacement de `git diff --check` sont
également conservés pour ne pas altérer les empreintes des scripts existants.

L'historique automatique KiCad `.history/`, dépourvu de dépôt distant,
est retiré du suivi parent et conservé localement. Pièces jointes, archives
de session et exports électroniques régénérables sont ignorés. Les petits
natifs explicitement autorisés sont publiables ; les dépendances fabricant
ignorées restent nécessaires pour rouvrir tous les assemblages.

Build ROS 2/PX4/Docker, Linux/arm64, campagnes natives FreeCAD, ERC/DRC,
SITL en vol et essais physiques ne sont pas exécutés dans cette tâche de
publication. La qualification du système complet reste **À valider**.

## 7. Registre des datasets

### 7.1 BotanicGarden `1006-03`

| Élément | Valeur |
|---|---|
| Rosbag LIO | 6 325 796 540 octets ; SHA-256 `482d4b3081264a6e5eaf3c05ea57d45f25cf572e01c1f887d5b598372ab79c68` |
| Vérité terrain | 834 042 octets ; SHA-256 `2d507e1344da2dbb8763f96971f9d9ea902e95f7084acc903768a3f8737cf3dd` |
| Durée / messages LIO | 610,003 s / 478 023 |
| Durée / poses de référence | 599,715 s / 5 947 |
| Usage | premier banc LIO Velodyne/Xsens et Livox/BMI088 |
| Limite | robot terrestre en jardin ; ne qualifie ni une vigne ni la dynamique de vol |

La chaîne Velodyne/Xsens est cohérente ; la norme médiane d'accélération Xsens
sur 2 000 messages vaut `9,8057`. Pour Livox/BMI088, utiliser directement
`T_bmi088_livox` : la norme médiane vaut `0,99575` et la gestion du facteur
`9,8` doit être explicite par algorithme. La chaîne caméra/BMI088 publiée est
incohérente avec cette extrinsèque directe et ne doit pas être mélangée au
benchmark LIO. Les conditions d'usage commercial restent **À valider**.

### 7.2 EscaYard B7 — régression historique uniquement

Le lot contient un LAS de 6 583 772 points et 138 troncs RTK B7. Les empreintes
MD5 contrôlées sont `ada3209607dd8e01a1e6bfa9fa6143c4` pour l'archive troncs,
`f3f33215b99e9c56411d4bd43e34e310` pour le CSV et
`e9d08ac4c4c857a811faabcd51350bce` pour le LAS ; les SHA-256 restent dans le
manifeste du dataset. Le LAS annonce `EPSG:32629`, les références `EPSG:25829`
et le datum vertical est inconnu : les métriques géométriques restent des
avertissements.

EscaYard n'est plus utilisé pour les nouveaux essais. Il reste un jeu de
régression pour l'isolation de la vérité terrain et la compatibilité des
archives ; FriûlBot est le jeu cartographique temporel actif.

### 7.3 FriûlBot Test 2 — jeu cartographique actif

| Élément | Valeur |
|---|---|
| Bag | 6 557 409 210 octets ; MD5 `f79aac2893a0b910863962fbd9a9a2bf` |
| Images `0029SET.zip` | 5 518 848 615 octets ; empreinte de référence dans le [catalogue, entrée FriûlBot](../datasets/manifests/catalogue_datasets.yaml) |
| Durée / messages | 1 283,858 s / 977 318 |
| Capteurs utiles | 12 728 scans, 256 812 IMU, 638 déclenchements, 638 jeux × 5 TIFF, 3 855 GNSS |

Le bag est un conteneur mixte. L'allowlist sépare perception
(LiDAR, IMU, déclenchements, TIFF, calibrations) et évaluation (GNSS, odométrie
roues et poses SLAM publiées). Les bags d'indices NDVI/GNDVI/NDRE des auteurs
sont exclus de la prédiction. FriûlBot qualifie une chaîne logicielle de
perception en vigne, pas le montage Airy/Basler ni la dynamique du drone.

## 8. Résultats de localisation

### 8.1 Comparaison de référence BotanicGarden à `1×`

Preuve historique retrouvée lors de l'audit du 7 octobre 2026 :
[comparaison complète du 19 août](../results/benchmarks/comparison/botanicgarden_1006-03/full_1x_qos_harmonized_20260819.json),
qui identifie les trois runs sources sous `/workspace/results/benchmarks/`
(montage conteneur du répertoire local `results/benchmarks/`). Cette archive
locale est volontairement hors Git ; sa lecture confirme le tableau, sans
rejeu ni qualification de la révision courante.

| Mesure | FAST-LIO2 | Point-LIO | LIO-SAM |
|---|---:|---:|---:|
| Scans reçus / synchronisés | 5 762 / 5 762 | 5 762 / 5 762 | 5 762 / 5 762 |
| Odométries | 5 758 | 5 758 | 5 758 |
| ATE translation RMSE | **0,35916 m** | 0,49940 m | 0,41206 m |
| ATE orientation RMSE | 1,67155° | 1,55623° | **1,13826°** |
| RPE translation à 1 s | 0,04825 m | 0,04642 m | **0,04174 m** |
| RPE rotation à 1 s | 0,59370° | 0,58981° | **0,57086°** |
| CPU moyen | 0,391 cœur | **0,337 cœur** | 1,601 cœur |
| RSS maximal | **306,9 Mio** | 315,7 Mio | 617,6 Mio |

FAST-LIO2 est la baseline principale, LIO-SAM le candidat précision et
Point-LIO la référence de sobriété calcul. Ce classement est valide pour cette
campagne PC ; sa généralisation à plusieurs scènes et à Jetson reste
**À valider**.

### 8.2 Sensibilité et répétabilité

À `0,8×`, FAST-LIO2 produit 5 214 odométries pour 5 762 scans (90,49 %), soit
seulement 1,44 point de plus qu'à `1×`. Sur trois fenêtres dynamiques, les
moyennes sont 87,47 % à `0,8×` et 87,70 % à `1×` : la saturation CPU n'explique
pas l'essentiel des sorties manquantes.

La campagne de 16 essais montre qu'un voxel de 1,00 m dégrade l'ATE moyenne de
91 %. Le voxel de 0,25 m l'améliore d'environ 10 % mais augmente le CPU d'environ
19 % et la mémoire de 21 %. Le réglage de travail reste 0,50 m ; sa qualification
sur d'autres scènes demeure **À valider**.

Après correction du calcul d'alignement C++, trois rejeux FAST-LIO2 complets
donnent `0,36442 / 0,37651 / 0,32524 m` d'ATE translation. Trois rejeux LIO-SAM
donnent `0,39505 / 0,36649 / 0,36768 m`. Tous reçoivent 5 762 scans et produisent
5 758 poses. Les anciens scores C++ obtenus avant le correctif d'alignement ne
doivent pas être utilisés ; les trajectoires enregistrées restent valides.

## 9. Résultats PX4 SITL

Le lot A valide la frontière de sûreté en simulation : ROS 2 publie des
consignes Offboard et PX4 reste seul responsable du contrôle critique et du
failsafe.

| Scénario | Résultat de référence | Conclusion |
|---|---|---|
| Carré 2 m | altitude max. 1,998 m ; erreur aux coins 0,330–0,345 m ; environ 19,3 s | quatre segments, atterrissage et désarmement réussis |
| Perte Offboard | arrêt 18,852 s ; `AUTO_LAND` 19,951 s ; latence 1,099 s ; posé 24,551 s | réaction autonome PX4 réussie |
| Rejeu C++ SW0 carré | altitude max. 2,018 m ; erreur max. 0,299–0,344 m | `square_completed`, posé, aucun failsafe |
| Rejeu C++ SW0 perte Offboard | perte 18,850 s ; action PX4 19,900 s ; latence 1,050 s | `offboard_loss_land_observed`, posé |

Les paramètres `COM_OF_LOSS_T=1.0` et `COM_OBL_RC_ACT=4` étaient réservés au
banc SITL headless. Ces résultats ne qualifient ni le matériel, ni le vol réel,
ni les paramètres de failsafe finaux. La perte de l'Agent DDS, la latence
réseau, les sauts d'horloge et le redémarrage d'un nœud restent **À valider**.

### 9.1 AUTO/MANU, couverture et RF commun — campagne planifiée

Les clarifications du 16 septembre 2026 dans DOC-HLD §4.2/4.6/4.7 et la
liaison DOC-ELEC §7.4 ont le statut **Planifié / À valider**. La base
Holybro H-RTK F9P (SKU 12022) reste retenue au sol. Le Rover DroneCAN
à antenne patch sélectionné le 24 septembre est réévalué pour la
synchronisation : la variante Helical DroneCAN STM32G4, avec sortie PPS
candidate, est **À valider** avant de figer le module embarqué. Le transport
des corrections par la RF commune Pocket/Backpack/RP4TD est candidat :
la base USB/QGroundControl fournit les messages MAVLink 2 GPS_RTCM_DATA,
qui doivent parvenir au rover via PX4. Aucun essai de cette chaîne n'a été
exécuté. Les résultats Offboard du §9 ne qualifient ni la poursuite AUTO
après perte RC/GCS, ni la commande MAVLink, ni le transit RTCM.

| Test | Exigences / composants | Protocole et résultat attendu |
|---|---|---|
| `T-MAP-COV-01` | `MAP-FUN-009` ; planification, caméra/LiDAR, suivi de trajectoire | surface et géométrie de référence connues, terrain plat puis pente/terrasses/arbres ; vérifier empreinte utile, recouvrements longitudinal/latéral, limites du polygone, zones non couvertes et dégagements ; seuils numériques **À valider** avant campagne |
| `T-RF-01` | `SYS-FUN-008/009`, `ELEC-LNK-002` ; Pocket, RP4TD, PX4, QGC | banc sans hélices : voies/modes correctement reçus, aller-retour MAVLink et accusés mission/paramètres ; fermer QGC puis couper le Wi-Fi local : commande physique maintenue et état sol signalé indisponible |
| `T-RF-02` | `SYS-FUN-007`, `SAFE-REQ-010`, `ELEC-LNK-001` ; mission embarquée et PX4 | SITL puis banc : couper séparément RC, QGC et RF commun en AUTO ; mission continue sous gardes valides ; injecter ensuite navigation/énergie invalide ou perte Offboard et constater la réaction spécifique, prioritaire |
| `T-RF-03` | `SYS-FUN-008`, `SAFE-REQ-010` ; sélection d'autorité | SITL puis banc : perte RC en MANU, commandes périmées, reconnexion avec interrupteurs déplacés ; repli attendu, aucun réarmement/changement d'autorité par reconnexion seule, retour AUTO explicite ; traitement inhibé à la reprise MANU |
| `T-RF-04` | `SYS-FUN-009`, `ELEC-LNK-001/002` ; transport et arbitrage | saturer les échanges mission/paramètres pendant la commande et les alarmes ; mesurer latence, fraîcheur, pertes, files et équité ; tester doublons, identifiants, heartbeats du RX/QGC, absence du vrai GCS et commandes contradictoires ; RTCM actif selon T-RF-06 |
| `T-RF-05` | `ELEC-LNK-001/002`, `ELEC-EMC-001` ; matériel et implantation | banc alimentation/CEM puis progression terrain : courant moyen/pointe, chute de rail, température, orientations, masques du châssis, perturbations propulsion ; relever la couverture aux positions opérateur/drone représentatives de Cornas, sans déduire la portée de 5 ha |
| `T-RF-06` | `SW-RTK-001`, `SYS-FUN-009`, `ELEC-LNK-001/002/003` ; H-RTK F9P Base et rover DroneCAN à figer après étude temporelle, QGroundControl, Pocket/Backpack, RP4TD et PX4 | banc sans hélices puis terrain : mesurer le débit réel RTCM/MAVLink 2 de la base avec constellations et messages configurés ; faire transiter simultanément RTCM continu, commandes ponctuelles avec acquittement, voies RC et télémétrie PX4 essentielle ; comparer 333 Hz Full et 250 Hz EU-LBT, puis dégrader la RF et charger missions/paramètres hors phase critique. Relever occupation montée/descente, perte/retard et âge des corrections, état RTK float/fix, latence/erreurs de commandes, fraîcheur de télémétrie, files/overflow Backpack et réaction PX4 à la perte des corrections. Aucun succès si la commande RC ou les alarmes critiques deviennent indisponibles ; seuils chiffrés de marge, âge, latence et disponibilité à approuver avant exécution |

Avant exécution, figer versions PX4/ELRS/Backpack/QGC/EdgeTX, matériel,
paramètres, domaine RF et antennes, fichiers mission, modes utilisés et
critères de latence/marge/durée de perte. Choisir une version corrigée puis
la tester ; ne pas confondre minimum compatible et version qualifiée.
Les défauts de radio réelle ne sont pas reproduits par une simple coupure
de topic SITL. Pour une mission en Offboard, la perte du compagnon embarqué
et la perte du sol sont injectées séparément.

Les preuves attendues sont les paramètres exportés, journaux PX4/compagnon,
traces MAVLink et transitions d'autorité, statistiques radio/Backpack,
mesures électriques et positions/conditions terrain. Les simulations
utilisent les artefacts T0 ; le banc ajoute ses références instrumentales.

La capacité annoncée par ExpressLRS à 333 Hz Full est d'environ 735 octets/s
montants avec RC et 1470 descendants ; à 250 Hz, la montée n'est que d'environ
300 octets/s. La référence PX4 d'environ 300 octets/s pour RTCM/MAVLink 2
est indicative et ne mesure pas la base F9P multi-constellation retenue. Ces
valeurs ne suffisent pas à déclarer la RF commune apte : les retransmissions,
le profil EU-LBT, les défauts et l'âge des corrections doivent être mesurés.
Les commandes de déplacement testées ici sont ponctuelles ; les consignes
Offboard dynamiques sont produites localement par le Jetson et sa perte est
testée séparément. Sources :
[ExpressLRS MAVLink](https://www.expresslrs.org/software/mavlink/),
[PX4 RTK](https://docs.px4.io/main/en/advanced/rtk_gps) et
[PX4 Offboard](https://docs.px4.io/main/en/flight_modes/offboard).

Les délais de réaction et marges radio ne sont pas encore approuvés :
aucune qualification possible avant leur fixation. Aucun paramètre réel
n'est modifié par cette mise à jour documentaire.

<a id="demarrage-gazebo"></a>
### 9.2 Préparer le démarrage Gazebo — évaluation du 23 octobre 2026

**Cadrage.** La demande porte sur les tâches à prévoir, sans lancer de
simulation dans cette passe. Le premier résultat utile proposé est la reprise
supervisée du socle existant, puis un premier `VB01` simplifié et mesuré.
Cette préparation logicielle réversible ne clôt pas la priorité de faisabilité
physique du cartographe (§14.1). Le `x500` générique vérifie la chaîne logicielle ;
une estimation propre au prototype demanderait masse, centrage, inerties et
propulsion identifiés, puis une confrontation au banc. Arrêter l'évaluation
quand les prérequis, les sorties attendues et les inconnues sont identifiés ;
aucun achat, changement de version ou développement n'est engagé ici.

**Constats de lecture et contrôles locaux :**

- Le [Compose](../compose.yaml) configure `gz_x500`, monde `default`, domaine
  ROS `42`, API locale `8091`, télémétrie `8092` et Agent DDS UDP `8888`.
  `docker compose --profile sim --profile viz config` se résout correctement.
  Le client Docker `29.7.2`, Compose `5.5.0` et WSL `2.7.11.0` répondent.
  Le moteur Docker Linux est inaccessible depuis cette session ; l'inventaire
  des images/conteneurs n'a donc pas abouti. L'état des distributions WSL et
  des ports hôte reste inconnu, leurs contrôles étant refusés dans la session.
- Le [répertoire simulation](../simulation/README.md) contient seulement son
  README : aucun monde, modèle ou scénario agricole du §4.1 n'est livré.
  `px4-sitl` monte seulement `.runtime/px4`, sans ressources Gazebo du projet.
  Des paramètres PX4 persistants existent : les relever avant tout rejeu,
  plutôt que présumer un état initial vierge.
- Le [catalogue Offboard](../configs/visualization/simulations/px4_offboard.json)
  et le [contrat du runner](../software/src/drone_agricole_px4_bridge/src/RunnerContract.cpp)
  proposent uniquement `square` et `failsafe`, sans mission libre ni vitesse
  paramétrable. La station V3 y accède depuis **Bench** ; ses brouillons
  **Missions** ne sont pas des missions PX4 exécutables (DOC-SW §4.6).
- Les preuves C++ [carré](../results/simulation/px4_lot_a/sw0_cpp_square_20260902_1/result.json)
  et [perte Offboard](../results/simulation/px4_lot_a/sw0_cpp_failsafe_20260902_1/result.json)
  du 2 septembre sont présentes et annoncent succès et posé. Leurs cinq
  artefacts T0 existent, mais les manifestes historiques n'identifient pas
  commit/image/architecture et leur date de fin est nulle. Ils ne démontrent
  pas le fonctionnement de la révision courante ; AUD-010/014/015 restent
  pertinents pour une nouvelle preuve.

**Ordre de travail proposé — Planifié ; charges À valider :**

| Étape | Travail minimal | Signal de fin | Charge indicative |
|---|---|---|---|
| GZ-01 — accès et état initial | rendre le moteur Docker Linux accessible ; vérifier images, espace, ressources et ports ; identifier les paramètres persistants et les sources/binaires réellement utilisés ; reconstruire les seules cibles nécessaires si obsolètes | environnement et configuration d'exécution identifiés, sans supposer que les images locales correspondent aux sources modifiées | 0,5–1 jour |
| GZ-02 — reprise du socle | tests des contrats/verrous concernés, lancement `x500/default`, contrôle API et odométrie fraîche, carré puis perte Offboard supervisés ; vérifier posé et finalisation des résultats | quatre segments et posé, puis repli autonome PX4 observé ; résultats, erreurs et artefacts relisibles | 0,5–1 jour |
| GZ-03 — preuve exploitable | relever images exécutées, empreintes des sources et état Git modifié, paramètres et dates ; contrôler les contrats applicables à l'entrée et à la finalisation ; sélectionner une version stable PX4 compatible avec `px4_msgs`, épingler puis rejouer | preuve reliée au logiciel effectif et à sa configuration ; stable requise avant qualification formelle (§6.1) | 1–3 jours |
| GZ-04 — premier VB01 exploratoire | terrain plat et rangs simples en SDF avec collisions ; montage et chemin de ressources ; mission déterministe C++17 à une vitesse déclarée ; vérité terrain distincte, métriques, événements et archivage T0 ; intégration par contrats/services partagés UI/CLI | parcours reproductible, erreurs de suivi, distances, collisions et fin de mission observables ; seuils agricoles définis avant campagne qualifiante | 3–5 jours |

Ces charges d'ingénierie supposent le poste existant réutilisable, sans panne
majeure ni téléchargement/construction exceptionnellement longs. Prévoir
**1–2 jours pour reprendre les essais existants**, puis **4–8 jours
supplémentaires** pour stabiliser la preuve et obtenir le premier `VB01`
exploratoire. Ce sont des estimations, pas un budget approuvé. Après GZ-02,
réestimer les étapes suivantes sur les difficultés réellement observées ;
une panne d'environnement suspend la progression au lieu d'élargir la refonte.
GZ-03 est obligatoire avant une conclusion qualifiante, sans interdire une
exploration explicitement préliminaire sur le banc expérimental existant.
L'orientation précisée ensuite par le responsable retient le modèle du
cartographe pour les estimations physiques (§9.3). Le chiffrage ci-dessus
couvre le banc générique et le premier monde, pas ce modèle ni sa calibration.

Le démarrage actuel est **sans fenêtre Gazebo** (`HEADLESS=1`). Une interface
Gazebo interactive représente un lot optionnel estimé à **2–6 h** de mise au
point, hors total : définir et tester le passage d'affichage sur cet hôte.
Changer seulement `PX4_HEADLESS` ne fournit pas les accès d'affichage absents
de Compose. Le monde et ses modèles devront être accessibles au simulateur
([guide PX4 Gazebo](https://docs.px4.io/v1.17/en/sim_gazebo_gz/index)) ; la
compatibilité des définitions de messages doit être vérifiée lors de tout
changement PX4 ([guide ROS 2 PX4](https://docs.px4.io/main/en/ros2/user_guide)).

Avant des campagnes sans surveillance, borner et tester la fin de mission :
le délai global d'[OffboardTest](../software/src/drone_agricole_px4_bridge/src/OffboardTest.cpp)
exclut l'état d'atterrissage ; aucun délai automatique externe couvrant ce cas
n'a été trouvé dans les chemins runner/client inspectés. L'arrêt opérateur
existe ; aucun blocage réel n'a été observé pendant cette évaluation.

Un premier passage `VB01` à trajectoire prédéfinie n'implémente pas la
perception, l'évitement, la couverture agricole ni toutes les variantes
0,5/1/2 m/s. Les capteurs LiDAR/caméra/IMU, leurs bruits et horloges, la LIO,
les modèles dynamiques du prototype, `VB02` à `VB10` et AUTO/MANU/RF sont des
lots distincts à réestimer selon la question retenue. La tolérance interne
du carré n'est pas un critère agricole approuvé. `GATE-03` reste ouverte.

Validation de cette évaluation : lecture croisée des configurations, contrats,
preuves historiques et chemins d'arrêt ; contrôles d'environnement en lecture
seule. Aucun build, test exécutable ou scénario n'a été lancé : cette passe
évalue les travaux et le moteur Docker n'était pas accessible. Aucun statut
**Qualifié** supplémentaire n'est accordé.

<a id="fidelite-gazebo-cartographe"></a>
### 9.3 Modèle du cartographe pour portance et autonomie — Implémenté partiellement

**Choix du 23 octobre 2026.** Le responsable souhaite utiliser le modèle 3D
du drone avec la meilleure précision possible et priorise **autonomie,
consommation et capacité à voler avec la charge**. La source retenue et ses
lacunes sont dans [DOC-MEC §2.3](architecture/ARCHITECTURE_MECANIQUE.md#modele-gazebo-prototype).
Cette orientation soutient le bilan de faisabilité du §14.1. Le résultat utile
est une estimation par configuration et profil de mission, avec incertitudes,
limites et comparaison à des mesures. L'erreur acceptable et l'enveloppe de
validité restent **À valider** ; aucun pourcentage de précision n'est promis.

**Travaux à reprendre dans cet ordre :**

| Lot | Travail minimal et dépendance | Sortie attendue |
|---|---|---|
| CGZ-01 — configuration physique | réconcilier la BOM active avec les occurrences CAO, masses/inclusions, matériaux, équipement réellement conservé et sources disponibles ; résoudre la cote des hélices | une configuration identifiée, bilan de masse, inconnues et mesures minimales à obtenir ; aucune masse inconnue remplacée par zéro |
| CGZ-02 — dérivation CAO | exporter les visuels, définir des collisions contrôlées, repères et quatre rotors ; constituer masse/centre/inerties depuis les données sourcées | modèle SDF traçable aux natifs ; aperçus géométriques possibles avant clôture des paramètres physiques, conclusions dynamiques limitées aux données disponibles |
| CGZ-03 — vol chargé | relier géométrie moteur, ordre des sorties, axes, sens et allocation PX4 à un airframe SITL propre ; identifier poussée/couple/régime, transitoires ESC/moteur et traînée selon tension, charge, vitesse et vent | stationnaire et petits mouvements instrumentés, saturation et marge de poussée observables dans le domaine documenté ; aucune reprise implicite des coefficients du x500 |
| CGZ-04 — consommation et batterie | coupler demande propulsive et consommation électrique du couple exact moteur/hélice/ESC ; ajouter charges avioniques et rendements réels ; modéliser capacité utilisable, tension/chute sous charge, température et seuils BMS/PX4 | énergie et courant par phase de mission, état batterie cohérent, durée avant réserve/repli avec incertitudes ; source de batterie simulée unique et identifiée |
| CGZ-05 — calibration et validation | confronter d'abord aux données fabricant identifiées, puis au banc et aux essais autorisés selon §2 ; réserver des données indépendantes pour l'évaluation | écarts entre prédiction et mesure, domaine valide et décision de corriger/accepter le modèle selon critères fixés avant résultat |

Le modèle moteur multicoptère de Gazebo fournit notamment poussée en fonction
du régime, couple et constantes de réponse paramétrées ; la forme CAO ne
calibre pas ces coefficients et ne réalise pas une CFD du drone
([source officielle gz-sim8](https://github.com/gazebosim/gz-sim/blob/gz-sim8/src/systems/multicopter_motor_model/MulticopterMotorModel.cc)).
Pour la capacité à voler, confronter poids, centrage, poussée disponible et
saturation par moteur aux tensions et conditions étudiées, puis au banc.
Une valeur publicitaire du porteur ou une animation stable ne ferme pas
`MEC-MAS-001` ni `ELEC-PWR-002`.

**L'autonomie exige un modèle énergétique explicite.** La batterie SITL
documentée par PX4 suit des paramètres de décharge et de plancher ; elle ne
constitue pas un calcul de consommation du prototype
([PX4, batterie simulée](https://docs.px4.io/main/en/simulation/failsafes#low-battery)).
Le plugin batterie Gazebo demande également une consommation explicitement
définie ([Gazebo Battery](https://gazebosim.org/api/sim/8/battery.html)).
Vérifier le comportement de la version épinglée et la source réellement reçue
par PX4 avant toute conclusion d'endurance. Ne pas compter deux fois les
pertes ou l'avionique ; les 75 W/80 % historiques de DOC-ELEC §5.1 et la
réserve de 20 % de DOC-MEC §6.3 restent des hypothèses d'étude, pas des mesures
de la configuration courante. Inclure décollage, transits, travail, retour et
atterrissage dans le profil utile, avec l'énergie nécessaire au retour.

**Validation proposée — tests Planifiés, seuils À valider avant campagne :**

| Test | Exigence / objet | Vérification et preuve attendue |
|---|---|---|
| `T-CARTO-GZ-01` | `MEC-ARC-001` ; export et repères | empreintes natives/maillages/SDF, occurrences, unités, dimensions et écarts de collisions ; positions et axes rotors ; paramètres effectifs d'airframe |
| `T-CARTO-GZ-02` | `MEC-MAS-001` ; masse/centrage/inerties | provenance, inclusions et incertitudes par composant ; agrégation sans doublon ; inerties admissibles ; comparaison masse/centrage mesurés et données indépendantes disponibles |
| `T-CARTO-GZ-03` | `SAFE-REQ-001/002`, `ELEC-PWR-002` ; portance et dynamique | repos au sol, efforts/couples connus, stationnaire, petits échelons, carré, posé et perte Offboard ; saturation et sensibilité au pas physique ; comparaison poussée/régime/courant et transitoires du banc |
| `T-CARTO-GZ-04` | `ELEC-PWR-002`, `SYS-FUN-006` ; énergie et endurance | bilan électrique sans double comptage, capacité et tension sous profils réservés à l'évaluation ; comparaison énergie/courant/durée, réserve et transitions BMS/PX4 ; erreur et domaine de validité publiés |

Les exécutions conserveront les contrats T0 du §3, les données de calibration
et d'évaluation distinctes, versions, pas physique, graines éventuelles,
paramètres, états PX4 et raisons de fin. Un profil de mission et un état de
batterie connus ne sont pas remplacés par une durée choisie pour obtenir le
résultat attendu. PX4 conserve l'autorité du vol ; toute logique propriétaire
nécessaire aux modèles/mesures reste en C++17.

**Charge indicative, À valider après CGZ-01 :** 1–2 jours de réconciliation
documentaire, 2–4 jours de dérivation géométrique, 1–3 jours de bilan
masse/inerties une fois les données disponibles, puis 2–5 jours logiciels
pour la première identification propulsion/énergie après disponibilité des
mesures. Acquisition des données, préparation des bancs et qualification
expérimentale sont hors de ces charges ; aucun délai fiable ne peut leur
être attribué sans inventaire. La mise au point détaillée des images et du
LiDAR est différée ; leurs masses, placements et consommations doivent
néanmoins être intégrés au bilan physique. Revoir le chiffrage après la première configuration
réconciliée ; arrêter sur une donnée discriminante absente et désigner la
mesure nécessaire plutôt que prolonger une simulation non étayée.

**Réalisation ORCH-GZ-1, 23 octobre 2026.** La passe réalise les chemins
logiciels disponibles pour la priorité physique de §14, sur une seule CAO
active. Le proxy fabricant est réfutable par des mesures du couple exact ;
les 6/7/8 kg sont des scénarios, jamais la masse du prototype. Décisions
réversibles, aucun achat ni essai matériel. Budget : une configuration,
54 cas, 2 400 s simulées maximum par cas, processus énergie borné à 60 s
réelles et corrections limitées au lot avec revue indépendante. Arrêt sur défaut hôte identifié ou donnée
physique discriminante absente, en poursuivant les travaux indépendants.
Signal de sortie : preuve finalisée et reproductible, sans qualification
physique implicite. Le [manifeste du véhicule](../simulation/gazebo/models/cartographe/model_manifest.json)
référence sources, paramètres, preuves et commandes ; il ne remplace ni la
BOM ni le manifeste CAO. Modifications initiales du dépôt préservées.

| Contrôle exécuté / cible | Résultat et preuve | Limite |
|---|---|---|
| FreeCAD 1.1.3 / OCCT 7.8.1, Windows amd64 | 339 feuilles = 335 fixes + quatre rotors, 145 dépendances SHA, cinq STL ; 13 contrôles dont deux refus. [Géométrie](../simulation/gazebo/models/cartographe/geometry/geometry_tests.json), [collisions](../simulation/gazebo/models/cartographe/geometry/collision_model.json) | 21 boîtes/quatre disques pour sol plat, Basler invalide OCCT tessellé sans réparation ; Ø393,7 mm provisoire distinct du nominal fabricant 381 mm |
| BOM/CAO | 95 postes embarqués, sept masses documentaires, six inclusions. [Bilan](../simulation/gazebo/models/cartographe/geometry/mass_ledger.json) | masse totale, centrage et inerties physiques inconnus ; aucun sous-total historique repris |
| C++17 / GCC 16.2 / Qt 6, Windows amd64 | six CTest réussis : T0, sûreté, SDF, refus physique, masse, énergie ; énergie 34 contrôles ; T0 34 cas négatifs. [Vérification](../simulation/verification/orch_gz_1_checks.json) | ne qualifie ni Linux/arm64 ni ROS 2 |
| SDF et airframe | XML, cinq liens/quatre joints/quatre moteurs, empreintes, inerties de scénario et allocation FLU/FRD contrôlés. [Calculs](../simulation/gazebo/models/cartographe/model_checks.json) | scénario synthétique 6 kg, kT proxy, kM/réponse hypothétiques ; chargement Gazebo non exécuté |
| Énergie hors ligne | 54 cas finalisés : 5 profils terminés, 7 réserves, 39 saturations, 3 sous-tensions. [Synthèse](../simulation/verification/energy_checks.json), [T0 exact](../results/simulation/orch_gz_1/t0_energy/t0_run_manifest.json) | aucune trajectoire, décollage ou posé observé ; pas une autonomie PX4 |
| Annulation et finalisation hors ligne | annulation à 3 s, refus d'écrasement, entrées périmées/non finalisées refusées, CSV et cinq artefacts T0 contrôlés ; mêmes synthèses | annulation en vol et atterrissage restent à vérifier en SITL |
| Docker/Compose | socle et surcharge cartographe résolus, runtime séparé ; refus préflight code 2. [Préflight](../simulation/px4_sitl/verification/bench_preflight.json), [infrastructure](../simulation/px4_sitl/verification/infrastructure_checks.json) | moteur Linux absent après échec du socket local Docker Desktop ; aucun reset hôte |

Le point central **synthétique** 6 kg / SoC 100 % atteint la réserve à
1 366,936 s et 319,475 Wh au bus ; le profil de 210 s consomme 50,160 Wh.
À 7 kg, le proxy sature à 759 s en stationnaire et dès la demande initiale
du profil simple ; à 8 kg, immédiatement. Ces valeurs testent les décisions
logicielles et orientent les mesures ; **elles ne prédisent pas l'autonomie
ou la portance du prototype**. Les variations sont des hypothèses choisies
avant calcul, sans niveau de confiance. Points fabricant de calibration et
profils synthétiques d'évaluation sont distincts ; zéro comparaison physique.

**Banc et batterie ouverts.** Versions attendues : PX4 `v1.18.0-beta2` au
digest de Compose, `px4_msgs` 598c7aad… et Agent 73622810… ; compatibilité
effective à vérifier sur les topics versionnés de l'image reconstruite.
La bêta reste expérimentale. Les paramètres historiques, dont autostart
4001, sont conservés ; la surcharge utilise 4010 et `.runtime/px4-cartographe`.
WSL répond hors sandbox, mais Docker Desktop échoue à renommer
`sailor-ingest.sock` en `.stale` ; le pipe moteur reste absent. Les essais
carré/perte Offboard historiques ne sont pas rejoués sur cette révision.
Compilation ROS, odométrie fraîche, repos, stationnaire, posé/désarmement
et annulation SITL restent non exécutés. La source batterie effectivement
reçue par PX4 n'a pas été observée. Le modèle énergie est **hors ligne** ;
son contrat RPM est testé, aucun adaptateur Gazebo→PX4 n'est installé.
Une décharge forfaitaire PX4 n'est pas une estimation d'autonomie.

**Portée T-CARTO-GZ-01..04.** `01` : dérivation numérique réussie,
chargement restant ; `02` : bilan/agrégation testés, mesures manquantes ;
`03` : politiques de sûreté testées, vol chargé/SITL non exécuté ; `04` :
campagne proxy et contrats réussis, couplage et précision expérimentale
non validés. Aucun test déclaré physiquement **Qualifié**.

Le [protocole](../simulation/energy/measurements_protocol.json) prépare
inventaire/pesées, centrage/inerties, poussée-couple-RPM-courant du couple
exact, OCV/impédance/capacité utilisable et consommation simultanée des
rails, avec sessions indépendantes pour identification et évaluation.
Erreurs acceptables, répétitions, budgets et seuils matériels restent
**À valider** avant les essais autorisés selon §2.

La [revue indépendante](../simulation/verification/independent_review.json)
est favorable sur le périmètre numérique et hors ligne après correction
des chemins Gazebo, du scellement, du domaine de stationnaire, de la
conversion RPM et de la chronologie T0. Elle ne clôt pas les essais absents.

**Reprise exécutée le 24 octobre 2026.** Le démarrage Docker par le
responsable lève le blocage hôte constaté le 23. Le périmètre reste un seul
banc Linux/amd64, sol plat, carré de 2 m à 2 m de hauteur, stationnaire 3 s,
perte Offboard et annulation après décollage. Budget par essai : armement
10 s, étape 12 s, mission 100 s, posé 35 s ; superviseur externe borné.
Arrêt sur identité ambiguë, données périmées ou absence de posé confirmé.
Aucun appareil réel, achat ou essai matériel. Les preuves exactes et leurs
empreintes sont dans la
[campagne structurée](../simulation/px4_sitl/verification/campaign_20261024.json).

Critères fonctionnels du runner : chaque cible du carré à moins de 0,35 m
après au moins 1 s dans l'étape, puis stationnaire de 3 s ; en perte
Offboard, transition spontanée vers `AUTO_LAND` dans les 6 s suivant la
coupure, avant toute commande LAND de secours ; en annulation, motif
`signal_interrupt`. Dans tous les cas retenus, posé et désarmement frais,
résultat atomique et cinq contrats T0 valides sont nécessaires. Sur les
preuves courantes, la transition perte Offboard est observée après 1,05 s
pour cartographe et 1,20 s pour x500. Ces seuils fonctionnels ne qualifient
pas la précision du suivi, la stabilité prolongée ou les marges physiques.

La reconstruction ROS 2 Jazzy passe les quatre exécutables CTest du pont
(six cas GTest et une politique de sûreté autonome). Les sept CTest natifs
passent, dont T0 énergie (34 cas négatifs) et SITL (six positifs, 29 négatifs).
Les deux refus exécutables `execute=false` et `DRONE_AGRICOLE_SITL=0`
s'exécutent dans des conteneurs sans réseau, code 2 sans émission. Les sept
fixtures préflight vérifient notamment airframe ambigu ou non conforme.

Trois corrections d'intégration sont nécessaires : conserver aussi les
chemins officiels Gazebo dans `GZ_SIM_RESOURCE_PATH` ; remplacer l'identifiant
4010, déjà attribué à `gz_x500_mono_cam`, par **40000** ; ajouter un bruit de
capteurs **synthétique**, les mesures parfaitement constantes étant rejetées
comme bloquées par les validateurs PX4. Ces contrôles restent activés.
La fixture utilise σ gyro 0,001 rad/s, accélération 0,01 m/s², pression
1 Pa, magnétomètre Harmonic 0,0001 gauss ; elle ne représente aucune
calibration du prototype et sa graine n'est pas fixée. Le champ déclaré du
monde est ENU ; avec les coordonnées sphériques, Harmonic utilise sa table
géomagnétique. Aucun succès n'est attribué à la seule correction du champ.

Sur **cartographe synthétique 6 kg**, carré, perte Offboard et annulation
aboutissent avec posé/désarmement confirmés et cinq contrats T0 validés.
Le carré atteint 2,0071 m de hauteur relative maximale. Le repos Gazebo
est observé à z = 0,312505 m, cohérent avec le bas des patins. L'observation
des commandes des moteurs contient 47 valeurs à la limite effective
628 rad/s sur 44 932 valeurs : saturation transitoire présente, sans
durée ni phase déterminées par cette capture non horodatée. Ce sont des
commandes simulées, pas des mesures de RPM ou de courant matériels.

PX4 exécuté : commit `83c4f4e580558816f0e398918f66358988004696`, Gazebo
8.14.0. Les neuf messages utilisés du `px4_msgs` installé, commit 598c7aad…,
sont identiques par SHA aux définitions de cette révision PX4. Cette preuve
et le transport exécuté couvrent ces neuf types seulement. La bêta reste
expérimentale. Le modèle reçoit six cellules et le simulateur batterie
forfaitaire (`SIM_BAT_DRAIN=60`, plancher 50 %, courant instantané −1 A).
**Aucune estimation d'autonomie couplée n'est validée.**

Les nouvelles requêtes T0 précèdent le vol et archivent leurs sources dans
`source_snapshot/`. Le scellement refuse une source modifiée pendant l'essai ;
la validation ultérieure utilise ces copies. Les premiers x500 `_01` restent
historiques, relus positivement lors de leur scellement ; leurs références
directes signalent désormais l'empreinte obsolète après correction du banc.
Ils ne sont ni réécrits ni utilisés comme preuve courante.

Les régressions x500 `_02` carré/perte Offboard/annulation sont également
réussies et validées, avec sources archivées : **six résultats courants**
au total. Le pont d'affichage confirme ensuite le désarmement des trois
régressions. Son cache HTTP est contrôlé par l'âge absolu de
`bridge_time_ns` en plus des âges des topics ; quatre fixtures vérifient
ce durcissement final, ajouté après les vols. Les preuves cartographe
immédiates peuvent encore afficher `armed=true` sur une publication en
retard ; le runner a confirmé le désarmement sur son abonnement direct,
et l'état désarmé a été contrôlé avant tout changement de banc.

`T-CARTO-GZ-01` couvre désormais aussi chargement et allocation effective ;
`03` dispose de premiers vols exploratoires avec posé et annulation.
`02` reste suspendu aux masses/CG/inerties réels ; `04` conserve les 54 cas
hors ligne et attend la source batterie couplée et les mesures exactes.
Les échelons dédiés, sensibilité au pas, vent, variations dynamiques de
charge/centrage/SoC et comparaison expérimentale restent **À valider**.
La revue indépendante de cette reprise est référencée par la campagne.

<a id="orchestration-gazebo"></a>
### 9.4 Réalisation par orchestrateurs successifs — Planifié

**Précision utilisateur du 23 octobre 2026 :** les trois domaines proposés
doivent être réalisés, dans l'ordre ci-dessous. Les prompts d'orchestration
doivent demander l'implémentation, les tests et la consolidation de chaque
lot. Ils ne constituent pas une autorisation d'achat ou d'essai physique.

| Lot | Périmètre | Base attendue pour la suite |
|---|---|---|
| `ORCH-GZ-1` | reprise du banc, dérivation CAO active, masse/centrage/inerties, véhicule PX4, propulsion et énergie ; CGZ-01..05 | modèle, paramètres et scénario minimal traçables ; preuves de fonctionnement ou prérequis d'exécution manquants explicités ; incertitudes physiques conservées |
| `ORCH-GZ-2` | stabilité, suivi de trajectoire, vent, variations de charge/centrage/état batterie et fautes PX4 ; régressions énergie | campagne dynamique reproductible, métriques et états d'arrêt ; baseline identifiée et effets des modifications mesurés |
| `ORCH-GZ-3` | modèles détaillés Airy/Basler/IMU/GNSS, temps et bruits, couverture, localisation/perception/cartographie et extension incrémentale de VB01 à VB10 | chaîne capteurs/cartographie évaluée sur vérité terrain séparée, limites et scénarios exécutés explicités ; aucune qualification implicite des fils ni du traitement |

Chaque orchestrateur reprend les sources et preuves du dépôt. Le premier
créera, s'il est absent, le manifeste technique léger
`simulation/gazebo/models/cartographe/model_manifest.json` ; les suivants
le contrôleront puis le feront évoluer en place. Il référencera sources et
empreintes, paramètres et provenance, unités/repères, configuration PX4,
source batterie, résultats exacts, limites et commandes de reproduction,
sans se substituer à la BOM ou au manifeste CAO. Ce manifeste est désormais
**Implémenté** par ORCH-GZ-1, avec les limites du §9.3.

Les investigations indépendantes sont déléguées avec propriétaires de fichiers
distincts ; l'orchestrateur consolide les analyses avant l'implémentation et
intègre seul les fichiers partagés et documents vivants. Une review indépendante
intervient après intégration. Les trois orchestrateurs ne sont pas lancés
simultanément sur le même banc. La qualification physique complète du lot
précédent n'est pas un prérequis général au suivant : contrôler les dépendances
réellement nécessaires, poursuivre les travaux indépendants et suspendre
seulement les conclusions qui dépendent des mesures absentes.

**Relais ORCH-GZ-2.** Dérivés CAO, collisions sol plat, générateur SDF/airframe,
agrégateur massique, énergie et contrats T0 sont disponibles. Le 24 octobre,
Docker, le pont ROS reconstruit, l'identité, les neuf types utilisés et les
premiers vols cartographe sont vérifiés (§9.3). ORCH-GZ-2 peut reprendre
cette baseline synthétique avec ses preuves de posé et finalisation, en
vérifiant à nouveau l'état courant. Le raccordement d'une source
batterie modèle unique manque pour les essais couplés. Les scénarios
synthétiques identifiés permettent des essais exploratoires ; une conclusion
sur le prototype exige les données physiques manquantes. Les commandes
sont dans [simulation/README.md](../simulation/README.md).

## 10. Résultats station et contrats

- T0.1 : sept contrats métier et huit schémas JSON, avec sélection par
  capacités ;
- T0.2 : cinq runners autorisés, validation côté service et une seule exécution
  active ; les smokes FAST-LIO2 et PX4 ont produit les cinq artefacts T0 ;
- T0.3 : index reconstruisible de 59 résultats historiques, dont 52 LIO et
  7 PX4 ; neuf archives LIO sans métriques restent identifiées comme incomplètes ;
- T0.4 : comparaison de deux à quatre archives compatibles, superposition et
  rapport sans relancer les algorithmes ;
- migration propriétaire C++17/Qt 6 : terminée pour le périmètre SW0 ;
- refonte évolutive : séparation application/domaine/algorithmes/adaptateurs,
  cycle `RunService` partagé par UI et CLI, navigation et pages persistantes
  validés sous Windows ;
- compatibilité des archives : conservée en lecture ; leur format n'est pas
  réécrit silencieusement.

Les futures fonctions de réception de paquets, construction globale, édition,
approbation/signature de carte, exécution de mission et transfert ne sont pas qualifiées.

<a id="station-v3"></a>
### 10.1 Station métier V3 issue de MagicPath — 23 octobre 2026

**Implémenté ; conclusion préliminaire limitée au poste Windows 11 x64.**
Les deux révisions MagicPath identifiées par
[`magicpath_reference.json`](../configs/station/magicpath_reference.json)
ont été lues via MCP, code et aperçus compris. Leur même structure fonctionnelle
est transposée en Qt 6 Widgets, avec thèmes bleu/vert sélectionnables et
persistants, sans importer leurs données fictives. Les décisions et limites
fonctionnelles sont dans [DOC-SW §4.6](architecture/ARCHITECTURE_LOGICIELLE.md#46-interface-métier-v3--23-octobre-2026).

Protocole : configurer et compiler `ci-windows` depuis la racine, exécuter
CTest, vérifier les 21 routes visibles, le retour au bench et sa configuration,
la création d'un nouveau formulaire, les changements de thème, les captures
et le format portable 1200 × 760. Les tests de services utilisent des fixtures
temporaires ; les régressions de cartographie conservent les données locales
EscaYard et FriûlBot. Le fichier
[`station_magicpath_v3.json`](verification/station_magicpath_v3.json)
porte les commandes, versions, empreintes et résultats de cette passe.

| Exigence | Composant / vérification | Résultat et limite |
|---|---|---|
| `UI-V3-001` | shell, six espaces et thèmes ; `test_station_navigation`, `test_workspace_pages`, captures | routes et contexte, deux thèmes et réglage persistant ; rendu desktop contrôlé |
| `UI-V3-002` | `WorkspaceService`, stockage atomique, BOM ; `test_workspace_service` | brouillons non exécutables, valeurs inconnues, import sans écrasement d'identité, état corrompu conservé, concurrence et lecture canonique |
| `UI-V3-003` | résultats/comparaison/analyse ; `test_workbench_pages`, `test_dashboard_mapping` | recherche/favoris, liens externes malgré filtres, comparaison, artefacts réels et régression cartographique |

La suite complète a passé **23 tests CTest sur 23**, en 92,09 s, dont
71,26 s pour la régression cartographique. Le premier passage avait cinq échecs
d'écriture dans le TEMP isolé Windows ; TEMP et TMP ont ensuite été placés
sous `.runtime/station-v3/tmp`, sans modifier ces tests pour masquer un échec.
Les dernières corrections de disposition font l'objet d'une nouvelle
compilation réussie puis de **5 tests UI CTest sur 5** en 3,76 s.
La capture des 21 routes, des deux thèmes et du format 1200 × 760 a été
rejouée avec succès après ces retouches ; les 25 captures sont liées par
empreinte dans la preuve.

Les journaux et captures restent locaux dans `.runtime/station-v3/`.
La CLI `station-workspace --action diagnostics` lit la même source que l'UI.
Le chargement des schémas station est distinct du catalogue T0 ; les contrôles
des brouillons sont effectivement codés et testés, sans prétendre fournir
un moteur JSON Schema général ni fermer AUD-010.

Ni PX4 SITL, ni banc matériel, ni vol, ni Linux/`arm64` n'ont été exécutés
pour cette refonte desktop. Les commandes de mission réelles, transferts,
approbations cartographiques, pilotes et diagnostics embarqués demeurent
**Planifiés / À valider**. Cocher un contrôle ou lire une ligne de BOM
ne produit aucune autorisation de vol ni qualification du matériel.

### 10.2 Passerelle du modèle 3D vers Gazebo — 24 octobre 2026

**Implémenté ; validation logicielle limitée à Windows amd64.** `UI-GZ-001`
relie la demande de préparation depuis Simulations à `GazeboExportService`,
son port, le backend local et la page `GazeboModelPage` ; `T-CARTO-GZ-01`
couvre les dérivés, unités et format du véhicule. La préparation crée un
nouvel artefact ; elle ne remplace pas les preuves de vol du §9.3.

Protocole : compiler la station `ci-windows`, tester service et page avec
fixtures autonomes, créer un dossier depuis les maillages existants puis
réaliser la conversion complète depuis la CAO avec Python FreeCAD 1.1.3.
Vérifier les empreintes d'entrée/sortie, quatre rotors, repères en mètres,
SDF/config/airframe présents et absence de modification des natifs ; faire
lire puis charger le modèle par Gazebo. Tester les refus de source périmée,
maillage altéré, destination existante/hors projet, Python absent, verrou
concurrent, annulation et relance depuis le signal de fin. Critère de
publication : sources inchangées et dossier finalisé complet ; une annulation
ne publie aucun nouveau dossier. Le worker doit être arrêté avant sa fin.

La [preuve structurée](verification/station_gazebo_bridge.json) référence les
commandes, exécutables, paquets, captures et journaux exacts. Les sept CTest
ciblés station passent, ainsi que les deux tests du générateur autonome.
La conversion CAO réelle et la réutilisation contrôlée des maillages passent.
L'annulation réelle pendant FreeCAD retourne 130 sans dossier publié.
Gazebo 8.14.0 répond `Valid` au SDF et charge le paquet pendant 1 000 pas,
dans un conteneur sans réseau, sans PX4 ni armement. Les avertissements de
namespace moteur et de balise `motorNumber` dépréciée restent non bloquants
sur cette version ; aucune compatibilité avec d'autres versions n'est déduite.
La capture réelle du parcours et les tests UI confirment navigation, aperçu,
progression, contrôles et finalisation. Les sources et gros résultats restent
hors Git selon leur politique ; la synthèse légère assure leur traçabilité.

Le premier test dans le TEMP isolé Windows et un test UI bloqué ont été
diagnostiqués ; les nouvelles fixtures utilisent leur dossier de travail,
et la suite finale est exécutée avec accès normal au TEMP. Aucun échec n'est
masqué par un succès antérieur. La revue indépendante a fait corriger l'ordre
de contrôle de la copie du monde et la publication trop précoce de `completed`.
Le profil reste celui du prototype actif ; aperçu simplifié, physiques
provisoires, absence d'autonomie couplée, Linux/arm64 et import arbitraire
restent À valider ou hors périmètre. Aucun nouveau vol n'est revendiqué ici.

## 11. Résultats de cartographie

### 11.1 Régression EscaYard B7

Le calcul indépendant traite les 6 583 772 points sans utiliser les RTK pour la
prédiction. Il produit 24 507 cellules de végétation, 888 050 points végétation,
une orientation de 53°, 32 axes et 31 trajectoires candidates. Après évaluation,
l'écart transversal RTK vaut 0,213 m médian, 0,309 m RMSE et 0,609 m P95 ;
98,55 % des troncs sont à moins de 0,75 m d'un axe.

Ces valeurs sont préliminaires **À valider** à cause des CRS distincts, du datum
vertical inconnu et de l'absence d'appariement un-à-un. L'empreinte de la
prédiction est identique avec ou sans ouverture des références. Le résultat
porte `mapping_safe=false` et ne produit aucun ordre PX4.

### 11.2 FriûlBot LiDAR–caméra

La première preuve à +120 s produisait 16 382 points, 1 779 projections
rouge/NIR (10,86 %), trois axes et deux trajectoires. Après ajout de la fusion
RGB, la preuve courante à +120 s produit 21 155 points de scène, 1 750 points
RGB, trois rangs et deux trajectoires locales candidates. Les 19 suites CTest
Windows passent et la preuve locale est sous `.runtime/cartographie-rgb/`.

La convention exacte des extrinsèques, l'appariement ordinal des captures, le
seuil d'occultation et les corrections radiométriques restent **À valider**.
La variante d'assemblage et de maillage observé est désormais implémentée dans
les limites de la section suivante. Les corridors navigables et la simulation
du passage du drone de traitement ne sont pas encore livrés.

### 11.3 Assemblage ICP et surface FriûlBot

La variante `scan_surface_v1` a traité la fenêtre +120 à +130 s du bag brut.
Le résultat `63c80faa` a accepté les **23 scans sélectionnés**, couvrant
9,843 s entre premières et dernières mesures, et produit **61 903 triangles**.
Cinq captures ont apporté des couleurs. Le déplacement estimé entre première
et dernière pose est d'environ 5,64 m. Le recouvrement minimal mesuré est de
89,1 % et le plus grand résidu ICP de 0,215 m. Ce résidu mesure les
correspondances entre scans, **pas une erreur absolue de localisation**.
Toutes ces valeurs et l'usage opérationnel sont **À valider**.

Le test `test_scan_reconstruction` vérifie un déplacement connu à six degrés
de liberté, le rejet de scans sans recouvrement et de géométrie colinéaire,
les surfaces verticales, les trous, la fusion des couleurs/sommets et le
respect des capacités sans mutation en cas de refus. `test_vineyard_map`
vérifie la lecture du maillage, l'état partiel et le rejet d'indices invalides.
`test_dashboard_mapping` exécute les variantes capture et surface, vérifie le
rejeu du maillage et de la trajectoire, l'export PLY et la conservation de la
page pendant le traitement. La suite Windows comporte **20 suites CTest
réussies** ; le parcours surface réel a été exécuté sans saut de test.

Preuves locales hors Git : `.runtime/scan-surface/` et
`results/simulation/vineyard_capture_mapping/scan_surface_v1_20260909T204144Z_63c80faa/`.
Le PLY est une surface ouverte des mesures observées. Les trous ne sont pas
assimilables à de l'espace libre. Aucun essai de collision, de dynamique de vol
ou de pulvérisation n'est validé par ce résultat. Linux/ROS 2 et ARM restent
**À valider** pour cette extension.

## 12. Vérifications mécaniques, électriques et réseau

Les preuves durables sont référencées depuis DOC-MEC et DOC-ELEC et conservées
auprès des assemblages :

- manifeste CAO et nomenclature des pièces ;
- contrôle des liens externes et des placements d'assemblage ;
- bilans de masse, charge sur isolateurs et autonomie ;
- contrôle d'encombrement, accessibilité de la cassette batterie et verrouillage ;
- continuité, polarité, chute de tension, protection et échauffement du faisceau ;
- tests de synchronisation, débit, perte de liaison et vieillissement des
  timestamps.

Les choix mécaniques et électriques candidats ne sont pas qualifiés par leur
seule présence en CAO ou dans une BOM. Les essais physiques correspondants
restent **À valider** tant qu'aucun résultat vérifiable n'est référencé.


### 12.1 Cartographe — corrections capteurs et pile avionique, 15–16 septembre 2026

Environnement : Windows `amd64`, moteur FreeCAD 1.1.3. Les sources fabricant
restent inchangées. Les placements du châssis sont évalués sur les feuilles
avec leur transformation globale ; les équipements OEM historiquement exclus
ne sont pas comptés comme montés.

| Exigence | Composant / contrôle | Résultat et preuve |
|---|---|---|
| `MEC-VIB-001`, `MEC-INT-001` | Airy +4 mm X avec ses perçages P16, retenue câble -3 mm Y ; huit translations discrètes | aucune interférence dépassant 10⁻⁶ mm³ sur ce périmètre ; `verification/correction_capteurs_20260915.json`, complément global du 16 septembre |
| `MEC-VIB-001` | équilibre statique idéal du bloc, masses et positions estimées | réactions d'environ 131 à 194 g/appui ; `verification/dimensionnement_isolateurs_20260915.json` ; dynamique et masses réelles **À valider** |
| `MEC-AVI-001`, `MEC-INT-001` | deux niveaux sur ancrages OEM, P06/P20–P22, retenues et visserie | aucune collision volumique détectée dans la configuration nominale testée ; `verification/avionique_empilee_20260916.json` |
| `MEC-ARC-001` | références réutilisées, matrices, liens et quantités SA03 | review indépendante : 48 occurrences, 27 sources, matrices comparées à 10⁻⁹ ; aucun écart ; contrôles après réouverture dans `verification/reouverture_finale_20260916.json` |
| outillage électronique | pont MCP KiCad local, projet factice | inventaire de 233 outils, création/relecture et netlist réussis ; `hardware/electronique/cartographe/verification/kicad_mcp_probe_20260915.json` ; aucun circuit drone testé |

La réouverture finale dans un processus neuf a recalculé **85 documents**,
contrôlé **118 occurrences** et vérifié **17 pièces natives** : aucune erreur
d'objet, de lien, de matrice ou de validité de solide n'a été détectée. Les vues
isométrique et de face de SA03 ont été inspectées ; leurs empreintes sont dans
`verification/controle_visuel_capture_20260916.json`.

Les chemins abrégés `verification/` ci-dessus sont relatifs à
`hardware/mecanique/cartographe/`. Les exports actualisés sont ceux des
répertoires `exports/iteration_20260915/` et `exports/iteration_20260916/`.

Les seuils de volume et de comparaison de matrices sont des tolérances
numériques de contrôle ; ce ne sont pas des jeux fonctionnels approuvés.
Le contrôle capteurs exclut la déformation des élastomères et ne couvre ni les
rotations ni le balayage continu. La review indépendante a contrôlé fichiers,
matrices et empreintes ; elle n'a pas répété les opérations OCCT.

Les essais physiques n'ont pas été exécutés : matériel et procédés non
confirmés. Restent **À valider** : références réelles, câbles/connecteurs,
accès outils, tenue des sangles/fraisures, couples et appuis sous carbone,
isolation des vis traversantes, vibrations, calibration, thermique, CEM,
masse/centrage et vol. Les deux contacts historiques Jetson restent ouverts.
Les 2,8 mm disponibles au-dessus du DC/DC (2,2 mm sangle comprise) imposent une
revue des connexions avant fabrication. La conclusion est **conforme pour les
contrôles CAO déclarés**, avec la qualification du matériel **À valider**.

### 12.1.1 Batterie 6S — variante de berceau fixe et capot captif, 2 octobre 2026

Périmètre : nouveaux natifs candidats P23–P26 et sous-assemblages de batterie
16/20 Ah, séparés du drone actif ; DOC-MEC §4.1.1. La capacité, les matériaux,
le loquet et les interfaces restent **À valider**. L'enveloppe maximale de
la 20 Ah comprend des tolérances d'étude qui ne sont pas des données fabricant.
Environnement de contrôle : Windows `amd64`, Python fourni avec FreeCAD 1.1.3,
processus séparé ; aucune commande de drone ni simulation de vol.

| Test / exigences | Protocole et critère du contrôle préliminaire |
|---|---|
| `T-BAT-CAO-01` / `MEC-ARC-001` | ouvrir et recalculer dans un processus neuf ; arbres CSG/paramètres présents, solides valides, liens résolus, fichiers/objets/matrices conformes au manifeste ; empreintes des fichiers actifs inchangées |
| `T-BAT-CAO-02` / `HW-BAT-SWAP-04` | comparer les deux enveloppes nominales et maximales aux appuis et au capot fermé ; volume commun nul hors contacts d'appui ; relever les jeux et la cale 20 Ah |
| `T-BAT-CAO-03` / `HW-BAT-SWAP-01/04` | capot aux positions discrètes entre 0 et 110° puis sortie verticale de chaque pack ; aucune collision volumique sur le périmètre modélisé ; la cinématique réelle du loquet est exclue |
| `T-BAT-CAO-04` / `MEC-INT-001`, `HW-BAT-SWAP-02` | comparer les nouvelles formes aux feuilles OEM avec leurs placements globaux, à l'avionique et au SBS/P15 courants ; sonder la matière autour des ancrages centrés sur les lumières OEM |

Résultat **préliminaire** : neuf références natives valides, deux
sous-assemblages et quinze liens contrôlés après réouverture/recalcul dans
un processus neuf, sans erreur. Les matrices du manifeste correspondent aux
occurrences fermées ; les fichiers de la configuration active et le contenu
préexistant du manifeste sont conservés. Les commandes d'angle 0/45/110°
ont été vérifiées sur les expressions natives.

Pour chaque capacité, aucune collision volumique n'est détectée sur les
23 positions du capot (0…110°, pas 5°), ni sur les douze positions de sortie
verticale (packs nominal/maximal, décalages Z0/5/20/50/100/200 mm).
L'intégration externe contrôle 358 obstacles BRep par variante et relève
neuf distances ciblées contre trois petites feuilles OEM ; aucun volume
commun supérieur au seuil numérique n'est détecté. L'intersection initiale
de 110 mm³ avec P15 est corrigée par une encoche du seul P23 candidat,
avec jeu géométrique d'étude de 0,5 mm. Les trous candidats ont de la matière
autour de leur axe au rayon de sondage 2,5 mm, sans démonstration de résistance.

Preuves relatives à `hardware/mecanique/cartographe/` :

- [construction et mouvements internes](../hardware/mecanique/cartographe/verification/construction_berceau_fixe_candidat_20261002.json) ;
- [intégration externe des deux variantes](../hardware/mecanique/cartographe/verification/integration_berceau_fixe_20261002.json) ;
- [réouverture, manifeste et empreintes](../hardware/mecanique/cartographe/verification/controle_berceau_fixe_manifest_20261002.json).

Les vues fermé/ouvert 16/20 Ah ont été inspectées à partir des maillages
des formes natives ; leurs empreintes sont consignées avec les exports.
L'intégration utilise les 27 exclusions OEM historiques explicites ; le
plateau `Part__Feature311` reste contrôlé. Le module RTK historique fourni
en mesh sans BRep est exclu du calcul volumique et signalé dans la preuve,
tandis que son support et l'antenne restent contrôlés. La nouvelle pile
CA01/Holybro n'est pas substituée dans ce contrôle.

La revue indépendante est favorable sur ce périmètre : réouverture des
deux sous-assemblages, quinze liens, paramètres/angles natifs et empreintes
concordants. Elle souligne que la retenue sous efforts dans toutes les
directions en position fermée n'est pas vérifiée par les tests d'ouverture
et d'extraction. Cette limite reste **À valider** ; la revue est consignée dans
`hardware/mecanique/cartographe/verification/revue_berceau_fixe_20261002.json`.

Le seuil de volume commun 10⁻⁶ mm³ est une tolérance numérique de contrôle,
pas un jeu fonctionnel approuvé. Un balayage discret ne démontre pas tout
le mouvement continu. Les formes simplifiées de batterie et de loquet ne
représentent ni fils, ni connecteurs mobiles, ni déformation du pack.

Les essais physiques sont **Planifiés / À valider** : montage sur le plateau
réel avec accès aux écrous/rondelles et blocage du glissement ; verrouillage
complet et incomplet, visibilité de l'état fermé et sécurité d'ouverture ;
tenue sous efforts établis à partir du profil de vol approuvé ; vibrations,
chocs et cycles ; échange avec gants et poussière en moins de 30 s ;
absence de pincement, abrasion, compression excessive et traction sur le SBS.
Les charges, nombres de cycles, matériaux et critères d'usure doivent être
fixés avant essai. Aucun essai de banc, fabrication ou vol n'est couvert ici.

### 12.1.2 Batterie interplateaux — préétude dimensionnelle, 2 octobre 2026

Exigences concernées : `MEC-INT-001`, `MEC-BAT-001`, `HW-BAT-SWAP-01/02/04`
et `MEC-MAS-001`. Environnement : Windows `amd64`, FreeCAD 1.1.3 dans un
processus séparé sans sauvegarde de CAO. Périmètre : mesure des plateaux et
colonnes OEM, confrontation aux enveloppes de pack 16/20 Ah et aux occupants
actuels, scénarios dimensionnels de rehausse en mémoire ; DOC-MEC §4.1.2.

Le logement visé mesure 50 mm entre Z33 et Z83. Les hauteurs nues
65/58 mm ne rentrent pas. Avec enveloppes maximales 67/60 mm et provision
de 9 mm pour appuis/protection/jeu, le besoin libre est 76/69 mm, soit
26/19 mm de rehausse minimale. Les options arrondies +30/+20 mm sont
**À valider** ; elles ne sont pas une conception de nouvelles entretoises.
Le Pixhawk, sa platine, son isolant et sa sangle occupent actuellement le volume
et doivent faire l'objet d'une nouvelle implantation.

Les disques d'hélices ne figurent pas dans le modèle OEM. Le calcul géométrique
avec diamètre hypothétique 381 mm et axes moteurs issus de la CAO donne
78,81 mm entre les disques à l'endroit étroit du trajet +X ; il ne reste que
0,41 mm par côté d'un pack de 78 mm, hors mains/fils/tolérances. Le Z exact
du plan d'hélice n'est pas connu et toute enveloppe de disque testée est
une hypothèse. Aucun passage réel ni dégagement de pales n'est qualifié.

Preuve et protocole reproductible :
`hardware/mecanique/cartographe/verification/logement_interplateaux_20261002.json`
et `verify_logement_interplateaux_20261002.py`. La coupe de principe associée
a été inspectée ; elle représente les hauteurs d'étude et non un nouvel
assemblage fabriquable. Résultat **préliminaire** : douze scénarios en mémoire,
soixante positions discrètes d'extraction OEM et vingt positions avec disques
hypothétiques contrôlées, aucune erreur de recalcul et empreintes CAO
avant/après identiques. Dans les scénarios sans SA03, le pack maximal 20 Ah
passe avec +20 mm, et le 16 Ah avec +30 mm, aux cinq translations X testées.
La présence de SA03 conserve les collisions avec le Pixhawk et sa sangle.
Les extensions de colonnes sont des cylindres illustratifs Ø5, sans visserie,
filetages ou structure nouvelle conçus.

La revue indépendante confirme les mesures, les calculs de rehausse et la
cohérence des limites, sans finding bloquant. Elle distingue rangement
statique, extraction, enveloppes absentes et migration de l'avionique.
Résultat et empreintes : `verification/revue_logement_interplateaux_20261002.json`
auprès de la preuve mécanique.

Non exécutés : nouvelle CAO structurelle de rehausse/verrou, placement de
l'avionique cible, tolérancement de fabrication, rigidité/vibrations,
mesure des hélices réelles, accès avec gants/câbles, pesée/centrage et vol.
Ces étapes nécessitent les interfaces et matériels réels ; aucune qualification
physique ne découle de cette préétude.

### 12.1.3 Cassette 6S 20 Ah et rehausse20mm, 2–3 octobre 2026

Résultat historique avant la migration de l'étage énergie et le raccordement
direct du pack (§12.1.8). Les quantités, coupes, retenues P41/P53 et essais
ci-dessous décrivent cette ancienne configuration ; ils ne certifient pas
la définition ni les fichiers courants.

**Périmètre : CAO native FreeCAD1.1.3, Windows, variante20Ah.** La capacité
20 Ah et la rehausse20mm sont choisies pour cette implémentation, sans
qualification matérielle. Les anciennes preuves de berceau et de faisabilité
restent historiques. Les scripts de construction conservent les originaux,
créent des références distinctes et assemblent par liens externes.

| Test / besoin | Protocole et preuve | Interprétation |
|---|---|---|
| `T-BAT20-NATIF` / `MEC-ARC-001` | reconstruire les natifs, fermer, rouvrir dans un nouveau processus et recalculer ; comparer sources, liens, formes finales et matrices ; `hierarchie_20Ah_20261002.json`, `reouverture_rehausse20_avionique_20261002.json` | réussite de représentation native, sans qualification des pièces |
| `T-BAT20-INSERT` / `HW-BAT-SWAP-01/04` | volume commun au verrouillage puis balayage des frontières mobiles sur300mm et poses de0à300mm parpas1mm ; géométries positives conservatrices pour faces nonextrudables ; `integration20Ah_20261002.json` | absence d'interférence limitée aux volumes couverts ; les interfaces fonctionnelles et anomalies STEP restent identifiées séparément |
| `T-BAT20-FIX` / `MEC-INT-001` | placer vis, rondelles, écrous et poches dans les solides finaux ; vérifier rails/P38, fonds/captures, loquet, contacts et capots | une vis nominalement bien placée ne démontre ni résistance ni serrage |
| `T-BAT20-CONTACT` / `HW-BAT-SWAP-02` | comparer plans et STEP officiels, coteA12,7mm et positions de puissance ; `construction_contacts20Ah_20261002.json` | compatibilité de catalogue ; anomalies de cavités STEP et engagement réel à confirmer |
| `T-BAT20-PROP` / `MEC-INT-001` | enveloppes de quatre rotors15pouces ; comparaison àposition verrouillée et durantcourse avec pales parallèlesX381×40×4mm | hypothèse de pale stationnaire à mesurer ; orientation libre pendant échange produit des collisions |
| `T-BAT20-BOM` / `MEC-BAT-001` | comparer quantités effectives CAO, standards, MPN, source fabricant et pièces de coupe ; `bom_dock20Ah_20261002.json`, `sources_bom_dock20Ah_20261002.json` | nomenclature de prototype, pas preuve de courant admissible, approvisionnement ni conformité de masse |

**Résultat final du3octobre2026, après correction des appuis des écrous M4
de butée :** dock181occurrences, hiérarchie575liens. Les99éléments mobiles
et445fixes du drone représentés passent la course continue300mm ainsi que
les301poses espacées de1mm : **zéro obstacle hors interfaces fonctionnelles
TE déclarées**. Toutes les paires de course sont couvertes ; aucune vis ni
aucun support n'est exclu. Les volumes internes des logements/contacts TE
et les représentations de filets/cavités des quatre bornesM5 restent bruts
et séparés du bilan. Position verrouillée, fixes dock/drone et interfaces
internes hors ces représentations sont libres. Les empreintes restent
inchangées durant l'exécution ; `finalisation_correcte=true` et certificat
continu complet dans `integration20Ah_20261002.json`. L'état sauvegardé
ExtractionX=0 et le SHA du dock sont consignés dans cette preuve.

Les enveloppes de pales parquées parallèlesX donnent zéro intersection ;
les rotors en position verrouillée aussi. En orientation libre durant
l'échange,50cas d'interférence sont détectés : le résultat d'insertion est
donc **conditionnel au stationnement des pales**, et leur largeur40mm est
une hypothèse à contrôler. Le modèle RTK maillé reste hors contrôle BRep.

La relecture native de la rehausse donne334liens, zéro erreur et zéro
collision sur son périmètre. `controle_manifest_dock20Ah_20261003.json`
confirme575liens et matrices, sans erreur ;
`review_bom_dock20Ah_20261003.json` confirme quantités et empreintes.
La BOM comprend27références fabriquées,34devisserie et25lignes commerciales.
Le classeur est contrôlé contre ces valeurs par
`controle_classeur_bom20Ah_20261003.json`, avec inspection visuelle des trois
feuilles ; aucune qualification dans MicrosoftExcel n'est revendiquée.
`preservation_dock20Ah_20261002.json` confirme131fichiers antérieurs inchangés.
La revue indépendante a vérifié les portéesP53, le serrage transmis au
module, les retenues et les quatre écrous désormais en appui surP35.

Les modèles de logement TE sont conservés **inchangés**. Leurs cavités
internes simplifiées produisent un recouvrement des guides àla cote de
montage du plan et des recouvrements avec les contacts insérés. Une dérivée
d'analyse prolonge les profils de guide sous forme de coupes natives ;
cette dérivée n'est ni une modification d'achat, ni une correction approuvée
par TE. La preuve conserve les volumes bruts et dérivés et ne transforme
pas les recouvrements restants en résultat«zéro». Une course de cassette
libre par rapport au châssis **ne clôt donc pas** l'engagement physique de
la paire de connecteurs. Il faut confronter les deux pièces ou obtenir les
cotes fonctionnelles fabricant avant de déclarer l'absence de blocage complète.

Les défauts mécaniques détectés sont corrigés dans la conception : portée
de butée qui accrochait le loquet, vis de rails dans le passage des flanges,
têtes de fixation arrière au-dessus de Z103 pendant la course et poches
d'écrous trop proches du bord. Le test final doit être relancé après toute
modification d'un conducteur, capot, câble ou élément de visserie. Le
maximum de pack198×78×60mm reste un maximum d'étude sans tolérance publiée.

La liberté de la fixation flottante TE sur toute sa plage, les coudes des
fils fournis avec le pack et les sorties non cotées du kitJETI doivent être
mesurés. Les lumières deP53/P41 sont implémentées, mais la rigidité,
vibration, dissipation des deux portées et retenue des longues boucles
restent **À valider**. Le splice34321 suppose le lotJETI8mm² confirmé ;
aucun kit6mm² n'est accepté par simple extrapolation. Les longueurs de
préparation et réservations de ports ne sont pas une instruction pour
usiner le module ni pour couper définitivement ses câbles.

**Essais physiques non exécutés**, pièces et drone montés indisponibles :
réception dimensionnelle du pack et connecteurs ; réglage de la butée au
stageprimaire avec engagement des contacts ; insertion lente sur toutecourse
sans pincement ni effort sur le softpack ; contrôle des deux stages, traction
et retenue dans toutesorientations ; essais gants/poussière/cycles ; inspection
du verrou contre ouverture accidentelle ; vibration et tenue des supports ;
pesée, centrage et vol progressif. Aucun statut **Qualifié** n'est attribué.

Le protocole électrique de banc doit commencer hors hélices : continuité,
polarité39/40 et isolationavant alimentation ; vérification que tous les
retours sont en aval du négatifJETI ; commandeOFF avant ouverture du loquet
et essai explicite de la mémoireON ; mesure du courant d'appel avec la
capacité réelle de distribution ; courant gradué, chutes de tension,
températures XT90/JETI/TE/barres/cosses et stabilité. Les valeurs100/125A
annoncées pour deux composants ne qualifient pas la chaîne complète.
Les charges mécaniques, durée/courant et critères thermiques d'acceptation
restent à établir selon le profil réel ; aucun seuil de réussite physique
n'est inventé à partir de cette vérification géométrique.

### 12.1.4 Configuration et faisceau système candidats, 3 octobre 2026

Périmètre : cartographe X650 6S 20 Ah, variante de revue inactive
`Drone_Cartographe_Systeme_Candidat.FCStd`, sous Windows amd64 avec le
Python de FreeCAD 1.1.3. Le matériel n'est pas assemblé par cette campagne.
L'[inventaire initial](../hardware/mecanique/cartographe/verification/inventaire_systeme_20261003.json)
compte 566 occurrences feuilles sur 151 fichiers CAO et aucun objet `Invalid`.
La [BOM cible](../hardware/mecanique/cartographe/configuration_cible_20261003.json)
recense 60 postes ; une masse ou quantité inconnue reste `null`.

| Besoin | Composant / contrôle | Résultat et preuve | Conclusion |
|---|---|---|---|
| `MEC-ARC-001`, `MEC-AVI-001` | `T-CARTO-SYS-NATIF` : construction puis réouverture/recalcul indépendant, empreintes des sources et des natifs | 42 nouveaux fichiers, 45 liens externes décrits par leurs matrices ; 35 balayages valides ; 154 sources CAO existantes préservées ; [construction](../hardware/mecanique/cartographe/verification/construction_systeme_faisceau_20261003.json) et [contrôle](../hardware/mecanique/cartographe/verification/controle_systeme_faisceau_20261003.json) | cohérence numérique **Implémenté** ; montage **À valider** |
| `CAB-CARTO-001`, `ELEC-PWR-002` | `T-CARTO-SYS-CAB` : chaque Wxx active appartient exactement à un groupe physique, interne, réservé ou sans fil | 33 liaisons, 28 groupes ; aucune liaison omise ou comptée deux fois ; [registre physique](../hardware/electronique/cartographe/faisceau_systeme_cible_20261003.json) | registre **Implémenté** ; fabrication **À valider** |
| `MEC-ARC-001`, `CAB-CARTO-001` | `T-CARTO-SYS-GEOM` : intersections BRep statiques des nouveaux équipements et des cordons avec les équipements représentés ; rayon obtenu comparé à la réservation | nouvelles poses PM08/PDB après collision dans l'itération initiale ; zéro intersection des nouveaux équipements ; 23 chemins sous le rayon réservé ; 32 cordons avec intersections brutes, sans exclusion automatique des interfaces | passages **À valider** ; conception ouverte |
| `MEC-MAS-001` | `T-CARTO-SYS-MAS` : complément cuivre des quatre conducteurs ajoutés au dock, sans addition des cordons OEM déjà inclus | 83,35 g de cuivre nominal ; budget historique partiel augmenté à 6,195–6,809 kg ; [bilan](../hardware/mecanique/cartographe/verification/bilan_masse_systeme_candidat_20261003.json) | **préliminaire** ; masse totale cible inconnue |

Les critères de cohérence sont : sources inchangées, liens résolus,
recalcul sans objet `Invalid`, chaque nouveau balayage valide à un solide,
couverture Wxx exacte. Une exécution sans erreur finalise sa preuve ; elle
ne démontre pas le respect des passages. Les rayons réservés sont des
hypothèses de routage, pas des minima fabricant qualifiés. Les intersections
de fin de cordon et les collisions véritables doivent encore être distinguées
sur des connecteurs accouplés et des sorties OEM cotés.

La revue indépendante, le manifeste et l'aperçu sont conservés dans
[la revue](../hardware/mecanique/cartographe/verification/revue_systeme_faisceau_20261003.json),
[le contrôle du manifeste](../hardware/mecanique/cartographe/verification/controle_manifest_systeme_candidat_20261003.json)
et [le rendu](../hardware/mecanique/cartographe/verification/rendu_systeme_faisceau_20261003.json).
L'itération initiale est conservée sous
`hardware/mecanique/cartographe/verification/archive_systeme_initial_20261003/`.
Les preuves actuelles portent les empreintes de la recette et des natifs.

Non exécutés : fabrication et montage des nouveaux supports/isolants,
accouplement/traction, mesures de rayons sur matériel, contrôle inter-cordons
et accès outils, débattement continu cassette avec le faisceau cible, repli
des bras, enveloppes hélices et mouvement réel du bloc capteurs,
continuité/isolement/précharge/thermique/CEM, pesée/centrage et vol.
Les interfaces du lot, les fournitures et les masses manquantes empêchent
de fermer ces validations. Refroidissement, accessoires de vol et LED OEM
n'ont pas de route native. Aucun montage fixé, faisceau complet ou marge
de masse démontrée n'est déclaré **Qualifié**.

### 12.1.5 Calcul conditionnel GNSS/radio sur plateaux, 4 octobre 2026

Chaîne `MEC-MAS-001` → bras OEM +Y et supports historiques P07–P09 →
`T-CARTO-GNSS-MAS-01` → [preuve de calcul](../hardware/mecanique/cartographe/verification/scenario_gnss_plateaux_20261004.json).
Sous Windows amd64, la [recette](../hardware/mecanique/cartographe/verification/calcul_scenario_gnss_plateaux_20261004.py)
réutilise les volumes de l'inventaire et du bilan mécanique, vérifie les
empreintes OEM/P07/P08/P09 et relit le JSON finalisé. Les matériaux restent
hypothétiques : bras 41,1 g avec ferrures aluminium ou 28,8 g avec ferrures
polymères ; anciens supports 39,7 g. Retrait historique maximal considéré
80,8 g sous la première hypothèse, avant additions. Les deux scénarios
de matériaux ne constituent pas des bornes physiques garanties.

Résultat arithmétique **Implémenté**, implantation **Planifié / À valider**.
Aucun fichier CAO, occurrence du manifeste, BOM active ou route de faisceau
n'est modifié. P07–P09 étant déjà absents de la maquette Helical candidate,
leur retrait ne lui apporte aucun second crédit. Le gain net et la masse
totale cible restent inconnus. Non exécutés : nouveaux placements BRep,
conception/pesée des supports et coaxiaux, contrôle d'accès/passages,
masques et essais RF, perturbations du compas sous charge, centrage et vol.
Ces validations demandent des fournitures et une implantation définies.

### 12.1.6 Tri des sous-assemblages FreeCAD, 4 octobre 2026

Chaîne `MEC-ARC-001` → catalogue courant/archives autonomes →
`T-CARTO-TRI-NATIF-01` → [plan et empreintes](../hardware/mecanique/cartographe/verification/plan_tri_sous_assemblages_20261004.json),
[courant](../hardware/mecanique/cartographe/verification/controle_tri_courant_20261004.json),
[archive](../hardware/mecanique/cartographe/verification/controle_tri_archive_20261004.json),
[reprise de source](../hardware/mecanique/cartographe/verification/controle_tri_source_stack_20261004.json)
et [catalogue](../hardware/mecanique/cartographe/verification/controle_catalogue_tri_20261004.json).
La [revue indépendante](../hardware/mecanique/cartographe/verification/revue_independante_tri_20261004.json)
confirme la cohérence du catalogue, les empreintes et l'idempotence de sa mise à jour.

Sous Windows amd64, FreeCAD1.1.3 réouvre les 12 sous-assemblages conservés
et l'intégration locale dans un processus neuf : 178 documents chargés,
aucun objet `Invalid`, aucun lien non résolu, aucune dépendance du courant
vers l'archive. Un autre processus réouvre le candidat complet archivé :
155 documents, aucun objet `Invalid` ni lien non résolu, toutes ses
dépendances natives dans l'archive. Les 290 natifs de l'instantané et
31 sauvegardes gardent leurs empreintes ; 18 natifs dépassés sont déplacés.

La reprise du châssis de base archivé, utilisée par la recette de stack,
est testée séparément : sept documents ouverts, liens du châssis rétablis
vers les pièces courantes, aucune sauvegarde de source. L'adaptation du
builder est tracée par son empreinte dans le contrôle du catalogue ; les
preuves de génération du 3 octobre ne sont pas réécrites ni interprétées
comme une régénération exécutée après le tri.

Le rangement et ses contrôles sont **Implémenté** ; les limites physiques
restent **À valider**. Non exécutés : régénération de la stack, nouvelle
campagne d'interférences et essais mécaniques/électriques/RF/vol, car aucun
placement, solide ou interface matérielle n'est modifié. Les preuves
antérieures et leurs réserves continuent de s'appliquer.

### 12.1.7 Couleurs et compacité du dock — 4 octobre 2026

Résultat historique de la première étape de compactage ; la définition
courante et son contrôle sont décrits au §12.1.8. Les réserves ci-dessous
décrivent l'état contrôlé à cette étape, sans certifier les fichiers évolués.

Chaîne `MEC-ARC-001`, `MEC-BAT-001` → dock et deux cordons fixes TE/JETI →
`T-CARTO-DOCK-COULEURS-01`, `T-CARTO-DOCK-COMPACT-01` →
[couleurs](../hardware/mecanique/cartographe/verification/couleurs_dock20Ah.json),
[implantation](../hardware/mecanique/cartographe/verification/compacite_dock20Ah.json),
[contrôle indépendant en processus neuf](../hardware/mecanique/cartographe/verification/controle_compacite_dock20Ah.json)
et [rendu natif](../hardware/mecanique/cartographe/verification/rendu_dock20Ah_courant.json).
La [revue indépendante](../hardware/mecanique/cartographe/verification/revue_compacite_dock20Ah.json)
contrôle les tangences natives, les BRep préservés et les tables d'apparence.
Recettes `update_compacite_dock20Ah.py`, `finalize_couleurs_dock20Ah.py`,
`verify_compacite_dock20Ah.py` et `render_dock20Ah_courant.py` dans le même répertoire.

Protocole Windows amd64 / FreeCAD1.1.3 : conserver références/placements,
réouvrir et recalculer, vérifier liens et arbres Chemin/Section/Sweep,
solides valides, rayons circulaires50mm, longueurs dechemin relevées,
absence de nouvelle collision externe et séparation continue de la cassette
sur+X. Les couleurs doivent être relues depuis les fichiers et contrôlées
sur une capture native ; une couleur en mémoire n'est pas un résultat finalisé.
Le PythonFreeCAD externe produisait des tables MaterialList v3 vides à la
sauvegarde : la finalisation restaure les tables GUI initiales depuis Git,
remplace seulement les apparences et vérifie ensuite leur réouverture.

Résultats :181 liens dock résolus, aucun objetInvalid, deux balayages natifs
valides,629 BRep exactement inchangés hors des deux cordons, aucune
intersection inter-cordons ni avec châssis/stack/capteurs/distribution.
La séparation conservatrice surX est17,17mm pour l'extraction continue+X.
L'enveloppe FreeCAD passe de548,64×135,84×212,89mm à543,84×135,84×150,57mm
(hauteur−29,3%, boîte−29,9%) ; conducteurs480,91/425,75mm libres.
Les couleurs sont persistantes sur89 références et les noms restent inchangés.

Conclusion **préliminaire**, CAO **Implémenté**, physique **À valider**.
L'intersection préexistante positif/P49 d'environ84,525mm³ est conservée,
signalée et doit être résolue avant fabrication. Les recouvrements avec
épissures/gaines sont consignés, sans conclure à l'absence globale d'interférence.
Non exécutés : mesure des ports/lot, liberté flottante, courbures réelles,
accessibilité et montage, vibration, thermique/isolement/courant, hélices et vol,
car les fournitures et le banc ne sont pas disponibles dans cette validation CAO.

L'état initial de91 petits natifs est conservé dans Git sur
`codex/batterie-avant-evolution-20261004` ;
[preuve de suivi](../hardware/mecanique/cartographe/verification/suivi_git_dock20Ah.json).
Les preuves du2–3octobre et du tri§12.1.6 restent historiques : leurs
empreintes antérieures ne certifient pas les fichiers évolués. Les nouvelles
empreintes sont celles du contrôle ci-dessus ; les exports STEP des deux
cordons sont régénérés. Aucune nouvelle qualification du drone complet.

### 12.1.8 Étage énergie et raccordement direct du pack — 4 octobre 2026

Chaîne `MEC-ARC-001`/`MEC-BAT-001` → SA02A, SA07 et P31/P39/P40/P43/P44/P51/P57 →
`T-CARTO-ETAGE-DIRECT-01` → [contrôle](../hardware/mecanique/cartographe/verification/controle_etage_batterie.json),
[distribution](../hardware/mecanique/cartographe/verification/distribution_etage_batterie.json),
[revue indépendante](../hardware/mecanique/cartographe/verification/revue_etage_batterie.json),
[cohérence des registres et des couleurs](../hardware/mecanique/cartographe/verification/controle_registres_etage_batterie.json),
[rendu natif](../hardware/mecanique/cartographe/verification/rendu_etage_batterie.json).
Windows amd64, FreeCAD 1.1.3 ; aucune qualification matérielle.

Périmètre courant : liaison directe candidate AWG8/742F5 M5, XT90-S,
adaptateurs AWG10 et barres P42 retirés ; JETI, commande magnétique,
PM08-CAN et PDB dans SA07 sur P57 candidat. PM08-CAN reste la sélection
courante ; PM08D est un module distinct, sans substitution. Le modèle de
cosse 742F5, notamment sa forme de coude, est une représentation d'étude **À valider**,
sans qualification de sa compatibilité AWG8 ni du sertissage.

Protocole : réouvrir/recalculer dans un processus neuf ; contrôler les liens,
l'unicité de JETI/PM08-CAN/PDB, les corps sous la batterie et les géométries
finales ; mesurer quatre balayages natifs, les rayons de 50 mm et les
intersections, puis l'extraction échantillonnée contre le châssis et les
pièces fixes. Les formes de construction cachées ne doivent pas gonfler
`App::Part.Shape` : les visibilités App et GUI sont synchronisées, les BRep
courants conservés et les matériaux natifs relus après sauvegarde.
Le contrôle porte uniquement sur le pack nominal de 193 × 76 × 58 mm.
L'enveloppe d'étude de 198 × 78 × 60 mm, sans tolérance fabricant publiée,
et le lot réel restent **À valider**.

Résultats courants : 130 occurrences du dock ; aucun objet `Invalid` ni
lien non résolu dans le contrôle. Fils mobiles de 89,70/90,56 mm ; fixes
de 354,42/354,07 mm, arcs de rayon 50 mm. Enveloppe batterie et énergie :
429,00 × 208,50 × 177,00 mm. Cette boîte inclut le déport latéral de SA07 ;
ne pas comparer son volume à l'ancien dock seul ni déduire un gain de
masse. Les détails des intersections et des poses d'extraction figurent
dans la preuve et la revue, sans assertion globale de conformité physique.
La réserve PDB de 22 mm est sans collision avec le châssis.

La revue indépendante vérifie 13 occurrences nouvelles et l'extraction de
9 occurrences mobiles aux courses 0, 10, 25, 50, 100, 200, 350 et 500 mm,
sans intersection détectée sur ce périmètre. Les quatre paires finales
cosse/vis/rondelle ont un volume commun nul après correction de leur pose
et de l'enveloppe d'étude du coude. Le contrôle des registres confirme
135 occurrences SA02A/SA07, les quantités et empreintes concordantes,
ainsi que les matériaux relus dans 91 sources natives.

Les collisions détectées avec logement TE/capture/cosse, un tube du châssis
et le plateau pendant l'extraction ont motivé des recoupes des coffrets,
un routage fixe plus précoce, des passages dans P31 et le rangement de
l'équilibrage dans le corridor intérieur. Le nouveau trajet traite aussi
l'intersection historique positif/P49 du §12.1.7. Le jeu nominal P44/plateau
est de 0,5 mm ; les tolérances restent **À valider**. La comparaison
échantillonnée n'est pas une preuve continue générale ; les guides STEP TE
gardent leurs limites historiques : ni accouplement ni flottement qualifiés.

Conclusion **préliminaire**, CAO **Implémenté**, matériel **À valider**.
Non exécutés : réception des lots pack/cosses/kit, compatibilité AWG8 et
sertissage, essai de l'adaptateur de charge TE, dressage et liberté TE,
finalisation des vis/sangles/coffrets, résistance des bras en porte-à-faux
de 82 mm, traction, vibration, isolement/courant/thermique, hélices et vol ;
les fournitures et le banc ne sont pas disponibles. Les faisceaux aval
JETI → PM08-CAN → PDB restent à recoter. L'adaptateur de puissance TE
protégé pour la charge hors drone est **Planifié** ; la prise JST
d'équilibrage seule ne remplace pas la liaison de puissance de charge,
et la charge ne passe pas par JETI OUT.

Les anciennes préparations de 150/600/520 mm et les tableaux de sept
colliers sont historiques et ne définissent pas les coupes ou quantités
actuelles ; BOM et faisceau sont mis à jour. La distance TE de 152,4 mm
est spatiale et concerne le collier éventuel ; un rayon nominal de 50 mm
et une longueur totale suffisante ne démontrent pas une conformité globale
au dressage perpendiculaire ni au flottement.

Point Git avant migration : `codex/batterie-avant-etage-inferieur` ; noms
des assemblages conservés. Les preuves §12.1.3/12.1.6/12.1.7 sont historiques
et leurs empreintes ne certifient pas les fichiers courants. Le contrôle
courant porte les nouvelles empreintes ; aucune qualification du drone
complet n'est ajoutée.

### 12.1.9 BMS de cassette et raccordement TE compact — 5 octobre 2026

`SAFE-REQ-011` / `ELEC-BMS-001` → JBD-SP22S003 A01, TE5signaux,
isolationUART et SA08 → contrôles natifs et schéma courants. CAO et schéma
**Implémentés**, qualification matérielle **À valider**. BMS au-dessus du
pack, P37 de95 mm et plateau/fixations rehaussés de25 mm conservés.

Le dernier compactage avance le TE encore40 mm sur X, avec décalage
Y−6,1535/Z+12,255 mm, réoriente la cosse négative de−90° autour de X et
supprime la chambre78×46×42 au profit de protections locales des cosses.
Les axes des douilles/contacts et vis sont cohérents après réouverture.
Le [comparatif courant](../hardware/mecanique/cartographe/verification/compactage_raccord_bms_te.json)
se réfère à Git `1ccbad81` :143 sources natives identiques aux fichiers Git
et quatre sources OEM lourdes figées localement par SHA. Utiliser les bornes
`bbox_apres_verification_mm`, recalculées en processus neuf :

| Périmètre identique avant/après | Avant L×l×H (mm) | Courant (mm) | Volume englobant |
|---|---|---|---|
| Batterie et énergie | 399×210,5×181 | 388×210,5×181 | −2,757 % |
| Cassette mobile | 346,337×108,5×91 | 295,900×113,6535×91 | −10,505 % |
| Intégration locale | 538,596×511,015×501,529 | 538,596×511,015×501,529 | 0 % |

La cassette gagne50,4369 mm sur X et s’élargit de5,1535 mm sur Y ;
l’ensemble énergie gagne11 mm sur X. Le gain de cassette inclut aussi la
correction d’orientation des douilles. L’isolateur fixe et les bras limitent
respectivement ces deux enveloppes. Avancer le TE de40 mm ne démontre pas
40 mm de gain global, de réduction de matière ou de masse. Le cache auteur
immédiatement enregistré donnaitXmin−167,796 ; le recalcul frais donne
**−167,900059 mm**, seule valeur retenue. Aucune qualification physique
ni enveloppe de drone de mission complet n’en est déduite.

Les contrôles de l’étape arrière Git `94d04d0`, de son comparatif145 sources
exactes/deux reconstructions P37=70/rehausse=20, puis de la première
implantation supérieure Git `1ccbad81` sont historiques. Leurs réussites
ne certifient pas le dernier déplacement. Les fichiers et noms restent
stables ; retours arrière par Git.

Les résultats suivants portent sur le compactage avant séparation des parents
CAO ; la migration est contrôlée séparément au §12.1.10. Le [contrôle BMS du compactage](../hardware/mecanique/cartographe/verification/controle_bms_cassette.json)
réouvre/recalcule les natifs en processus FreeCAD neuf :147 sources,
aucune erreur de recalcul ni lien rompu, cinq routes valides avec contrôle
BOP, axes et entrées des cosses cohérents, aucune collision non classée.
Les parcours mobiles mesurent17,2548 mm B+ axial,77,6861 mm B− brut,
49,3353 mm C− protégé,52,9941 mm équilibrage et83,6733 mm UART.
Les huit poses d’extraction0/10/25/50/100/200/350/500 mm sont libres.
Seul le recouvrement86,5901 mm³ câble d’équilibrage/réservation JST est
intentionnel ; accouplement physique **À valider**. Ce test reste limité au
pack nominal193×76×58 mm ; enveloppe d’étude198×78×60 et lot réel non acceptés.

Le départ fixe des cinq signaux TE de SA08 est recalé vers
(−195, −26,1535, 90,255) mm. Le
[contrôle complet des37 routes](../hardware/mecanique/cartographe/verification/controle_routes_systeme_courant.json)
est réussi en mode «natifs enregistrés», sans collision et avec sources
externes stables. PM_OUT_PDB conserve son départ puis descend de4 mm pour
éviter le dock ; cette correction est incluse dans le contrôle complet.
La [relecture finale après sauvegarde](../hardware/mecanique/cartographe/verification/controle_faisceau_natif_bms.json)
est réussie en processus neuf :109 empreintes de sources obstacles et38
fichiers de faisceau concordants,37 routes valides au contrôle BOP et
identité géométrique natif/candidat avec différence symétrique maximale
0 mm³ pour seuil1e−5 mm³. La preuve candidate et la recette de vérification
sont rattachées par chemin et SHA. Les booléens contre les obstacles ne sont
pas recalculés dans ce processus ; le résultat complet est réutilisé après
contrôle d’identité. La relecture indépendante P49 confirme un solide BOP sain,
24 interfaces sans collision et sommetZ121 conservé ; rigidité physique
**À valider**. Les cordons fixes mesurent305,7557/325,2341 mm avec troisR50
chacun et extrémités JETI cohérentes. Aucune collision non classée ou réserve
géométrique ne reste ouverte dans le périmètre nominal contrôlé.

Les registres de cette étape avant migration sont actualisés :182 occurrences,115 références et629 placements
dans le manifeste, avec TE à12 mm de recul sur X. Le
[rendu final](../hardware/mecanique/cartographe/verification/rendu_bms_cassette.json)
produit deux PNG relus, sans modification des147 sources : protections
locales et P49 monobloc visibles, grande chambre supprimée. La dernière
mise en concordance doit suivre le gel documentaire :
`verify_registres_bms.py`, puis contrôle électrique `verify_cablage.ps1`
rattachant notamment le chemin et le SHA de DOC-ELEC. Consulter les preuves
[des registres](../hardware/mecanique/cartographe/verification/controle_registres_bms.json)
et [du câblage](../hardware/electronique/cartographe/verification/cablage_global_bms.json)
pour les résultats et empreintes de cette dernière exécution. La [revue indépendante](../hardware/mecanique/cartographe/verification/revue_bms_cassette.json)
doit porter sur ces mêmes natifs et documents.

Un résultat «sans collision» ne valide pas les rayons : PM_OUT_PDB mesure
R50/R33/R28,9365 pour R50 souhaité ; TE5_SIGNAL_ISOLATEUR mesure185,6664 mm
avec R7,04/R8,2925/R9,24/R4,4 pour R23 souhaité. Ces écarts restent
explicitement **À valider**, sans réduction silencieuse des critères.

Le circuit reste27 modules et40 liaisons ; le vérificateur électrique
couvre aussi28 broches CA01 et trois requêtes JBD03/04/05 avec checksum.
Le diagramme Mermaid reste synchronisé avec DOC-ELEC. Aucun contrôle de
trame déclarative n’est un test de décodeur, de communication réelle ou de
courant. B+ continu→TE39, B− brut→BMS, C−/P− protégé→TE40 ; charge hors
drone par B+/P− protégé, jamais B− brut. L’UART brut ne rejoint l’avionique
qu’à travers l’isolateur fixe ; VDD JBD et5V TTL isolée restent NC.

| Essai | Critères restant à fermer | État |
|---|---|---|
| T-CARTO-BMS-01 réception/interface pack | lotA01, chimie6S, ordreB0…B6/JST, adaptation22S, fil ouvert, NTC, J2/J3, niveauTTL | Planifié, pas de matériel |
| T-CARTO-BMS-02 implantation/extraction | BMS supérieur, PCB tolérancé, P37/plateau/fixations, jeux3/4 mm, protections locales et continuité P49, cosses/câbles ; course continue, rigidité et masse | CAO **Implémentée**, contrôle BMS réussi ; contrôle complet et relecture native SA08 réussis, physique **À valider** |
| T-CARTO-BMS-03 puissance/charge/thermique | courant mission, pertes, pointes, charge protégée, précharge et températures selonOEM | Planifié ;100A système non qualifié |
| T-CARTO-BMS-04 coupures/communication | aucune voie B− brut vers avionique, isolationdata+DC/DC, VDD/5VNC, mappingTE/ports réels, parser/identité/fraîcheur | Topologie déclarative contrôlée ; banc et logiciel Planifiés |
| T-CARTO-BMS-05 alerte/protection coordonnée | margesPX4 pour dérives progressives, défauts sévères immédiats, perte de mesure ; aucune inhibition des protections | Planifié, pas d’essai nouveau |
| T-CARTO-BMS-06 cycles/environnement | nombre échanges mission, retenue, guidage/flottement, protection au toucher, intrusion et vibration | Planifié, objectifs à fermer |

Rayons brutsR16,77/équilibrageR12,41/UARTR8, diamètre AWG8 réservé5 mm,
ports non cotés, cosse742F5 M5/10 mm² et positif axial très court restent
**À valider** sur lot. Les132,7452 mm de solde sur les150 mm usine ne sont
pas une longueur de coupe. Aucun test numérique ne qualifie sertissage,
tolérances, liberté flottante, reprise de traction ou dissipation100A.
Une coupure BMS supprime propulsion et les deux BEC du PM08 ; POWER1/2 ne
constituent pas un secours à cette cause commune. PM08 reste source PX4.
Non exécutés : réception, sertissage, isolation physique, thermique, charge,
vibration, cycles, matériel embarqué et vol, faute de lot/banc. Aucun
résultat **Qualifié**.

### 12.1.10 Découpage batterie/récepteur et énergie directe — 5 octobre 2026

**Portée historique :** les résultats ci-dessous concernent les fichiers
empreintés dans la revue. Le contrôle du 7 octobre constate une empreinte
différente pour l'assemblage d'intégration présent ; voir [AUD-007](#aud-007).
La portée de ce changement reste inconnue ; la revue historique ne certifie
pas à elle seule les octets courants.

`MEC-ARC-001` / `MEC-BAT-001` / `SAFE-REQ-011` → batterie mobile,
récepteur fixe et principal6+6 → `T-CARTO-HIER-BAT-01` →
`verification/decoupage_sous_assemblages_batterie.json`.
La migration CAO est **Implémentée** et le contrôle après sauvegarde est
réussi. Les preuves de migration et de contrôle frais sont finalisées. Le contrôle frais est
`verification/controle_hierarchie_batterie.json`, la concordance registres/BOM
`verification/hierarchie_batterie_recepteur.json`, et la vérification des vues
`verification/rendu_hierarchie_batterie.json`. Les anciennes preuves de
compactage restent gelées, avec leurs empreintes et leur parentage antérieur.

Cible :67 pièces mobiles dans `SA02_Cassette20Ah_Coulissante`,72 fixes dans
`SA02A_Dock20Ah`, six pièces d’énergie directement dans le principal et six
liens de sous-assemblages, soit12 liens directs. SA07 est conservé hors
configuration installée. Le protocole en processus FreeCAD neuf vérifie :

- parentage et unicité, absence du groupe SA07 installé, liens résolus et recalcul ;
- références et quantités identiques, matrices mondiales et orientations
  conservées, sources natives de pièces/faisceau inchangées et couleurs avant/après ;
- extraction appliquée une seule fois à l’ensemble mobile67 pièces,
  récepteur et six équipements fixes immobiles, aux trois translations0/50/500 mm ;
- empreintes des sources et des preuves du compactage permettant le transfert
  de leurs résultats ; les sources de pièces et faisceau ne doivent pas changer.
  Les huit poses et booléens de collision antérieurs sont réutilisés par cette
  identité, sans les présenter comme de nouveaux calculs de collision ;
- registres installés sans double comptage des montages historiques.

Résultats : aucun objet Invalid ni lien non résolu,149 éléments affectés
conservés comme multiensemble de références et matrices mondiales, apparences
complètes identiques. Ces149 éléments sont139 anciens éléments du dock,
six équipements et quatre liens principaux traités comme blocs ; ils ne
constituent pas un inventaire détaillé de tous les objets internes du drone.
Aux translations0/50/500 mm, seuls les67 mobiles bougent une fois ;72
éléments du récepteur, six pièces directes et37 routes restent fixes.
Le contrôle ne modifie aucun natif ; sources de pièces/faisceau, anciennes
preuves et enveloppe du principal conservées. Les registres publiés
confirment182 occurrences/115 références sur le périmètre batterie,
récepteur, énergie directe et SA08, ainsi que12 liens directs dans le principal.

Les gardes des anciennes recettes monolithiques doivent refuser cette
hiérarchie avant mutation. Les preuves citées ici ne constituent pas
un rejeu de toutes les recettes historiques. Les vues et leur contrôle
sont rattachés à `verification/rendu_hierarchie_batterie.json` ; vérifier
sa finalisation et ses empreintes avant de réutiliser une vue.

Les mesures388×210,5×181 mm énergie,295,900×113,6535×91 mm cassette et
538,596×511,015×501,529 mm intégration sont les références géométriques du
compactage précédent. Leurs sources et poses sont conservées ; aucun nouveau gain
n’est attribué au seul changement de hiérarchie. Circuit27 modules/40 liaisons
et frontières BMS/JETI/isolation inchangés. Aucune qualification matérielle,
course continue, tenue des fixations, thermique ou vol n’est ajoutée.

<a id="validation-skill-electromecanique"></a>
### 12.1.11 Skill d'intégration électromécanique — 27–28 octobre 2026

`T-SKILL-EMI-01` vérifie les ressources réutilisables de la
[skill](../.agents/skills/electromechanical-integration/SKILL.md), en soutien
des exigences `CAB-CARTO-001` et `MEC-INT-001`. La
[preuve structurée](verification/electromechanical_integration.json) conserve
les commandes, codes de retour, empreintes, mesures synthétiques, cas couverts
et conclusion de revue. Aucun natif du drone ni constructeur existant modifié.

Environnement : Windows amd64, C++17 GCC 16.2.0/Qt6Core 6.11.2, FreeCAD 1.1.3,
Cables 0.3.7. Le MCP freecad-mcp 0.1.22 installé est indisponible (connexion
RPC refusée) ; le Python embarqué réalise les contrôles Part et les créations
natives dans un processus indépendant offscreen. Aucun contrôle interactif.

Critères : conservation exacte des liaisons et extrémités, absence de partage
non autorisé, refus des incohérences/débordements, absence de faux succès sur
mesure inconnue ou solide périmé, isolation des sources et résultats finalisés.
Les valeurs des fixtures sont synthétiques ; elles ne deviennent pas des
spécifications fournisseur.

| Cas demandé | Contrôle exécuté et résultat |
|---|---|
| Deux câbles compatibles, corridor commun | partage de 100 mm détecté ; longueur cumulée de 240 mm et deux liaisons conservées |
| Trois câbles et dérivations | tronc partagé, destinations distinctes, branches et trois liaisons conservées ; forward-test indépendant |
| Câbles incompatibles | aucune gaine commune ; séparation géométrique dans un corridor commun encore explicitement à démontrer |
| Rayon non conforme | arc BRep de 10 mm rejeté face au seuil synthétique de 22 mm |
| Collision réelle | intersection BRep positive câble/obstacle détectée et rejetée |
| Inclusion/contact autorisé | inclusion justifiée dans une enveloppe de gaine acceptée ; pénétration de matière rejetée |
| Échec de génération | forme nulle et retour natif injecté sans nouvelle forme rejetés ; ancien solide effacé avant recalcul |
| Propriété fournisseur absente | `null` conservé, candidat `unresolved` ; aucune conformité fournisseur déduite |
| MCP indisponible | branche de repli testée ; probe Part et génération Cables réellement exécutés séparément, sans faux état d'exécution |
| Connexion perdue | omission identifiée `missing_link`, candidat rejeté |

Résultats : compilation et CTest réussis, **41 assertions C++**, **19 tests
FreeCAD dont 4 natifs**, **6 tests d'infrastructure**, validateur officiel
`quick_validate.py` réussi. La revue indépendante a identifié puis vérifié
la correction d'un faux succès sur coordonnées/axes NaN ; 15 contre-exemples
NaN/±inf sont rejetés. La correction du prédimensionnement des câbles isolés
est aussi vérifiée : Ø3 mm dans 4 mm accepté, dans 2 mm rejeté, sans gaine
ajoutée implicitement. La preuve porte les sorties et empreintes exactes.

La méthode et ses utilitaires sont **Implémenté**. Ces résultats sont limités
aux contrats et géométries synthétiques, pas à un assemblage réel. Splines sans
borne globale, découverte de corridors, routage complet, packing, CEM,
thermique, vibrations, montage et maintenance réels restent **À valider**.
Sauvegarde/réouverture d'un assemblage reconstruit, contrôle interactif et
validation physique non exécutés : hors périmètre de cette mission de skill.
La définition et qualification du faisceau drone ne changent pas.

**Évolution d'autonomie — `T-SKILL-EMI-02`, 28 octobre 2026.** La
[décision de conception](architecture/ARCHITECTURE_MECANIQUE.md#integration-electromecanique)
enrichit la skill existante ; les scripts métier, d'isolation et FreeCAD
restent identiques. La
[preuve d'évaluation](verification/electromechanical_autonomy.json)
porte les entrées/empreintes, commandes, résultats bruts et leur appréciation.
Les huit [cas synthétiques](../.agents/skills/electromechanical-integration/references/evaluation.md)
testent les actions observées, distinctement des régressions exécutables.
Deux agents indépendants reçoivent les consignes et données sans barème ; une
revue séparée compare les instructions et contrats à la baseline préservée.

Rejeu Windows amd64 : nouvelle compilation depuis les sources actives,
CTest **1/1**, **41 assertions C++**, **6 tests d'isolation**, **19 tests
FreeCAD dont 4 natifs**, tous réussis sans exclusion. Rapport FreeCAD finalisé
et relu ; empreintes des scripts et du constructeur inchangées. Validation
officielle de la skill et liens internes contrôlés. La revue indépendante
ne relève pas de contradiction bloquante avec les mécanismes antérieurs.

Les **8/8 cas comportementaux réussissent** au barème observé :

| Cas | Résultat observé et limite |
|---|---|
| D1 — documentation | notice fictive B retrouvée, A écartée ; rayons 12/40 mm avec conditions, sans question préalable |
| K1 — cinématique | pivot calculé : déplacement nominal–butée 26,105 mm et corde entre butées 51,764 mm ; pas une longueur de cordon |
| P1 — amplitude inconnue | bornes issues des butées, distance des ports 97–103,310 mm ; scénarios de longueur et contrôle paramétrique, vibration/fatigue inconnues conservées |
| L1 — longueur héritée | minimum 282 mm ; 200/250 rejetés, 300 retenu conditionnellement face à 350 ; masse 9 g, chute 0,060 V et pertes 0,30 W |
| G1 — guide modifiable | baseline en collision, guides y20/y35 comparés par trajets analytiques R10 ; y20 retenu conditionnellement, port/guide fonctionnels conservés ; natif et tolérances non vérifiés |
| R1 — regroupement | gaine Øint 5 rejetée pour deux Ø4 et séparation imposée ; architecture séparée candidate, CEM/thermique ouvertes |
| B1 — blocage local | liaison mobile non vérifiée ; liaison fixe calculée jusqu'au résultat : chute 0,4 V sous seuil 0,5 V, pertes 2 W, température inconnue |
| H1 — hypothèse | `pass` numérique rapporté conservé, seuil 22 mm hypothétique ; candidat conditionnel et validation physique requise, aucune promotion globale |

Les évaluations documentaires utilisent des notices fictives locales ; elles
ne démontrent pas une recherche web fabricant réelle. Les cas cinématiques et
électriques sont calculés en C++17 ; leurs résultats ne qualifient ni montage,
ni CEM, ni thermique, ni fatigue. Aucun modèle du drone ouvert ou modifié,
aucune publication de variante ni essai matériel. La validation interactive
et physique n'est pas exécutée, hors périmètre de cette évolution de skill.
Méthode **Implémenté**, autonomie générale et intégration réelle **À valider**.

<a id="validation-reconstruction-faisceaux"></a>
### 12.1.12 Reconstruction des faisceaux sur copie

<a id="validation-refonte-faisceaux"></a>
**Refonte du 9 novembre 2026 — candidat sur copie, À valider.**
Le [reçu d'installation](../hardware/mecanique/cartographe/verification/refonte_faisceaux/installation.json)
identifie les fichiers natifs, les sources et les paramètres. La recette
utilise FreeCAD 1.1.3 avec Cables 0.3.7 sous Windows. Le RPC a refusé la
connexion au démarrage. Le Python embarqué a exécuté les opérations natives
et les 19 tests du banc synthétique. Les propriétés du planificateur C++17
ont également été testées. Les résultats synthétiques et ceux du drone sont
interprétés séparément.

| Porte et exigence | Contrôle et portée |
|---|---|
| A / EM-INT-01 et EM-INT-02 | Réconciliation de 43 lignes BOM, des 40 identifiants du registre électrique global et de 53 parcours natifs. Le registre compte 71 lignes et couvre les liaisons embarquées, les interfaces directes, les liaisons internes, le sol et les retraits. Un export KiCad neuf retrouve les 43 broches vérifiées sur 15 références. |
| B / EM-GEO-01 et EM-GEO-02 | Réouverture de 141 natifs. 53 câbles, 4 gaines et 2 guides recalculés avec leur cache vidé. Équivalence volumique aux tolérances du contrôle. La revue des 21 groupes confirme les 53 identifiants et leurs extrémités. |
| C / EM-GRP-01 | Quatre protections communes distinctes du cordon Airy. Dix inclusions locales passent, avec zéro volume en paroi. Tronçons de 105, 30, 9 et 8 mm. Quatre stations de retenue du corridor nord restent à redéfinir autour de la gaine. |
| C / EM-COL-01 et EM-COL-02 | 19 765 paires au nominal, dont 2 527 touchées par la refonte. Aucun nouveau recouvrement détecté au seuil de 0,0001 mm³. Six recouvrements d'enveloppes Airy restent circonscrits à l'éclatement. Neuf distances exactes restent indéterminées. |
| D / EM-INT-02 et EM-GRP-01 | 53 axes avant/après. Les protections communes passent de 80 à 152 mm, hors tronc Airy déjà présent. Les axes cumulés passent d'environ 12 195 à 12 207 mm. Masse complète inconnue des deux côtés. Les douze selles des bras sont conservées. |

Le [rapport géométrique](../hardware/mecanique/cartographe/verification/refonte_faisceaux/validation_geometrique.json)
rattache la réouverture, les comparaisons volumiques et les preuves
indépendantes aux mêmes natifs sauvegardés. Deux paires entre P75 et les
équipements avioniques ont dépassé le délai du calcul direct. Leur
recouvrement est borné par les contrôles du guide de référence et par la
borne sur la matière ajoutée après les soustractions. Ce raisonnement ne
donne pas leur dégagement exact. La
[comparaison des variantes](../hardware/mecanique/cartographe/verification/refonte_faisceaux/validation_variantes.json)
reporte les rejets et le dimensionnement des sections. Le classement porte
sur les variantes testées et les critères géométriques évalués.

Le contrôle différentiel de F16 compte 4 455 paires sur 27 poses sans
nouveau recouvrement ou calcul indéterminé. Les intersections rigides de
référence aux poses caméra et la course réelle restent ouvertes. Pour M8,
sept poses sur seize échouent à raccorder le départ hérité à R52. Sur 36
variations du départ, trois des quatre variantes contrôlées passent au
nominal. Les trois rencontrent la semelle ou la rondelle du BMS dans au
moins deux poses. La copie conserve donc la route nominale M8. Les essais
exploratoires autorisaient la variation de longueur entre poses et ne
démontrent aucune tenue en traction, torsion ou fatigue.
[Contrôle des poses](../hardware/mecanique/cartographe/verification/refonte_faisceaux/mobilite.json),
[variantes M8](../hardware/mecanique/cartographe/verification/refonte_faisceaux/mobilite_variantes_m8.json).

La course et la fatigue F16/M8, la tenue des retenues, les efforts et jeux
au montage, les températures, la CEM et les longueurs de commande restent
**À valider**. Le registre conserve les neuf définitions embarquées non
résolues. Aucun essai physique ni validation interactive du montage n'a été
exécuté.

<a id="validation-faisceaux-modulaires"></a>
**Copie modulaire du 9 novembre 2026 — Implémenté en CAO, À valider pour le montage.**
La [preuve consolidée](../hardware/mecanique/cartographe_faisceaux_modulaires/verification/validation.json)
relie les critères `CAB-CARTO-001`, `MEC-INT-001` et `EM-INT/GEO/COL/GRP`
au modèle et à ses fichiers finaux. La
[revue indépendante initiale](../hardware/mecanique/cartographe_faisceaux_modulaires/verification/revue_modulaire.json)
recoupe les axes, les interfaces électriques et les intersections des premiers
trajets reconstruits. La
[contrelecture de la reprise](../hardware/mecanique/cartographe_faisceaux_modulaires/verification/revue_reprise_modulaire.json)
vérifie les natifs P70, la retenue F41 et le trajet F06.

| Porte | Résultat et périmètre |
|---|---|
| A — Intégrité | 147 fichiers de la source de copie vérifiés par empreinte. Onze modules, 53 axes et 71 identités électriques rapprochées. Équipements, placements et terminaisons électriques conservés. |
| B — Recalcul et réouverture | FreeCAD 1.1.3 et Cables 0.3.7 sous Windows AMD64. Les 53 câbles sont reconstruits en mémoire à partir des natifs sauvegardés. Les 141 documents de la fermeture native sont rouverts dans la copie. Les rayons et axes de définition sont contrôlés séparément des données fournisseur. |
| C — Retenues et protections | 172 paires à proximité des occurrences ajoutées ou reprises. Aucun recouvrement volumique ou résultat indéterminé dans ce sous-contrôle. Les cinq interférences de la première passe ont été reprises. Les deux gaines F38 contiennent chacune leur câble sur 105 mm, avec 0,75 mm de garde radiale nominale et 66 % de section occupée. |
| C — Assemblage nominal | 33 120 paires impliquant un câble, une gaine ou une retenue. Après reprise des quatre calculs interrompus, aucune intersection interdite détectée au seuil de 0,0001 mm³. Six recouvrements d'enveloppe sont circonscrits à l'éclatement Airy. Les distances exactes de quatre paires autour de CA01 et de la porteuse restent indéterminées. |
| D — Comparaison | Trois cadres et deux grandes retenues retirés. Les occurrences de supports de faisceau, quincaillerie et boucles dans la CAO passent de 75 à 58. Les longueurs d'axe diminuent de 1 082,7 mm. Le retrait invalide 263 affectations historiques de station. Le bilan de masse reste incomplet. |

Le retrait de P75 a d'abord laissé les supports radio P70 sans ancrage.
La reprise utilise les colonnes P68. Le
[contrôle sur les natifs](../hardware/mecanique/cartographe_faisceaux_modulaires/verification/validation_radio.json)
mesure le jeu radial nominal de 0,10 mm et identifie les faces de butée
axiale. Les forces d'encliquetage et de retenue, les tolérances et le
comportement vibratoire demeurent **À valider**.

Le contrôle géométrique porte sur la pose nominale. Les 48 axes conservés
comprennent des réservations dont les attaches ne sont plus définies. Les
couples et tolérances, le passage des connecteurs, la tenue vibratoire,
thermique et CEM, la course et la fatigue de la caméra restent à vérifier.
Les essais de montage physique et
l'inspection interactive d'accessibilité n'ont pas été exécutés.

**Reprise du 8 novembre 2026 — Implémentée sur copie, À valider.** Le
[bilan technique](../hardware/mecanique/cartographe/verification/reconstruction_faisceaux/bilan_autonomie.json)
relie les essais et leurs empreintes à l'assemblage final. La recette utilise
le Python embarqué de FreeCAD 1.1.3 avec Cables 0.3.7 et le solveur C++17.

| Porte et exigence | Contrôle et résultat |
|---|---|
| A / EM-INT-01 et 02 | 143 sources originales et 144 fichiers de la copie de référence vérifiés par SHA256. Fermeture finale de 138 natifs sous la copie. 53 parcours uniques, 52 autres parcours et leurs liens conservés, deux terminaisons de F16 conservées. |
| B / EM-GEO-01 et 02 | F16 complet `Cable002` sur `CompoundPath`, protection F38 paramétrique et guide P73 recalculés. Réouverture de l'assemblage en processus dédié avec chargement complet préalable des deux candidats à reconstruire. Différences volumiques nulles aux tolérances du contrôle. |
| C / EM-F16-01 | 24 géométries nominales explorées, 6 infaisables par manque de tangence et 3 avec intersection. Une géométrie favorable du lot exploratoire garde une trace d'exécution non figée. Cinq stations retenues à moins de 0,6 mm de l'axe. R50 mobile et R24 fixe vérifiés. |
| C / EM-COL-01 | 27 poses de F16, aucun recouvrement au-dessus de 0,0001 mm³ sur les obstacles modélisés. Longueur constante, écart numérique inférieur à 2 × 10⁻¹³ mm. Les nouveaux volumes P73/F38 sont disjoints des sections F16 et des 31 pièces mobiles aux 27 poses, soit 1 782 paires supplémentaires écartées par boîtes englobantes. |
| C / suspension | 16 poses sur 27 présentent une intersection rigide, dont 7 des 8 combinaisons à signes couplés de ±0,5 mm et ±0,5°. Les quatre bagues et quatre tampons déformables sont exclus de la simulation rigide. Aucun domaine de déplacement continu ni qualification vibratoire déduits. |
| C / EM-GRP-01 | Quatre longueurs de gaine ronde F38 interfèrent avec P73. La paroi ovale de 80 mm sur P73 adapté contient les deux tronçons sans pénétration de paroi. Les gaines NTC de 6 mm et GNSS de 5 mm, testées en CAO, ne sont pas retenues. |
| D / comparaison | F16 initial 425,174 mm et R22. Candidat 494,608 mm et rayons 50/24 mm, trois stations libérées, cinq conservées. Un tronçon de protection commun de 80 mm. Les mesures ne lèvent pas les inconnues de montage et de masse complète. |

La distance nominale de 0,105 mm au P75 est mesurée sur le tronçon fixe.
Un retour de distance nul près de la vis OEM079 contredit la séparation des
boîtes englobantes. La distance exacte de cette paire est donc indéterminée,
et l'intersection de cette paire est exclue par la borne géométrique. Le zéro
brut ne sert pas de dégagement. Les seuils de dégagement physiques restent ouverts.

La réouverture a d'abord échoué sur le document F16 partiellement chargé par
XLink. L'ouverture préalable des deux natifs candidats a permis de les
reconstruire et de vérifier les liens et empreintes du modèle final. Les
recettes de comparaison se limitent aux poses discrètes, au câble F16 et aux
nouveaux volumes rigides. Les autres câbles mobiles, le passage des outils et
des prises, la tenue des colliers et du guide, la torsion et la fatigue de
F16, le comportement USB3, la CEM et le thermique restent à valider. Aucun
essai physique, en vol ou validation interactive n'a été réalisé.

**Contrôle étendu aux 53 parcours.** Cinq lots ont reconstruit les 53 solides
à partir de leurs bases natives, cache de câble vidé et absence d'écart
volumétrique au seuil de 0,0001 mm³. Les extrémités coïncident avec les points
du registre. Les axes de prise et rayons d'acceptation indépendants ne sont
pas établis dans cette recette pour 52 parcours. Les mesures de courbure ne
qualifient donc pas ces liaisons. La distinction entre câble natif et groupe
`Ensemble` lié dans SA07 est vérifiée sur les 53 occurrences.

La mesure des 257 associations entre stations documentées et axes a conduit
à corriger sept stations de P73/P75. Le premier candidat P73 est écarté pour
trois intersections. Sur la paire de guides retenue, les seuls volumes ajoutés
ou leur borne conservatrice sont vérifiés contre les autres occurrences et
entre eux. Aucun nouveau recouvrement n'est détecté au nominal, ni dans le
complément de contrôle du bloc rigide et de F16 aux 27 poses déjà étudiées.
Le modèle complet et les deux guides ont été rouverts en processus neuf. Les
guides recalculés ont des volumes égaux aux volumes sauvegardés à la tolérance
du contrôle. Après transformation de huit points déclarés en repère local,
11 écarts dépassent 0,6 mm. Huit correspondent à des distances au point
commun du peigne MAIN, qui ne désigne pas les axes individuels. Les trois
sites individuels à reprendre sont F38_POS_RETOUR, F05_POS_T_20 et F37_NEG_V.
La tenue des colliers et les accès de montage restent ouverts.
[Résultats du contrôle étendu](../hardware/mecanique/cartographe/verification/reconstruction_faisceaux/bilan_faisceau_complet.json).

**Baseline du 28 octobre 2026.** Les résultats suivants concernent la copie
conservée et l'essai R23,5 séparé.

**Résultat partiel, À valider ; aucune reconstruction globale qualifiée.**
Protocole : skill `electromechanical-integration`, portes intégrité, géométrie
fraîche, intégration puis comparaison. Environnement Windows amd64, FreeCAD
1.1.3, Cables 0.3.7 et planificateur C++17/Qt6. Le RPC a refusé la connexion ;
les tentatives de démarrage n'ont pas établi de session MCP durable. Le repli
Python embarqué a réellement exécuté les mesures et objets natifs, avec GUI
dédiée hors écran. Les avertissements Qt/cache ne valent pas échec BRep ni
validation interactive. Les 19 tests synthétiques de la skill ont réussi.

Le [bilan consolidé](../hardware/mecanique/cartographe/verification/reconstruction_faisceaux/bilan.json)
relie fichiers, empreintes, phases, mesures et limites. La comparaison détaillée
et les vues sont dans [DOC-MEC §2.2.3](architecture/ARCHITECTURE_MECANIQUE.md#reconstruction-faisceaux).
La copie conserve l'assemblage initial ; l'essai F16 reste séparé.

| Exigence / risque | Contrôle exécuté | Résultat / preuve dans `verification/reconstruction_faisceaux/` |
|---|---|---|
| EM-INT-01 — préserver sources et dépendances | fermeture XLink, SHA256, résolution native | 143 fichiers préservés ; 137 documents uniquement sous la copie ; reçu `experiment.json` de la copie et `reouverture_assemblage.json` |
| EM-INT-02 — conserver les identités | projection des 53 routes et inventaire logique/BOM | aucune omission/duplication dans la projection ; trois candidats `unresolved` ; brochages physiques NON_VERIFIE ; `analyse_connectivite.json`, `resultat_planificateur.json` |
| EM-GEO-01 — supprimer le risque de solide périmé | cache Shape vidé avant recalcul | 53/53 câbles frais valides et essai F16 valide puis réouvert ; `recalcul_natif.json`, `prototype_f16_reouverture.json` |
| EM-GEO-02 — relier sauvegarde et recalcul | différences volumiques dans les deux sens | 54/54 différences ≤0,0001 mm³ ; 60 poses racine/câbles identité et conformes au registre ; `equivalence_solides.json` |
| EM-F16-01 — stations, rayon, tangence, longueur | huit stations à 0,6 mm ; continuité 0,00001 mm, tangence 0,1° ; courbes analytiques | statique favorable pour initial et R23,5 ; axes candidats, dynamique NON_VERIFIE ; `comparaison_f16.json` |
| EM-COL-01 — volumes F16 | BRep sur 360 autres occurrences, seuil 0,0001 mm³ | aucune intersection positive ou opération inconnue ; minimum 0 mm, aucune marge vibratoire démontrée |
| EM-COL-02 — périmètre global | 17 702 paires prises en compte, dont AABB disjointes, reprise bornée | intersections et erreurs détaillées ci-dessous ; ce nombre n'est pas celui de booléens réussis |
| EM-GRP-01 — enveloppes | C++17, aire et disposition nominale de disques | huit diamètres candidats ; aucune compatibilité CEM/thermique ou fourniture validée ; `dimensionnement_gaines.json` |

L'équivalence mesurée est volumétrique, pas une borne de Hausdorff ni une
preuve de montage. Les minima de distance non conservés ou non calculés
restent `null` ; un zéro mesuré est un contact, pas un dégagement acceptable.

**Collisions.** `baseline_volumes.json` finalise les 361 occurrences
(53 routes, 308 obstacles), mais rapporte six intersections entre les quatre
enveloppes Airy et 159 paires inconnues après expiration de trois lots de
35 s (CA01, Holybro6XOrin et P75_Cadre). Cette preuve conserve ses erreurs.
`affinage_volumes.json` porte séparément la reprise avec validité des entrées
mise en cache et contrôles BRep maintenus, ainsi que la mesure des recouvrements
Airy hors zone nominale d'éclatement. Le bilan consolidé indique le résultat
effectivement finalisé ; `complete=true` signifie rapport terminé, pas absence
de défaut. Un recouvrement d'enveloppes OEM ne permet pas des conducteurs
physiques superposés ; l'intérieur réel de la jonction reste NON_VERIFIE.

**Reprise finalisée : 159/159 paires résolues, aucune inconnue de calcul
résiduelle et aucune intersection supplémentaire détectée.** Pour les composés
coûteux, les intersections sont évaluées sur leurs solides détaillés après
filtrage AABB ; la somme des volumes est une borne supérieure si ces solides
se recouvrent. Tous les résultats correspondants sont nuls à la tolérance.
Les six volumes Airy hors zone nominale sont nuls. Cette localisation ne
qualifie pas leur intérieur, les dégagements de service ni les mouvements.

**Statuts et arrêt.** R48 uniforme sur les points F16 initiaux est
`NON_CONFORME` par manque de longueur de tangence. Le candidat R23,5 et
l'architecture globale restent `NON_VERIFIE` pour l'intégration complète ;
le matériel reste `A_VALIDER_PHYSIQUEMENT`. Aucun faisceau n'est déclaré
globalement `VALIDE_GEOMETRIQUEMENT`. Le gain local F16 (suppression de deux
contacts structure) ne lève ni la condition de flexion caméra ni les inconnues
de cohabitation. Phase D non engagée. Montage/démontage, débattements,
extraction des prises, vibration, thermique et CEM ne sont pas validés ;
aucun essai matériel ou vol n'est exécuté. Les données discriminantes et la
prochaine décision sont dans DOC-MEC.

La [revue indépendante](../hardware/mecanique/cartographe/verification/reconstruction_faisceaux/revue_reconstruction.json)
porte les constats et leur clôture ou maintien explicite.

<a id="validation-moteur-electromecanique"></a>
### 12.1.13 Moteur électromécanique sur banc — 10–11 novembre 2026

`T-EM-ENGINE-01` vérifie la chaîne de conception du banc pour `CAB-CARTO-001`
et `MEC-INT-001`. Le [guide d’exécution](../electromechanical_engine/README.md)
décrit la reprise. La [preuve structurée](verification/electromechanical_engine.json)
identifie les commandes, empreintes, résultats et limites par phase. Le banc
utilise des entrées synthétiques en millimètres dans un repère XYZ, Z vers le
haut. Cette action soutient la complétude électromécanique du lot
ORCH-CAO-MASSE-1. La progression des essais et la priorité du §14 restent
applicables.

| Jalon | Contrôle et critère de sortie |
|---|---|
| J0 — environnement | Probe Part et contrôle Cables, versions et API locales, fermeture XLink et empreintes avant/après. Le refus RPC conduit à un repli testé dans un processus FreeCAD distinct. |
| J1 — contrats | Validation des identifiants, de la provenance et des contraintes, gel des octets et refus des divergences. |
| J2 — extraction | Sauvegarde d’une copie avec dépendances, réouverture et vérification de l’intégrité en processus distinct. |
| J3 — validation | Contrôles V1–V4 sur données de test et sur les mesures natives prises en charge. Les exigences dont les mesures manquent restent ouvertes. |
| J4 — rapports | Longueurs, volumes, dégagements, métriques par zone et projections à cadre commun lorsque les observations le permettent. Les métriques absentes sont identifiées. |
| J5 — variantes | Corridors rattachés aux enveloppes porteuses gelées, hypothèses de connectique et électronique conditionnelles, budget et contraintes vérifiés. |
| J6 — rétrovalidation | Collision native du trajet direct, contournement déclenché par le même défaut et la même paire, réouverture indépendante et comparaison des variantes admissibles. |
| J7 — utilisation | CLI, trois skills, exécution de leurs parcours, résultats et point de reprise par tentative. |

**Résultat du banc — Implémenté.** La paire `L1` / `Obstacle` passe de
31,416 mm³ d’intersection à zéro. Le contournement `lateral` atteint 10 mm
de dégagement pour un seuil de test de 1 mm. Il mesure 121,416 mm, soit 12 mm
de moins que `lateral-large`, et reste seul sur le front de Pareto des
candidats admissibles pour l’objectif de longueur. Le trajet direct est
rejeté. Les variantes de connectique et d’électronique restent
conditionnelles. Le rapport de revalidation confirme le verdict après une
nouvelle ouverture. Les SHA-256 des 941 fichiers contrôlés (938 natifs sous
`hardware/mecanique/cartographe` et trois sources techniques) sont identiques
avant et après la reprise.

L’extraction native est démontrée sur la fixture à deux documents et sur la
copie du sous-assemblage `SA04_Prototype_Perception`. Cette dernière couvre
20 documents, 285 objets et 52 liens. Deux dépendances ouvertes partiellement
ont été chargées en entier avant le contrôle. Les sources ont gardé leurs
empreintes et la copie a été rouverte et recalculée dans un nouveau processus.
Les 61 tests du moteur, dont trois intégrations FreeCAD, et les 19 tests de
l’utilitaire Cables passent. Les trois skills passent le validateur de format
et leurs parcours CLI sont exercés. La couverture de lignes du processus
orchestrateur figure dans la preuve. Le worker est contrôlé par les tests
natifs, hors instrumentation de couverture.

**Clôture du développement — GO 1.** Le rejeu `T-EM-ENGINE-02` valide le
moteur sur deux bancs contrôlés sous Windows amd64, FreeCAD 1.1.3,
OCCT 7.8.1 et Cables 0.3.7. Les 66 tests du moteur, dont six tests natifs,
et les 19 tests Cables réussissent. Le RPC refusait la connexion. Les essais
natifs ont utilisé le Python de FreeCAD dans des processus distincts.
[Preuve de clôture](verification/electromechanical_engine_go1.json)

Sur le banc mobile, V3 vérifie la couronne fermée du support dans le solide
natif et mesure 111,416 mm de portée maximale sur l’axe, pour une limite de
115 mm. La variante de 131,416 mm est rejetée. V4 contrôle le câble sauvegardé
aux poses intermédiaire et extrême. La collision de 31,416 mm³ à la pose
extrême déclenche une correction de la même liaison dans cette pose.
Le dégagement final atteint 28 mm sur cette paire, la longueur développée
reste de 121,416 mm et le rayon minimal est de 5 mm aux deux poses. Le
validateur rejette une variation de longueur de 5 mm et laisse une pose
manquante conditionnelle. Une nouvelle ouverture indépendante confirme le
verdict du candidat corrigé.

L’extraction de `SA04_Prototype_Perception` confirme la sauvegarde et la
réouverture de la copie avec ses 20 fichiers et 52 liens. L’inventaire
complet du prototype a finalisé le contrôle de 137 fichiers, 3 733 objets
et 375 liens. OCCT signale quatre solides et leur agrégat dans
`EQ_Chassis_X650.FCStd`. Le code 2 indique que ces défauts ont empêché la
sauvegarde et la réouverture de cette copie. Les 941 empreintes sources
contrôlées concordent avec l’inventaire initial.

GO 1 couvre les capacités exercées sur ces bancs et l’extraction sur copie.
La réserve V4 correspond à la longueur développée moins la corde entre
ports. La cinématique entre les poses, la tenue des fixations, le mapping
métier du cartographe, le regroupement physique et les métriques dont les
entrées manquent restent **À valider**. La qualification du cartographe
relève de l’action 2 et les essais physiques suivent le §2.

<a id="qualification-moteur-go2"></a>
#### Action 2 — qualification indépendante du moteur, 11 novembre 2026

`T-EM-ENGINE-03` vérifie que le moteur reconnaît ses défauts avant toute
nouvelle intégration. L’action a été bornée aux deux bancs GO 1, aux cas
adversariaux et aux géométries historiques retrouvées. Les exigences des
bancs ont été gelées séparément des candidats. Les natifs historiques ont
été ouverts depuis des copies isolées. Le cartographe complet, sa définition
massique et les essais physiques conservent leurs conditions de clôture du §14.

**GO CONDITIONNEL.** Passage autorisé pour l’usage des capacités démontrées
sur banc sous Windows amd64, FreeCAD 1.1.3, OCCT 7.8.1 et Cables 0.3.7.
Les historiques donnent des constats ciblés. Leur admission globale et
l’usage du moteur pour accepter une conception complète du cartographe
restent **À valider**. [Manifeste de qualification et résultats](verification/electromechanical_engine_go2.json)
[Revue indépendante](../electromechanical_engine/qualification/independent_review.json)

Les comparaisons nominales de banc réconcilient chaque paire de l’inventaire
gelé. Une borne de distance entre boîtes englobantes strictement supérieure
au dégagement requis augmenté de la tolérance permet d’écarter une paire.
Les autres paires passent par un contrôle BRep. Les cas d’extraction sont
mesurés séparément des collisions nominales. Deux réouvertures indépendantes
du même candidat admissible de chaque banc produisent des rapports identiques.
Les 73 tests du moteur, 19 tests FreeCAD/Cables et 6 tests d’isolation
réussissent. Aucun de ces tests n’a été sauté.
Le client RPC local a renvoyé `WinError 10061`. Le repli par processus
FreeCAD séparé a exécuté les contrôles natifs. L’exécution sur RPC disponible
reste **À valider**. [Cas adversariaux et limites par classe](../electromechanical_engine/qualification/adversarial_cases.json)

| Exigence et composant | Défaut reproduit | Correctif et preuve de non-régression |
|---|---|---|
| `MEC-INT-001` → inventaire et contrôle de paires | Un lien de propriété masquait un solide qui recouvrait le câble de 12,566 mm³. Le moteur annonçait une couverture complète. | Rejet de tout solide sans identité de campagne ou pose mobile reconnue. Les candidats du banc sont mesurés dans un seul document. Les fixtures de lien interne et externe sont rejetées après réouverture. L’extraction d’assemblages liés conserve son parcours séparé. |
| `CAB-CARTO-001` → verdict de courbure | Un arc de test de 7,2 mm était rejeté à cause de la lecture 7,199999999999996 mm. | Marge d’arrondi de 16 ULP sur la mesure analytique certifiée, enregistrée dans le constat. Le rayon de 7,199999 mm reste rejeté pour le même seuil. La lecture native de l’arc F16 à 21,999999999999954 mm exerce également ce contrôle d’arrondi. |
| `MEC-INT-001` → comparaison et Pareto | Une copie de rapport dépourvue du constat de couverture pouvait rester admissible. | Cinq constats natifs favorables sont requis pour l’admission. Les différences de métriques restent calculables à périmètre commun. La provenance d’un rapport exige la revalidation indépendante de son natif. |

Le [catalogue des historiques](../electromechanical_engine/qualification/historical_catalog.json)
répertorie les fichiers, preuves, sources d’interface et références manquantes.
Les mesures de trajectoire et de collisions ne certifient que la géométrie
observée. Le classement global reste ouvert pour les cas privés de contrat
d’interface, d’exigence de manipulation, de modèle exact ou de résultat BRep
conclusif. Les vues historiques facilitent l’identification des objets.
Les verdicts reposent sur les critères et mesures cités.
La comparaison avant/après confirme l’intégrité des 1 998 fichiers
catalogués. [Empreintes des sources](../electromechanical_engine/qualification/historical_source_integrity.json)

| Cas historique | Contre-validation et limite |
|---|---|
| F16 initial | Axe rouvert de 425,174 mm et minimum échantillonné de 22 mm. Le couple avec P73 est dégagé dans le contrôle ciblé. La référence de famille distingue 22 mm statique et 48 mm en flexion continue. Le cordon effectivement monté et son usage dynamique restent **À valider**. |
| F16 `BSpline_K` | Axe de 456,959 mm avec un rayon local échantillonné voisin de 0,006 mm. Le recalcul conservait l’ancien solide en mémoire. Après effacement du cache sur la copie rouverte, la gaine n’est pas régénérée et le validateur signale un solide invalide. |
| F16 `BSpline_P` | Rayon minimal échantillonné de 23,663 mm, sans borne globale certifiée. Le couple avec P73 confirme l’interférence par deux méthodes, pour environ 704,63 mm³. Le détail des paires non conclues reste dans la preuve et le décompte de huit intersections appartient au rapport historique. |
| Guides orange et copie modulaire | Sur le périmètre historique identifié, le volume des guides et retenues passe de 221,958 à 30,514 cm³ pour 17 occurrences dans chaque copie. P72 et P73 représentent respectivement 43,85 et 75,75 cm³ sur le monolithe. Statut physique, masse, ancrage, accès, montage et variantes de parcours doivent encore être établis avant acceptation. |
| F12 | La borne native de A tombe sur GPS2 suivant le repère de la carte de référence. Le contrat radio fixe TELEM1. Cette destination est `NON_CONFORME` dans A. La borne de la copie par faces rejoint TELEM1. Brochage et accouplement du lot restent à vérifier. |
| F24A | La cible GPIO de la CAO demeure présumée. Le brochage fournisseur consulté ne démontre pas la correspondance entre le gabarit modélisé et le connecteur réel. Destination `NON_VERIFIE`. |
| F25 | Le catalogue identifie le trajet sous P66, la remontée GPS1 et le clip local P85. Les coordonnées terminales ont été relues. Les preuves historiques de dégagement restent limitées aux volumes et poses modélisés. |
| F31 | Le parcours bas sauvegardé a été relu face aux obstacles du modèle. Les paires non conclues restent ouvertes. L’enveloppe installée, la protection puissance et le volume d’accouplement/extraction CAN1 doivent être contrôlés séparément. Le conflit historique avec F35 et les variantes d’orientation du PM08 ne donnent pas une validation de la manœuvre CAN1. |
| F41 | Axe rouvert ramené de 1 180,942 à 340,408 mm. L’accès fonctionnel de diagnostic reste `NON_VERIFIE` en l’absence d’une longueur utile et d’un scénario de manipulation documentés. |

La variante A et la copie par faces utilisent les mêmes volumes de référence
dans le repère XYZ de l’assemblage, en millimètres. Les 53 axes ont été
recalculés depuis les BRep sauvegardés. Les longueurs portent sur les axes.
L’altitude maximale est le Z maximal des enveloppes de gaine. Les zones, le découpage
et la tolérance de comparaison sont consignés dans les preuves natives
référencées par le manifeste. Les longueurs et altitudes se répètent à
l’identique. Le balayage complet F16 a expiré lors de la répétition, et les
deux passages F31 laissent des paires indéterminées différentes. Le contrôle
ciblé F16/P73 se répète à l’identique.
[Mesures, journaux et critères de rejeu](../electromechanical_engine/qualification/native_evidence.json)

| Métrique | A (mm) | Faces (mm) |
|---|---:|---:|
| Longueur au-dessus de la porteuse | 2 051,213 | 1 802,043 |
| Longueur dans la baie de référence | 4 221,879 | 3 860,643 |
| Longueur sous l’emprise de P66 | 21,721 | 275,508 |
| Longueur totale | 10 885,079 | 10 788,378 |
| Altitude maximale | 170,278 | 170,278 |

Le gain de 249,170 mm au-dessus de la porteuse s’accompagne d’une hausse de
253,787 mm sous son emprise. La hauteur maximale est identique.
Les dégagements de montage, les rayons applicables et l’effet sur la
congestion globale restent **À valider**.

<a id="cartographe-action3"></a>
#### Action 3 — exploration du cartographe sans dock, 11 novembre 2026

`T-EM-ENGINE-04` traite la complétude géométrique et électrique du lot
ORCH-CAO-MASSE-1 (§14, audit AUD-003/004/006/007 au §15). Le
[référentiel de campagne](verification/cartographe_action3_reference.json)
fixe les contrôles V1–V6 et identifie la demande, le GO 2 et les 30 fichiers
de code et d’entrée dont les SHA-256 concordent avec GO 2. Les seuils du
banc ne sont pas applicables au prototype. Il reste à établir la
correspondance entre ports, obstacles et exigences pour geler le contrat
du moteur sur le prototype complet. Les 73 tests du moteur réussissent, y compris les essais
natifs exécutés avec le Python de FreeCAD. Le contrôle RPC local n’a pas
abouti (WinError 10013). Les contrôles natifs ont utilisé des processus
FreeCAD dédiés. Les 137 sources de la fermeture XLink sont identiques avant
et après extraction. Le corpus historique de 1 998 fichiers concorde
avec GO 2.

| Contrôle | Résultat et périmètre |
|---|---|
| V1 — interconnexions | La [matrice](verification/cartographe_action3_interconnexions.json) réconcilie 71 lignes de périmètre, 50 liaisons embarquées, 43 identifiants de liaison de la nomenclature et 53 axes. Neuf liaisons restent non résolues dans la copie de référence. Le natif actif de F12 est identique à celui de A, mesuré sur GPS2 dans le repère RC02 alors que la destination requise est TELEM1. F24A, le brochage et l’accouplement restent ouverts. |
| V2 — intégrité et géométrie | [Extraction sur copie](verification/cartographe_action3_extraction.json). L’inventaire du prototype est complet (137 fichiers, 3 733 objets, 375 liens). Quatre solides HUAZHU-LV-M3-90 et leur agrégat OEM X650 sont invalides. L’extraction renvoie le code 2 avant sauvegarde et réouverture. Les 12 essais de réparation locale sur copie restent invalides. Le sous-assemblage de perception a été sauvegardé puis rouvert en processus neuf (20 fichiers, 285 objets, 52 liens, code 0). Le candidat isolé F31_Sous_P66 est comparé aux obstacles de la copie par faces en excluant le F31 assemblé. Sur 349 paires, 311 sont éliminées par séparation des boîtes et une paire BRep avec l’avionique reste non conclue. |
| V3 — montage et démontage | **À valider**. Mesurer la manœuvre CAN1 autour de F31/F35, l’ancrage des retenues, l’assemblage du passage bas et la réserve accessible de F41. |
| V4 — mouvement | Mouvement non exécuté. Deux mesures indépendantes du couple F16/P73 sur copies historiques reproduisent 0,200 mm de dégagement pour l’axe initial et 704,630 mm³ d’interférence pour la variante BSpline_P. Poses, réserve utilisable et flexion continue **À valider**. |
| V5 — comparaison | Le [rejeu](verification/cartographe_action3_rejeu.json) mesure les mêmes 53 axes en deux passages par historique. De A à la copie par faces, −96,701 mm au total, −249,170 mm au-dessus de la porteuse (zone à partir de Z = 130,052 mm), −361,237 mm dans la baie, +253,787 mm sous l’emprise de la porteuse, altitude de gaine inchangée à 170,278 mm. Ces longueurs sont des mesures de zones géométriques. La congestion, la masse, le montage et la CEM demandent des preuves supplémentaires. |
| V6 — revue des vues | Revue des vues historiques à échelle commune, avec rapprochement des empreintes des natifs et des mesures de zones. Les vues de détail et les volumes de manœuvre des nouveaux candidats restent à produire. |

Le [catalogue](verification/cartographe_action3_architectures.json) décrit
les alternatives A (corridors à équipement fixe), B (implantation et
connectique) et C (redistribution électronique). Les trois pistes restent
**À valider**. Le front de Pareto admissible est vide. **GO 3 non acquis.**
La revue indépendante a réconcilié les empreintes, rapports, statuts
d’exécution et mesures historiques. Pour poursuivre, vérifier une source CAO
OEM corrigée sur copie. Une enveloppe conservatrice sourcée peut servir au
préfiltrage des passages dans un périmètre explicite. Le choix du premier
candidat dépend aussi du mapping des interfaces et du préfiltrage des accès
CAN1, F16 et F41. Les contrôles de montage, vibration, fatigue, CEM et
thermique suivent la progression du §2.

**Reprise sur copie corrigée.** Les quatre BRep invalides du châssis X650
ont été remplacés, dans la branche OEM de la copie, par la réservation
nominale Ø5 × 90 mm avec alésage simplifié Ø2,5 mm. Les quatre liens actifs
de SA01 conservent leur référence paramétrique. L’assemblage complet a été
recalculé, sauvegardé puis rouvert et recalculé dans un second processus
FreeCAD. Les 137 fichiers, 3 733 objets et 375 liens sont réconciliés,
sans objet invalide, lien rompu ni document partiel. Les empreintes des
137 fichiers natifs sources concordent. [Preuve X650](verification/cartographe_action3_x650.json)

La piste A1 a été reprise sur une seconde copie avec le même X650 corrigé.
Le trajet F12 rejoint TELEM1 dans le repère CAO et passe de 183,979 à
163,999 mm. SA07 a été sauvegardé. La racine complète a été rouverte puis
recalculée dans un processus distinct, avec contrôle du lien F12.
Le criblage géométrique de 2 418 paires couvre 272 mesures BRep, sans
intersection de volume positif ni paire non résolue sur ce périmètre.
Deux contacts géométriques avec la porteuse restent à instruire. La
retenue, l’accouplement et le brochage restent **À valider**.
[Preuve A1/F12](verification/cartographe_action3_reprise_f12.json)

Pour B1, le criblage sur la copie de référence autour de CAN1 a mesuré
0,800 mm de jeu avec F35 pour un gabarit vertical de 4 × 4 × 10 mm.
Avec un gabarit de 6 × 6 × 10 mm, F35 intersecte le volume de 1,082 mm³.
Les cotes de la fiche et de l’outillage ainsi que les autres obstacles
restent à vérifier avant de choisir un déplacement. Aucun gabarit
d’essai ne fait autorité pour l’enveloppe réelle. Le GO 3 reste ouvert.
[Préfiltrage B1/CAN1](verification/cartographe_action3_reprise_can1.json)

**Accès CAN1 et essai F35.** Le plan JST GH4 et la porteuse OEM fixent le
gabarit nominal à 4,15 × 6,25 × 5,7 mm, largeur selon Y et retrait selon +Z.
L’assise est estimée à partir de la hauteur accouplée de 7,3 mm au-dessus
du PCB. Sur le trajet initial, le gabarit ne touche pas F35 à 4,25 mm de
course et l’intersecte à 5 mm. La course de déverrouillage réelle n’est
pas mesurée. Sur le nouveau trajet, le jeu est d’au moins 3,75 mm avec
F35 pour les courses testées jusqu’à 20 mm. La sonde candidate MPT2SV a
été testée avec des gabarits dérivés des cotes fabricant. Des poses
interfèrent encore avec la retenue P75. Les neuf poses testées côté +X
intersectent F31. Le geste de
déverrouillage, la prise et la réserve du cordon restent à vérifier.
[Preuve CAN1](verification/cartographe_action3_can1_service.json)

F35 passe désormais au sud de CAN1 dans la copie candidate et conserve
ses extrémités, sa longueur de 123,090 mm et son rayon nominal de 5 mm.
La fermeture de 137 fichiers a été rouverte et recalculée en processus
neuf après sauvegarde de F35 et SA07. Le contrôle de 3 005 paires, dont
131 mesures BRep, ne relève aucune intersection au seuil de 0,0001 mm³.
Le jeu de 0,20 mm avec F25 et P75 et la retenue haute restent **À valider**.
Les sources et la copie A1 d’entrée conservent leurs empreintes.
[Preuve F35](verification/cartographe_action3_f35.json)

**Consolidation du 12 novembre 2026.** La copie X650 corrigée regroupe
F12 vers TELEM1, le trajet F35 qui libère CAN1, F25 abaissé sur le chant
est avec P85, et F16 à rayons de 50 mm sur la section mobile et 24 mm
sur la section fixe. La copie a été rouverte et recalculée dans un
processus distinct, avec 138 fichiers, 3 753 objets et cinq liens ciblés
visibles et valides. Les quatre criblages statiques F16/F25/P85/F35
réconcilient chacun 3 006 paires. Les 1 460 mesures BRep ne relèvent
aucune interférence supérieure à 0,0001 mm³ ni paire indéterminée.
Un contact F16–châssis à distance nulle reste à instruire.
[Preuve de la copie consolidée](verification/cartographe_action3_integre.json)
La contre-validation intégrale a sauvegardé l’assemblage puis l’a
rouvert dans un second processus FreeCAD. Elle confirme 376 liens,
aucun objet invalide, lien rompu ou document partiel. Les empreintes
des entrées et des natifs rouverts ont été réconciliées.

À périmètre commun de 53 axes, la longueur totale augmente de 87,3 mm
et la longueur au-dessus de la porteuse diminue de 105,0 mm. L’altitude
maximale des gaines reste 173,3 mm. F25 réduit son point haut de 12,5 mm
et passe 102,1 mm sous le plan P66, sur le côté du plateau.
P85 présente 0,05 mm de jeu nominal au chant et 0,307 mm vers F25.
Sa tenue et le montage de la fiche restent **À valider**.
[Preuve F25 et P85](verification/cartographe_action3_f25.json)

Le gabarit de fiche CAN1 passe sur les courses testées jusqu’à 12 mm
et conserve 4,10 mm avec F35. Les six phases simulées de la sonde
MPT1RSV avec un appui hypothétique de 1 mm et une levée de 4,25 mm
passent sur la copie intégrée, avec une borne de 0,120 mm près de F31.
Le point d’appui du verrou, le geste opérateur et la réserve F31
restent **À valider**. [Preuve CAN1 intégrée](verification/cartographe_action3_can1_integre.json)

F16 mesure 494,608 mm sur l’axe. Le cordon de catalogue de 508 mm
hors tout laisse 428,5 mm après allocation des extrémités dans le
gabarit, soit un déficit de 66,1 mm. Le candidat demande une définition
du cordon et de sa course réelle. Les collisions rigides des poses
d’étude interdisent de déduire la mobilité de la seule souplesse du
câble. [Preuve F16](verification/cartographe_action3_f16.json)

Une variante optique a été sauvegardée et rouverte avec deux dégagements
locaux sur P17 et les passages de P65 portés à Ø8,6 mm. Les 27 poses
discrètes de translation à ±0,50 mm passent les 909 contrôles BRep.
Les ligaments nominaux de 2,80 mm vers le passage M2 et de 2,30 mm vers
le lamage P10 demandent un contrôle de tenue. La course réelle, les
rotations, la fatigue du cordon et les tolérances restent ouvertes.
Cette variante optique a aussi été rouverte avec le trajet F16
de 493,459 mm qui dégage le solide OEM précédemment tangent.
Les quatre poses de câble testées passent. La portion droite
côté mobile à V75 mesure 15 mm. La longueur commerciale disponible
et la tenue de cette retenue restent à démontrer.

Une autre copie rouverte teste le dégagement GPIO avec deux encoches
P75 et un parcours F13A à rayon nominal de 8 mm. Le criblage ciblé
ne relève aucune intersection positive du F13A modifié. Le changement
de tangente à l’antenne et la résistance du guide restent à vérifier.
[Preuve GPIO/F13A](verification/cartographe_action3_f24a.json)

Le diagnostic USB-B/TTL reste ouvert. Aucun des 24 trajets F40 et
20 placements explorés pour l’isolateur ne démontre le dégagement
simultané des deux interfaces. [Preuve F40/F41](verification/cartographe_action3_f41.json)

Le GO 3 reste ouvert.

<a id="moteur-electromecanique-v2-l0"></a>
#### Audit L0 et contrats V2 — 12 novembre 2026

`T-EM-ENGINE-L0` conclut **L0_READY** pour engager le rapprochement L1 du
prototype sans dock. L’audit a vérifié les empreintes de 137 natifs actifs
et de 138 natifs de la copie consolidée. Le registre couvre 71 lignes.
Les 50 lignes embarquées se rattachent aux 53 axes par 56 couples.
Un export KiCad 10.0.6 retrouve les 43 broches sélectionnées sur 15
références. Sous Windows x64, 73 tests
du moteur avec FreeCAD, 19 tests Cables et 6 tests d’isolation passent. Le
planificateur C++17 passe ses 41 assertions. Le banc statique donne deux
rapports identiques en réouvertures indépendantes. Le RPC est inaccessible
depuis la session et le repli par le Python FreeCAD est exercé.

Le contrat et son exemple hypothétique ont passé la validation de schéma
et la revue des références. Le rapprochement métier et le gel des exigences du
prototype restent des prérequis de L2 et L3. L’intégration complète et les interfaces physiques
restent **À valider**. L0 conserve GO 3 ouvert. La CAO du prototype a été
contrôlée par empreinte et fermeture XLink, avec les reçus historiques
pour les mesures natives. [Audit L0](electromechanical_v2/L0_AUDIT.md) ·
[Résultats des contrôles](electromechanical_v2/TEST_RESULTS.json) ·
[Reprise L1](electromechanical_v2/ROADMAP_L1_L5.md#reprise-de-l1)

<a id="moteur-electromecanique-v2-l1"></a>
#### Recherche technique L1 — 12 novembre 2026

`T-EM-ENGINE-L1` conclut **L1_PASS** sur Windows amd64 pour le moteur
C++17/Qt 6, l’API Python, la CLI et les échanges L0. Les 24 tests passent
en compilation principale et indépendante. Le schéma valide les huit
rapports du catalogue hors ligne et le rapport HTTPS Basler. La
régression du moteur FreeCAD existant passe sur les 63 tests hors natif.
Les 137 empreintes de la fermeture CAO active correspondent à L0.

Le parcours F16 retrouve 425,174 mm pour l’axe nominal de l’actif et
494,608 mm pour l’axe de la copie R50/R24. Avec la convention A1 du plan
USBFireWire et l’axe de la copie, l’étude conditionnelle borne la marge
de longueur à environ −53,608 à −22,808 mm. La masse nette du cordon et
le rayon de flexion continue applicable à la pièce montée restent
`UNKNOWN`. La borne fabricant de masse de la caméra, inférieure à 85 g,
est vérifiée sur la copie locale v135 et par requête HTTPS sur v138. Le
rejeu avec DNS indisponible avait finalisé l’inconnue v138 avec diagnostic.

Le moteur est **Implémenté**. Le résultat couvre la recherche et la
traçabilité documentaires. Le gel complet V2, l’admission du prototype et
les essais physiques restent **À valider**. [Reçu L1](electromechanical_v2/L1_RESULT.md) ·
[Preuve structurée](verification/technical_research_l1.json) ·
[Architecture](architecture/ARCHITECTURE_LOGICIELLE.md#recherche-technique-l1)

<a id="moteur-electromecanique-v2-l2"></a>
#### Interconnexion et accouplement L2 — 12 novembre 2026

`T-EM-ENGINE-L2` conclut **L2_CONDITIONAL**. Le banc numérique Windows
amd64 est **Qualifié** pour deux interfaces droites et un cordon à quatre
contacts. Les 25 tests L2 passent. Le nominal établit la continuité, les
repères d’accouplement et la sortie de câble. Les défauts d’identité, de
brochage, de détrompage, de pose, de dégagement et de rattachement sont
rejetés. Une donnée indispensable inconnue donne `INCONCLUSIVE`. Le
FCStd a été sauvegardé puis rouvert et recalculé dans un processus
distinct avec FreeCAD 1.1.3 et Cables 0.3.7.

Le convertisseur rapproche 71 lignes et 53 axes actifs par 56 associations
vérifiées. Le mauvais port F12 de l’actif reste un échec géométrique. L1
laisse ouvertes la révision de la liaison TELEM1 et la limite dynamique du
cordon F16 monté. Les preuves contribuent à la clôture des interfaces
d’ORCH-CAO-MASSE-1. Le graphe gelé du prototype, la compatibilité réelle
des références et les essais matériels restent **À valider**.
[Preuve L2](electromechanical_v2/L2_RESULT.md) ·
[Registre rapproché](electromechanical_v2/L2_RECONCILIATION.json)

<a id="moteur-electromecanique-v2-l3"></a>
#### Décision et exploration d’architectures L3 — 13 novembre 2026

`T-EM-ENGINE-L3` conclut **L3_PASS** sur Windows amd64 pour les cinq cas
synthétiques demandés. Le lot soutient ORCH-CAO-MASSE-1 en distinguant
les problèmes de trajet, de service et d’interface. Les observations
historiques CAN1 et F40/F41 motivent les bancs. L’exploration utilise
les paramètres et exigences synthétiques gelés, avec au plus cinq
variantes F31 et sept F40/F41, hors références et consolidations déclarées.

| Cas de réception | Résultat observé |
|---|---|
| F31/PM08–CAN1 | Deux détours libèrent le trajet avec 0,4 mm de marge et laissent le retrait et l’outil obstrués. La translation de PM08 de −10 mm donne 8,4 mm de marge de service au banc. |
| F40/F41 | Après deux routes insuffisantes, le déplacement de P75 et l’interface passive déportée conservent les deux signaux. La marge locale est bornée à [−4, −1] mm sur le domaine étudié. L’interface active reste `INCONCLUSIVE` avec contrat manquant. |
| Consolidation | Le déplacement et le déport passif passent seuls, puis échouent ensemble avec −3 mm sur la réservation commune. Le témoin compatible passe. Une double affectation contradictoire est refusée. |
| Fiche inconnue | L1 conserve la provenance de la fiche droite et établit un écart de référence. La compatibilité de la fiche latérale reste `INCONCLUSIVE`. Les courses de 8, 12 et 16 mm donnent +1,4, +0,9 et −0,6 mm de marge. Deux échantillons encadrent la transition entre 12 et 16 mm. |
| Déplacement et Pareto | F31, F35 et les deux départs de puissance sont réévalués pour PM08. F40, F41, F24A et le coaxial sont réévalués pour P75. Trois variantes restent sur le front de Pareto diagnostic. Le coût reste inconnu. |

La revue indépendante a rejoué les mutations de graphe électrique,
de seuil et de classement d’exigence ainsi que le refus d’un artefact altéré.
Les décisions et mesures sont stables entre rejeux. Les horodatages L1
se propagent dans les empreintes de preuve. Les projections L0 et le rapport
L1 passent leurs schémas et les dossiers T0 passent le validateur.
Les réservations F31 utilisent des boîtes et des axes polygonaux. Les
marges F40/F41 proviennent du modèle affine du banc. Le prototype et
l’implantation native restent **À valider**.
[Réception et commandes](electromechanical_v2/L3_RESULT.md) ·
[Preuve structurée](verification/architecture_decision_l3.json) ·
[Architecture](architecture/ARCHITECTURE_LOGICIELLE.md#exploration-architecture-l3)

<a id="moteur-electromecanique-v2-l4"></a>
#### Rétrovalidation électromécanique indépendante L4 — 13 novembre 2026

`T-EM-ENGINE-L4` prolonge ORCH-CAO-MASSE-1 en contrôlant les défauts qui
peuvent invalider une définition géométrique ou un raccordement. Le budget
est limité aux cas de réception figés, à deux mesures FreeCAD par natif et
à un délai maximal de cinq minutes par cas. La référence, les seuils, la
recette, les scripts et le binaire sont empreintés avant l’évaluation.
La copie de chaque fermeture permet la réouverture et la mesure en
processus neuf. Les résultats sont rapportés dans le périmètre mesuré.

**Résultat `L4_CONDITIONAL` sur Windows amd64.** Les 100 attentes de
réception correspondent sur 29 cas. Les 71 constats donnent 39 `PASS`,
21 `FAIL` et 11 `INCONCLUSIVE`. Les 19 cas natifs ont chacun fourni deux
mesures reproductibles dans FreeCAD 1.1.3 / OCCT 7.8.1. Les 137 empreintes
du cartographe actif concordent avec L0 avant et après l’exécution.
La vérification L0 et T0 passe. Le rejeu sans FreeCAD conserve 69 attentes
de réception `NOT_RUN`. Le candidat latéral sauvegardé passe et le candidat
direct échoue sous le même gel. Un interpréteur substitué et un artefact
T0 altéré sont refusés.

| Famille | Signal recherché et limite d’interprétation |
|---|---|
| V1 | Le banc à quatre circuits réconcilie les broches, les contacts, la compatibilité et les révisions. Le port F12 erroné, le détrompage incompatible, la révision divergente et la matrice permutée sont discriminés. La perte du retour F41 fait échouer le contrôle même si le signal F40 subsiste. Les références montées F12 et F24A restent **À valider**. |
| V2 | La recette exerce le rayon analytique, la B-spline F16 K, la gaine en cache, le chargement partiel et le criblage conservatif des paires, dont la paire ajoutée hors sélection. Le contact F16/châssis à distance et volume nuls est interdit dans son périmètre. |
| V3 | Les repères de deux embases et fiches, le volume de retrait CAN1 et l’appui d’une retenue sur le porteur sont contrôlés. L’obstruction historique concerne le gabarit nominal de 5 mm face à F35. Le geste, l’outil et l’extraction complète du PM08 réel restent **À valider**. |
| V4 | Les poses intermédiaire et extrême du banc mobile éprouvent la réserve, la longueur développée et les distances. Une collision à la pose extrême est discriminée. L’enveloppe continue, la traction, le pincement et la tenue en service restent **À valider**. |
| V5 | Les deux historiques A/Faces sont comparés sur les mêmes 53 axes. La longueur totale, la cote haute et la longueur discrétisée en zone sont rejouées. Le banc plus court qui occupe davantage la zone supérieure est défavorable sur ce critère. La masse et la maintenabilité du système restent ouvertes. |
| V6 | Les vues dessus, dessous, profils, connecteurs, extraction et retenues servent à formuler des hypothèses testées par mesures de distance, volume, pose ou appui. |

La variante F16 K donne un témoin local de rayon de 4,95 × 10⁻⁸ mm et une
gaine invalide après régénération. Le contact F16/châssis donne 0 mm et
0 mm³. Le retrait CAN1 rencontre F35 sur 0,05176 mm³. L’historique F16
initial garde 0,20 mm de dégagement au droit de P73. Le câble haut du
banc mesure 117,416 mm contre 121,416 mm pour le témoin latéral, avec une
occupation haute bornée entre 65,708 et 71,708 mm contre 0 mm. Les témoins
et échecs historiques restent limités aux mesures correspondantes.

Les résultats et limites de réception sont consignés dans la [preuve L4](verification/electromechanical_validation_l4.json).
La procédure conserve la [matrice de traçabilité et les commandes](../validation_engine/README.md).
La fatigue, la CEM et la sécurité du vol gardent leurs preuves et essais
propres. GO 3 reste ouvert et la réalisation native du cartographe relève
d’un lot ultérieur.

<a id="moteur-electromecanique-v2-l5"></a>
#### Convergence et consolidation électromécanique L5 — 13–14 novembre 2026

`T-EM-ENGINE-L5` vérifie qu’une campagne peut aboutir à une seule
architecture intégrée sur un banc isolé. La demande L5 contribue à
ORCH-CAO-MASSE-1 en réduisant le risque d’assembler des variantes locales
incompatibles. L’action est réversible et bornée aux fixtures, aux copies
FreeCAD et à leurs rapports. La configuration autorise douze candidats
détaillés, trois corrections locales successives, au moins deux familles
examinées après escalade et deux tentatives de consolidation. Les budgets
par problème et par famille sont fixés avant l’exécution.

**Résultat `L5_PASS`, décision `GO` pour le banc numérique** sur Windows
amd64, GCC 16.2, Qt 6.11.2, FreeCAD 1.1.3, OCCT 7.8.1 et Cables 0.3.7.
Sept variantes ont été construites. Trois corrections échouent sur la même
paire L1–obstacle et déclenchent L1 et le criblage L3. Trois familles sont
examinées. La variante de connectique coudée reste conditionnelle et la
seconde demande identique est détectée. Une route équivalente est
dédupliquée. Une fusion locale est refusée sur les affectations concurrentes
de L1. Sur les deux tentatives natives, la première est rejetée par L4 pour
garde nulle entre L1 et L2. La seconde, `lateral-service`, passe les
13 contrôles obligatoires, dont les quatre extractions nominales, et couvre
L1 et L2. Sa longueur totale est de 221,416 mm et sa cote haute de
10,993 mm. Ces métriques proviennent des réouvertures indépendantes de la
copie retenue.

La préférence du banc va à la cote haute minimale, puis à la longueur,
avec 0,001 mm de tolérance par objectif. La variante haute est plus courte
dans la comparaison locale et consomme davantage de hauteur. Sa fusion
reste hors budget. Le Pareto consolidé se limite aux copies admissibles
effectivement revalidées. Le manifeste T0, le rapport de sélection et le
checkpoint reprenable sont identifiés dans la
[preuve L5](verification/electromechanical_convergence_l5.json).
[Recette](../convergence_manager/README.md)

La réception CTest L5 passe 3/3 suites, dont 11 scénarios CLI. Le rejeu
avec interruption conserve le manifeste, l’historique et les métriques
dans les tolérances déclarées. Une variante locale et un portefeuille qui
portent le même nom conservent des reçus de construction distincts.
Le scénario d’entrée documentaire utilise deux transcriptions synthétiques
de fiches fabricant. Leur contradiction donne `L5_CONDITIONAL` quand la
preuve conditionne le jalon. La branche indépendante est consolidée.
Les contrôles injectent aussi un échec de sauvegarde, un XLink rompu et
l’indisponibilité de FreeCAD. Les régressions L1 à L4 passent sur leurs
deux configurations CTest (4/4 chacune) et les régressions du moteur
électromécanique passent 76/76. Les deux rapports L4 de consolidation
satisfont les contrats L0 et le validateur T0 accepte la campagne.

**Critères proposés — À valider avant engagement**

| Jalon | Critères de passage proposés |
|---|---|
| GO2bis | Rejouer le parcours L5 sur des bancs isolés avec les versions cibles. Vérifier reprise, gel, couverture, échec borné, provenance des preuves et rollback. Ajouter une consolidation avec fermeture XLink et un cas combinant géométrie native et contrôle électrique indépendant. Identifier la portée exacte des contrôles mobilisés. |
| GO3A | Sur une copie du périmètre cartographe approuvé, réconcilier lignes, axes, broches, références et révisions montées. Geler les exigences depuis leurs sources et cribler les variantes sur copies. Réserver la reconstruction détaillée et la rétrovalidation de la cible commune à GO3B. Bloquer les interfaces critiques dont le référentiel reste insuffisant. |
| GO3B | Après admission du référentiel GO3A, construire une copie FreeCAD consolidée et vérifier indépendamment les connexions électriques et la géométrie sur les natifs sauvegardés et rouverts. Comparer les métriques au périmètre gelé. Les mesures physiques relèvent de GO4/GO5 selon les prérequis de DOC-VAL §2 et §14. |

Le banc L5 couvre les axes statiques, les paires et les volumes de service
nominaux. La [qualification GO2bis](#qualification-moteur-go2bis) statue sur
ce périmètre. Le brochage observé et la tenue physique restent **À valider**.

<a id="qualification-moteur-go2bis"></a>
#### Qualification du moteur V2 — GO2bis, 14 novembre 2026

**GO conditionnel** sur Windows amd64. Le périmètre admis couvre la
recherche traçable, les bancs numériques d’interconnexion, l’exploration
bornée, les rétrovalidations ciblées et la consolidation sur banc
monodocument. Le dossier de qualification associe chaque contrôle à son
oracle et à ses preuves. [Matrice GO2bis](verification/GO2BIS_QUALIFICATION.md) ·
[Reçu structuré](verification/go2bis_results.json)

- Les 71 lignes se rapprochent de 53 axes par 56 associations
  bidirectionnelles. Les 50 lignes embarquées peuvent partager un axe ou
  en référencer plusieurs. Les 21 autres portent leur motif d’absence
  d’axe embarqué. Le candidat d’interconnexion du cartographe reste
  `INCONCLUSIVE`. [Preuves L0–L2](verification/go2bis_l1_l2.json)
- La réception L4 sur le code corrigé compte 29 cas et 71 constats, dont
  39 `PASS`, 21 `FAIL` attendus et 11 `INCONCLUSIVE` attendus. La variante
  sans FreeCAD produit 69 attentes `NOT_RUN`. Les réouvertures indépendantes
  de A, Faces et de la copie consolidée contrôlent respectivement 141, 145
  et 138 fichiers natifs. L’inventaire BRep exhaustif de la copie consolidée
  a dépassé deux fois le délai de 180 s. Les contrôles historiques ciblés
  retrouvent F12 vers GPS2, le rayon extrême et la gaine invalide F16,
  l’interférence F16/P73 et une contrainte d’accès F31. F24A, la réserve
  F41 et la tenue de P85 restent `INCONCLUSIVE`. [Preuves L4](verification/go2bis_l4.json)
- Sur la branche `codex/go2bis-corrections`, les mêmes témoins vérifient les
  corrections de longueur et polarité L2, de provenance du port et de
  caractéristiques du cordon L4, et de reprise et de conservation du gel L5.
  La fusion statique couvre les deux liaisons requises. L4 co-évalue la
  géométrie de cette famille de banc et un graphe électrique indépendant.
  La traçabilité entre le graphe et les câbles natifs, ainsi que
  l’admission d’une fusion L5 composée de plusieurs natifs XLink, restent
  **À valider**. [Preuves L3 et L5](verification/go2bis_l3_l5.json)

**GO3A — portée admise.** Si une suite est engagée séparément, le moteur
peut servir à réconcilier les lignes, préparer le gel, instruire les
inconnues et cribler les variantes sur copies isolées. La reconstruction
et l’admission du cartographe consolidé restent suspendues à la démonstration
de la chaîne liée et du rattachement électrique indépendant, ainsi qu’à la
fermeture des inconnues critiques du périmètre choisi.

**Admission GO3B — À valider sur la cible.** Identifier les révisions,
les fiches OEM, les gestes de dépose et la cinématique applicable pour
définir les contrôles numériques. Les vérifications physiques de montage,
de retenue et de tenue requièrent un protocole approuvé selon les §2 et §14.

<a id="cartographe-go3a"></a>
#### Architecture du cartographe — GO3A, 14 novembre 2026

**GO3A_CONDITIONNEL.** Le dossier est **Implémenté** avec des preuves
et copies isolées, et la configuration H-01 demeure **À valider**.
L’architecture conserve les équipements de la BOM du prototype sans dock.
Elle reprend les corridors de chant et dessous, des corrections d’interface
et un déport de service passif. Les 71 lignes sont rapprochées, dont 50
embarquées avec 56 associations couvrant 53 axes. Les 21 lignes sans axe
portent un motif individuel. La mise en service des quatre branches LED
n’est pas instruite. [Dossier de reprise](verification/go3a/GO3A_HANDOFF.md) ·
[Reçu de campagne](verification/go3a/GO3A_MANIFEST.json)

| Contrôle | Résultat observé et portée |
|---|---|
| Réconciliation L2 et netlist CA01 | Rejeu L2 identique à GO2bis. KiCad recoupe 43 broches sur 15 références et les quatre résistances DNP. L’anomalie F12→GPS2 dans l’actif et l’accouplement SMA du GNSS restent tracés. La BOM recense 142 côtés. Les révisions montées, matrices complètes et volumes de service restent à établir selon chaque interface. |
| Fermeture CAO et inventaire | 137 FCStd et quatre auxiliaires vérifiés par empreinte sur copie. Onze chargements partiels complétés, aucune dépendance manquante ou externe à la copie. Le passage d’inventaire BRep a expiré à 120 s avant réception d’un résultat sauvegardé et rouvert. L’actif et la copie Action 3 ont six dépendances différentes, et P85 figure seulement dans le témoin. |
| Alternatives et voisinage | Trois dossiers T0 L3 validés, dont deux mutations rejetées comme attendu. Les familles A/B/C et leur combinaison sont comparées. Le contrat de H-01 impose la conservation de l’isolement et des signaux. La continuité du déport a été vérifiée au banc L3. Dans le criblage des sorties sur copie, le gabarit TTL recoupe la PDB aux deux positions de sonde étudiées. Aucun candidat cartographe admissible démontré. |
| Reprise GO3B | Valider la baie commune CAN1/F31/F35/PM08 et F40/F41, la chaîne GPIO/CSI, les prises et le mouvement caméra, les retenues et les extrémités OEM. Démontrer la fermeture XLink avec un graphe électrique indépendant rattaché aux natifs. Masse, centrage, montabilité avec tolérances et essais GO4 restent ouverts. |

<a id="cartographe-go3b"></a>
#### Intégration du cartographe — admission GO3B, 14 novembre 2026

**`NO_GO_MOTIVE` à l’admission.** Le gel documentaire H-01 est intact.
GO3A reste conditionnel avec les interfaces critiques ouvertes et aucun
candidat admissible. La contre-épreuve GO2bis sur XLink complet laisse
13 contrôles natifs `NOT_RUN`. Le lien entre le graphe électrique
indépendant et les occurrences natives reste à démontrer.
[Preuve d’admission](verification/go3b/GO3B_ADMISSION.json) ·
[Synthèse GO3B](verification/go3b/GO3B_REPORT.md)

Le rejeu L2 est identique octet pour octet. Les 71 liaisons et 142 côtés
A/B concordent avec 53 axes et 56 associations bidirectionnelles. La
fermeture XML contient 137 FCStd et les 180 fichiers empreintés au départ
sont retrouvés identiques à la fin. Le rejeu KiCad recoupe 43 broches CA01
et confirme R530–R533 DNP. Les contrôles de réception d’un candidat et les
métriques avant/après sont `NOT_RUN`, après arrêt avant construction.
[Matrice d’interconnexion](verification/go3b/GO3B_INTERCONNECTION_COVERAGE.csv) ·
[Empreintes](verification/go3b/GO3B_SOURCE_MANIFEST.json)

La reprise demande un témoin XLink sous gel avec rapprochement indépendant
port/contact → conducteur → occurrence, réouverture et détection d’un défaut
injecté. Elle demande aussi l’identification de TELEM1, la fermeture de
l’accès conjoint CAN1/diagnostic avec isolement, la définition GPIO/CSI et
F16/M8 et les autres verrous H-01. Les critères de réception et de comparaison
restent **À valider**. [Verrous GO3A](verification/go3a/GO3A_HANDOFF.md#verrous-de-réception-go3b)

<a id="cartographe-go3a-revise"></a>
#### Préparation des essais sur copies — GO3A V2.1, 17 novembre 2026

**`GO3A_EXPLORATION_READY`.** Le préflight donne `EXPLORATION_ALLOWED`
pour H-03, H-02 et H-01, à partir du gel historique et de trois demandes
liées aux contrats de construction. Les huit exigences G3A-01 à G3A-08
restent `INCONCLUSIVE`. Aucun candidat cartographe n’a été construit
pendant ce lot. La réception rend `FINAL_NO_GO` et le rejeu historique
rend `NO_GO_MOTIVE`. Le portefeuille ouvre des essais CAO hors tension.
Les preuves de conformité du montage restent **À valider**.
[Portefeuille, demandes et reçus](verification/v21_go3a_candidates.json) ·
[Recette GO3B](electromechanical_v2_1/05_GO3A_ARCHITECTURES.md)

| Contrôle | Résultat observé |
|---|---|
| Gel, L2 et CA01 | Deux gels concordants, 71 lignes, 53 axes, 56 associations bidirectionnelles et 21 exceptions motivées. Rejeu KiCad sur 43 broches et R530–R533 DNP documentaires. |
| Fermeture mécanique | FreeCAD 1.1.3, OCCT 7.8.1 et Cables 0.3.7 sous Windows `amd64`. 137 natifs et 4 auxiliaires vérifiés, 2 772 occurrences résolues sur copie, recalcul sans sauvegarde. |
| L1–L3 | 19 recherches L1 finalisées, dont 6 résolutions documentaires et 13 inconnues. Rejeu d’architecture L3 sur banc synthétique, 27 critères réussis et reçu T0 valide. Le coût manque au front de Pareto du banc. |
| Préflight C | Les trois demandes finalisées contrôlent 180 entrées. Pause et reprise H-01 à budget constant. Écriture vers l’actif, collision connue et promotion d’un verrou à `PASS` refusées. L’exécutable V2.1 du gel corrigé C est requis. Le rejeu avec le binaire de l’arbre courant échoue sur le SHA du worker. |
| Relocalisation C4 et L4 | Rejeu du banc synthétique XLink avec translation de 12 mm, 4 conducteurs et 8 contacts conservés, 15 contrôles géométriques réussis après réouverture. Changement de fiche hors capacité et affaiblissement du rayon refusés. T0 vérifié sur le banc et les cas L4. |

Les sept intersections du prototype B.2 et la couverture des contacts,
outils, mouvements, retenues et masses du futur candidat restent à
instruire. Le banc C4 vérifie la méthode de relocalisation dans son
propre périmètre. Le constructeur GO3B devra appliquer les mutations à
une fermeture privée du cartographe, avec projection électrique
indépendante et contrôle dans les deux sens. L’essai physique conserve
la progression du §2. [Rejeu des entrées](verification/v21_go3a_reference_replay.json) ·
[Verrous et nomenclature](verification/v21_go3a_evidence_gaps.json) ·
[Paires B.2](verification/v21_b2/coverage.json)

<a id="cartographe-go3b-reconstruction"></a>
#### GO3B V2.1 construit et contre-validé — 17 novembre 2026

**`GO3B_CAO_NO_GO_MOTIVE`.** La porte exploratoire a été rejouée
sur les trois demandes GO3A avec le binaire C scellé. Le témoin est
mesuré avant mutation et les sources sont contrôlées après exécution.
Huit tentatives de variantes produisent six copies sauvegardées et deux
échecs de génération conservés. Une consolidation des corrections
communes ajoute une expérience, soit 9/12 crédits. Les deux configurations
de chaque famille sont rejetées sur les défauts mesurés.
La reconstruction est **Implémenté**, l’admission et le montage restent
**À valider**. [Rapport GO3B demandé](electromechanical_v2_1/06_GO3B_REPORT.md) ·
[Variantes](verification/v21_go3b_candidates.json)

| Exigence, composant et contrôle | Résultat et portée |
|---|---|
| G3A-01 à G3A-08 → gel et fermeture → T-GO3B-REF/NATIVE | Windows amd64, FreeCAD 1.1.3, Cables 0.3.7, OCCT 7.8.1. Les six variantes et la consolidée sont sauvegardées et rouvertes. La consolidée compte 138 natifs, sans lien rompu ni objet en erreur. Les 142 fichiers sources sont identiques avant/après. Probe Part et 19/19 tests Cables réussis. |
| G3A-01/02/03/05/07 → graphe L2, CA01 et occurrences → T-GO3B-GRAPH | 71 lignes, 142 côtés, 53 axes, 56 associations et 21 exceptions motivées. TELEM1 corrigé sur copies, GPS2 rejeté sur témoin. Rejeu CA01 sur 43 broches documentaires, 15 références, six feuilles et quatre DNP. Négatifs mauvais côté et repère décalé discriminés. L2 INCONCLUSIVE sur la consolidée, contacts montés et continuité physique ouverts. Régressions 3/3 suites réussies. |
| G3A-07/08 → solides et paires B.2 → T-GO3B-B2 | 566 solides PASS et 53 routes INCONCLUSIVE sur la consolidée. 28 567 paires câble éligibles, 26 941 exclusions AABB. Les 1 629 paires retenues et supplémentaires donnent 7 FAIL, 1 562 INCONCLUSIVE et 60 NOT_RUN pour l’admission. Les mesures nominales correspondantes comptent 1 562 PASS géométriques et sept FAIL. |
| G3A-08 → fermeture et projections L4 → T-GO3B-XY | L4 XLink et finalisation T0 exécutés sur H03-A et la consolidée. T0 validé code 0. Le résultat L4 conditionnel garde les contacts et les tâches non mesurées ouverts. |
| G3A-02/04/05/06 → interfaces et appuis → T-GO3B-SERVICE | 93 enveloppes ASSUMED mesurées séparément, admission INCONCLUSIVE. Les branches historiques F40/F41 de la consolidée restent à 98,871 et 53,639 mm des faces candidates. Les appuis H03 sont rejetés sous leurs hypothèses. Mouvements continus et gestes réels NOT_RUN. |
| G3A-08 → métriques et nomenclatures → T-GO3B-METRICS/MASS | Même inventaire des 53 axes et mêmes zones gelées. Consolidée à 12 143,722 mm contre 12 125,900 mm au témoin. Masse totale, centrage et union des volumes connectés exacts inconnus. BOM électrique et physique dérivées disponibles. |

Les sept défauts B.2 sont remesurés sur toutes les copies. Les six
recouvrements Airy restent ouverts. F37_POS/P73 reste en échec au seuil
gelé nul pour 2,8373 × 10⁻⁸ mm³, avec interprétation physique à instruire.
La consolidée reprend 1 533 paires après identité stricte BRep/pose/
visibilité/critères et finalise 36 nouvelles mesures, dont sept échecs.
Les couples porteur/F12, porteur/F25 et porteur/F35 bloquants et les
paires hors budget restent NOT_RUN dans leur dénominateur.
Les variantes présentent des défauts supplémentaires et leurs couvertures
diffèrent. Aucun classement de conformité n’est établi.
[Contre-validation](verification/v21_go3b/independent_evidence.json)

La consolidée réunit F12/TELEM1, F35 au sud et F25/P85.
Les décisions contradictoires des trois familles rejetées sont écartées.
Le prochain essai doit concevoir un appui ancré de l’isolateur, dégager
F40 des retenues et recontrôler CAN1/diagnostic et toutes les branches
affectées. Montage, continuité, isolement, traction, mouvement,
vibration/fatigue, CEM, thermique et vol restent NOT_RUN.
[Contrôles et exigences](verification/v21_go3b_validation.json) ·
[Manifeste et copies natives](verification/v21_go3b_manifest.json) ·
[Essais GO4](verification/v21_go3b/go4.json)

<a id="preuve-connectique-v21"></a>
#### Connectique V2.1 du prototype sans dock, 15 novembre 2026

`T-CARTO-V21-CONNECTORS` prolonge l’admission GO3B sur le périmètre H-01.
Le contrôle croise les 71 lignes, 142 extrémités, 53 axes et 56 associations
dans les deux sens. Les 21 lignes hors axe gardent leur motif d’origine.
Le rejeu des bancs L2 vérifie les défauts de port, clé, cavité, numéro de
broche et signal, ainsi que les volumes accouplés, de retrait et d’accès.
La réouverture d’une copie XLink donne 108 poses d’équipement et aucune
attache de contact aux 106 bouts WireFlex observés. Pour F16/B, le retrait et
l’accès donnent des conflits de gabarits candidats au voisinage du pack.

**`V21_CONNECTORS_CONDITIONAL`.** Les contrôles numériques sont **Implémentés**
sur Windows `amd64`. La réception réelle reste **À valider** pour les
révisions et lots, la continuité, les volumes de montage et le mouvement
d’extraction. Les tests synthétiques et la relecture de la copie ne ferment
aucun des contrôles de réception GO3B. Le prochain signal est un plan orienté
applicable aux exemplaires, avec les repères des embases et les gestes
de service des interfaces critiques. [Preuve](verification/v21_connector_tests.json) ·
[Inventaire](verification/v21_connector_inventory.csv) ·
[Recette](electromechanical_v2_1/02_CONNECTOR_RESOLUTION.md)

<a id="preuve-xlink-v21"></a>
#### Validation XLink de la fermeture cartographe, 15 novembre 2026

`T-CARTO-V21-XLINK` exerce la chaîne graphe L2 → occurrences du montage →
relecture et mesure FreeCAD. Sur Windows `amd64`, le prototype actif est
copié avec ses 137 natifs. La sauvegarde de la racine de copie et sa
réouverture s’exécutent dans deux processus. Les empreintes des sources et
des dépendances sauvegardées sont contrôlées. Le graphe L2 relie 53 axes
natifs à 56 segments de parcours et conserve les motifs des 21 lignes hors
axe. Il donne 108 poses d’équipement sur 142 côtés, dont 96 sur 100 côtés
du faisceau embarqué. Les contacts du montage restent sans attache démontrée.

Le calcul nominal valide les 565 solides terminaux visibles récupérés et
relève les rayons des 53 axes analytiques. La réservation CA01
`ReserveTVS` reste sans solide exploitable. Sur 28 514 paires de solides
visibles comprenant au moins un câble, les boîtes englobantes en écartent
26 905. Trois lots bornés mesurent 130 des 1 609 paires restantes et
laissent 1 479 `NOT_RUN`. Le dernier lot reprend 720 mesures déjà enregistrées.
Le criblage GO3A relève six recouvrements entre le tronc et les branches du
faisceau Airy, ainsi qu’entre ses branches. La définition de l’éclatement et
les zones de contact autorisées restent à vérifier au montage.

Le témoin historique L4 de deux documents a été relu séparément.
Ses 13 contrôles auparavant `NOT_RUN` donnent 3 `FAIL` et 10
`INCONCLUSIVE`. Le natif historique ne contient plus les proxies
nécessaires à la régénération de ses deux gaines. Le banc reconstruit
avec proxies préservés donne 13 `PASS`. Il couvre dix paires, dont
deux BRep et huit exclusions AABB, et quatre retraits avec quatre
obstacles par volume.

**`V21_XLINK_CONDITIONAL`.** État de la chaîne de preuve numérique
**Implémenté**. La validation du montage reste **À valider** pour les
contacts, les rayons et tangentes aux ports, les montages de fiches, les
retenues, les courses et enveloppes cinématiques. Les tests du prototype
portent sur sa fermeture de 137 natifs. La fermeture Action 3 de 138 natifs
conserve ses preuves propres. [Couverture](verification/v21_xlink_coverage.json) ·
[Recette](electromechanical_v2_1/03_XLINK_VALIDATION.md)

<a id="qualification-xlink-v21-b2"></a>
#### Clôture de la couverture XLink V2.1 B.2, 17 novembre 2026

`T-CARTO-V21-XLINK-B2` complète le criblage du cartographe actif sans
dock, en état nominal sauvegardé, avec le validateur scellé de la mission
B sous Windows `amd64`. Les 267 observations initiales ont été authentifiées
et les 1 342 paires restantes mesurées. Les 26 905 exclusions AABB ont été
vérifiées séparément. Les 1 609 paires candidates donnent 1 602 `PASS`
de mesure et 7 `FAIL`. Aucun résultat de mesure ne reste indéterminé ou
`NOT_RUN`. Le checkpoint final et ses preuves T0 sont valides. La réouverture
indépendante reproduit 14 mesures, dont les sept interférences, et les
202 empreintes originales concordent.

Le moteur reçoit `GO_B` et est **Qualifié** pour la couverture nominale de
ces paires XLink sur cette cible. Le prototype est **non conforme** dans
ce périmètre géométrique. Six intersections concernent les gaines AIRY
au nœud d’éclatement et une concerne F37_POS et le guide P73. Le criblage
conserve 1 602 paires au statut d’admission `INCONCLUSIVE`. Le montage,
les critères fonctionnels et la qualification physique restent **À valider**.
GO 3A et GO 3B sont restés `NOT_RUN`.
[Clôture et preuves](verification/v21_b2/REPORT.md) ·
[Couverture JSON](verification/v21_b2/coverage.json)

<a id="qualification-integree-v21"></a>
#### Qualification indépendante de l’intégration V2.1, 15 novembre 2026

`T-CARTO-V21-QUAL` porte sur l’aptitude de la livraison à piloter une
campagne numérique sur copies. Les oracles des cinq lots ont été gelés
avant construction et les dossiers de revalidation ont été créés à part.
Le rejeu H-01 a identifié un écart sur les 180 fichiers d’autorité. Le
préflight du moteur courant refuse les trois modes avant l’évaluation
des règles. Sur banc, une sortie fictive à l’intérieur d’une fiche est
acceptée par L2 et par l’adaptateur natif. Une mesure falsifiée dans le
cache XLink remplace un `FAIL` géométrique par un `PASS` sans remesure.
Le contrôle de structure T0 accepte la sortie ainsi produite.

Le prototype actif a été relu dans une fermeture privée de 137 natifs.
Les 71 lignes, 53 axes et 56 associations sont réconciliés. Les contacts
restent ouverts et 1 506 paires candidates sont `NOT_RUN`. La convergence
L5 a construit et revalidé une fusion de parcours sur banc. Le gestionnaire
ne consomme pas la file du préflight et son constructeur n’a pas réalisé
de décision de connectique ou d’implantation sur un natif XLink.

**`V21_EXPLORATION_NO_GO`** pour la chaîne intégrée. La reprise exige un
référentiel H-01 compatible et vérifiable, une preuve de sortie de fiche
et de provenance indépendante, des mesures XLink de reprise intègres,
et un parcours exécuté du plan à la copie consolidée en reliant les
contrôles électriques et natifs. Le montage et la réception finale restent
**À valider**. [Matrice Q1–Q5](electromechanical_v2_1/04_QUALIFICATION.md) ·
[Preuves](verification/v21_qualification_results.json).

<a id="requalification-v21-c"></a>
#### Requalification indépendante V2.1, 17 novembre 2026

`T-CARTO-V21-FIX-C` confronte la livraison corrective au gel de
`T-CARTO-V21-QUAL` du 15 novembre, sous Windows `amd64` avec FreeCAD 1.1.3,
OCCT 7.8.1 et Cables 0.3.7. C0 admet `GO_A` au commit `d5706a0` et
`GO_B` après la [clôture B.2](#qualification-xlink-v21-b2) sur `b17a915`.
Les empreintes du gel historique, des deux fermetures L0 de 137 et 138 natifs,
des preuves B.2 et des exécutables scellés concordent. Les oracles de
recette sont antérieurs aux exécutions et les mesures de réception utilisent
les natifs sauvegardés. Le correctif C4 est isolé au commit `71f7218`.
[Reçu, matrice par cas, commandes et empreintes](verification/v21_fix_c_qualification.json)

| Lot | Résultat du 15 novembre | Résultat de la requalification |
|---|---|---|
| Q1 · Préflight, gardes et reprise | Les trois modes échouaient au contrôle du worker. Une hypothèse impérative déclarée `PASS` traversait la garde isolée. | 16 exécutions concordantes. `historical` donne `NO_GO_MOTIVE` à 0/12, `explore` donne `EXPLORATION_ALLOWED` avec huit écarts et `final` donne `FINAL_NO_GO`. L’hypothèse et le faux reçu sont rejetés. Worker, entrée ou manifeste altérés sur copie produisent le code 1 avant verdict. La reprise conserve le plan, les identités et le préfixe de file. |
| Q2 · Interfaces, identité et provenance | Nominal accepté. Faux repère de sortie et provenance locale acceptés à tort. | 12 cas L2 et deux contrôles natifs concordants. Le nominal rouvert conserve deux cartes, deux embases, deux fiches, quatre conducteurs et huit paires de contacts. Le repère décalé de 3 mm avec l’axe est rejeté. La provenance locale reste `INCONCLUSIVE`. |
| Q3 · XLink et couverture | Mutation de dépendance détectée. Cache falsifié accepté. 103 mesures sur 1 609 candidates, 1 506 `NOT_RUN`. | La mutation est détectée à racine identique. Le cache falsifié est écarté et la collision de 7,653 mm³ remesurée. Une reprise sous empreinte d’autorité complète le banc interrompu. Sur le même gel cartographe, 14 remesures indépendantes confirment le lot B.2, dont les sept interférences. |
| Q4 · Convergence et réimplantation | Changement de famille et reprise réussis sur le banc D1. La chaîne entre préflight et action de connectique ou d’implantation échouait. | L5 reproduit le changement de famille, le refus d’une fusion incompatible, la reprise, le budget de six détails et deux fusions et les 14 constats L4 du consolidé. Sur le banc lié, `integrate` matérialise une réimplantation choisie par L3 et l’action non supportée est rejetée avant construction. L2 et L4/T0 revalident la fermeture. Un rayon minimal abaissé dans les critères du candidat est rejeté. |
| Q5 · Non-régression historique | Défauts F16, F12 et F31 reproduits. F24A, F40/F41 et P85 restent ouverts. | Six fermetures relues deux fois, résultats répétés. Les témoins F16, F12, F31/CAN1 et P85 concordent. Les 24 variantes de l’archive F40 gardent une collision de service. Montage, pinmux F24A, réserve F41, accès TTL/USB et tenue P85 restent **À valider**. |

Sur le banc lié, les quatre repères de l’interface B, l’équipement et les
volumes de retrait et d’outillage sont translatés de 12 mm selon +Y. L’axe
de gaine passe de 72 à 77,273 mm. La réouverture conserve les quatre
conducteurs et huit paires de contacts. L4 retrouve 100,531 mm³
d’intersection sur le témoin, puis 6 mm de jeu sur le candidat. Les cinq
exclusions AABB et quatre mesures BRep du montage final couvrent les
paires du banc. Les quatre mesures entre réservations et obstacles liés
donnent au moins 22,36 mm de jeu pour un seuil de 2 mm.

| Axe de réception | Périmètre démontré et limite |
|---|---|
| Qualité du moteur | Les contre-épreuves critiques de promotion de preuve, faux repère, fausse provenance, cache falsifié et seuil de validation modifié sont rejetées. |
| Capacité d’exploration | H-01 est autorisé sur copie privée sous huit écarts ouverts. Les hypothèses restent au statut d’essai. |
| Capacité de construction | Réimplantation latérale **Qualifiée** sur le banc synthétique lié et son contrat. Le remplacement de fiche, les concepts PCB et la matérialisation d’une architecture sur le cartographe restent **À valider**. |
| Couverture de validation | Même gel cartographe, 28 514 paires, 26 905 exclusions AABB et 1 609 mesures dont sept intersections. Aucune erreur OCC ni paire `NOT_RUN` dans ce dénominateur. Les 564 contrôles autonomes hors paires restent `NOT_RUN`. Le criblage et les approximations OEM X650 conservent leur portée nominale. |

Les régressions passent sur le moteur L0 (77 tests), l’isolation (6),
Cables (19), le planificateur (1), L1–L3 (4 suites), L4 (7 suites) et L5
(6 suites). Le banc statique relu deux fois reste équivalent et les scénarios
correctifs A et B sont couverts par les rejeux. Les essais ont utilisé les
binaires scellés des lots inchangés ainsi que la compilation C++17 du
gestionnaire corrigé. [Reçu de régression](verification/v21_fix_c_qualification.json)

**`GO_CONDITIONNEL_V21_CORRECTIF`**. Le périmètre admis couvre le
préflight et l’exploration numérique sous hypothèses de H-01, la
réimplantation qualifiée sur le banc lié et l’exploitation des mesures
nominales du gel cartographe. Une construction automatique sur le
cartographe, la réception finale du montage, GO 3A, GO 3B et les essais
physiques restent hors de cette autorisation. Les sept interférences,
les contacts installés et les preuves de service propres au montage
conditionnent une reprise sur le prototype. [Clôture B.2](#qualification-xlink-v21-b2)

<a id="cartographe-v3-a"></a>

#### Référentiel XLink et graphe électromécanique V3-A — 18 novembre 2026

**`V3_A_GO_CONDITIONNEL`** sur Windows amd64 avec FreeCAD 1.1.3,
OCCT 7.8.1, Cables 0.3.7 et Qt 6.11.2. La couverture admise porte sur
l’inventaire de la référence sans dock et les trois analyses virtuelles
de dépendances F40/F41. [Acceptation structurée](verification/v3/a/acceptance.json)

| Exigence | Composant et contrôle | Résultat |
|---|---|---|
| `V3-A-01` Fermeture, identité et sources | `T-CARTO-V3-A-NATIVE`, réouverture et recalcul sur deux copies, composition indépendante et sept cas natifs | 137 natifs, 3 733 définitions, 2 772 poses et 53 axes. Le transfert conserve les résultats. 142 fichiers sources identiques avant et après. [Reçu](verification/v3/a/native_receipt.json) |
| `V3-A-02` Traçabilité, topologie et autorités | `v3_graph_contract`, migration L2 et contre-épreuves de projection | 71 liaisons, 142 côtés, 53 axes, 56 associations et 21 lignes sans axe motivées. Le manifeste mécanique LF reproduit l’empreinte CRLF historique par conversion des 51 110 fins de ligne. [Réconciliation](verification/v3/a/reconciliation.json) |
| `V3-A-03` Fermeture d’impact | Oracle indépendant et requêtes `MOVE iso`, `RETENTION p72` et `FRAME ttl-reference` sur les deux copies et un banc XLink | Les neuf cas retrouvent tous les nœuds et contrôles attendus. Les dépendances de voisinage incertaines restent incluses pour revue. [Reçu](verification/v3/a/impact.json) |
| `V3-A-04` Refus adversariaux et preuves | Tests V3, L0–L5 et validation T0 | Dix contre-épreuves d’intégration V3 rejetées. Les gardes de repère +3 mm, provenance fournisseur, cache et worker V2.1 ont été rejouées. Le rapprochement L2 historique passe sur la copie scellée CRLF. [Régressions](verification/v3/a/regressions.json) |

Les deux réservations masquées de l’isolateur sont à 98,871 mm côté TTL
et 53,639 mm côté USB des extrémités des axes correspondants. Ces valeurs
décrivent les représentations CAO. L’inventaire conserve les contradictions
sur J2/J3, la déconnexion F40, les NC et les références à confirmer ainsi
que les inconnues sur l’ancrage, le domaine P72/P73 et les gestes d’accès.
[Autorités et écarts](electromechanical_v3/cartographe.json)

À l’entrée de B, la lecture du gel et l’analyse virtuelle de ces trois
opérations sont admises pour instruire les observations discriminantes.
La recherche de poses, la relaxation de contraintes, la génération CAO ou
la réception de variantes exigent des repères d’interface indépendants, des
domaines de modification et des ancrages étayés, ainsi que des critères
d’accès et d’isolation explicites. La conformité du cartographe demeure
**À valider**. Réception physique `NOT_RUN`.
[Entrées exactes et restrictions](verification/v3/a/acceptance.json)

<a id="cartographe-v3-a1"></a>
#### Admission d’essais d’opérateurs V3-A.1 — 18 novembre 2026

**`V3_A1_ENGINE_TEST_ADMISSION_GO`** pour l’admission sur banc numérique
fermé, sur Windows amd64. Le préflight historique V3-B s’était arrêté au
`next_gate` du cartographe avant toute transaction. V3-A.1 résout ce
blocage à la frontière de construction L5 avec un sceau de banc indépendant
et quatre scénarios typés. Le jalon de B.1 est un résultat transactionnel
mesuré après réouverture, avec contrôle électrique, géométrique et T0.
[Reçu V3-A.1](verification/v3/a1/admission.json)

| Exigence | Composant et essai | Résultat et preuve |
|---|---|---|
| `V3-A1-01` Autorité d’exécution et portée | `evaluateAdmissionScope` → `l5_v3_admission_policy` et `l5_v3_admission_entry` | Quatre opérations admises sur le banc scellé. L5 refuse le déplacement d’iso, la réception physique, les effets composites, les reçus utilisés comme demandes et les clés JSON dupliquées. [Contre-épreuves](verification/v3/a1/adversarial.json) |
| `V3-A1-02` Référence et transfert | Rejeu natif FreeCAD et contrôle des copies L5 | Deux documents, huit liens externes et neuf poses sur deux copies. Les originaux du banc conservent leurs empreintes. Les écarts de version, de signature et d’octets, l’absence ou l’altération du reçu natif et les copies inscriptibles ferment l’admission. [Reçu natif](electromechanical_v3/bench_a1/native_receipt.json) |
| `V3-A1-03` Confinement et régression | Scellés A, graphe V3, L2/L4/L5 et gardes Q1/Q2/Q3 | Sources CAO et gel A conservés. Les preuves B.2 restent historiques et les inconnues UART du cartographe restent ouvertes. [Régressions](verification/v3/a1/regressions.json) · [Commandes](verification/v3/a1/REPORT.md) |

Les trois analyses virtuelles de V3-A restent admissibles sur des copies
en lecture seule. L’ouverture d’une expérience CAO sur une copie du cartographe
reste conditionnée à des garanties locales d’ancrage, de repères, de
cheminement et de service. Les autorités de conception, dont J2/J3, le
brochage du lot retenu et la préservation des isolations, des NC et des
protections, relèvent de V3-A.2. Les défauts B.2 et les incertitudes de
service sont conservés. Construction native et réception physique `NOT_RUN`
pour V3-A.1.

<a id="cartographe-v3-b1"></a>
#### Construction XLink V3 B.1 — 19 novembre 2026

Le verdict `V3_B1_ENGINE_GO` est **Qualifié** sur les profils de banc
scellés sous Windows amd64. Les opérateurs `REPOSITION_DEVICE`,
`REROUTE_HARNESS`, `RELOCATE_SUPPORT` et `CREATE_SUPPORT` sont
**Implémentés** dans L5. Le rejeu C4 et deux compositions distinctes
mesurent les effets sauvegardés depuis une copie de réouverture. Le
contrôle soutient les reprises d’appui et de cheminement de
`ORCH-CAO-MASSE-1`. [Reçu d’acceptation B.1](verification/v3/b1/acceptance.json)

| Exigence | Chaîne de vérification | Preuve |
|---|---|---|
| `V3-B1-01` Effet admis et impact fermé | `evaluateAdmissionScope` → moteur V3-A → L5 avant mutation | Autorités, plan, fermeture d’impact et empreintes dans les reçus des deux bancs. |
| `V3-B1-02` Effets conservés après transfert | `v3_mutate` → sauvegarde → `v3_verify` en processus neuf → validation T0 | C4 à +12 mm avec quatre conducteurs et huit contacts, deux poses `App::Link` avec définition partagée, faisceau et deux platines. |
| `V3-B1-03` Détection des écarts | Mesures FreeCAD/OCCT, vérificateur et reprise L5 | Refus d’autorité et d’intégrité, collisions, rayon inférieur au seuil, ancrage flottant et rollback. |
| `V3-B1-04` Préservation des références | Rejeu de lecture seule V3-A, L2/L4/L5, Q1/Q2/Q3 et comparaison SHA | 137 documents, 2 772 poses et 142 fichiers sources conservés. Les sept interférences et les 1 609 paires B.2 conservent leur statut historique. |

La mutation expérimentale du cartographe et la réception physique sont
`NOT_RUN`. L’admission de conception reste `NO_GO` et les domaines de pose
et d’ancrage restent **À valider**. Les deux extensions de connectique
et de topologie rendent `UNSUPPORTED` à l’entrée L5.
[Recette et périmètre](verification/v3/b1/REPORT.md) ·
[Matrice des capacités](verification/v3/b1/capabilities.json)

<a id="cartographe-v3-a2"></a>
#### Preuves d’interfaces et d’ancrages V3-A.2 — 18 novembre 2026

**`V3_A2_EVIDENCE_CONDITIONAL`** pour le prototype sans dock. Le registre
documente huit issues ouvertes et zéro révision physique confirmée.
L’applicabilité au lot, les repères d’accouplement et de sortie,
les appuis porteurs et les gestes restent **À valider**.
[Registre](verification/v3/a2/evidence_register.json) ·
[Fiche de relevés](verification/v3/a2/measurement_requests.md)

| Exigence | Composant et contrôle | Résultat et preuve |
|---|---|---|
| `CAB-CARTO-001` | W40/W41 et interfaces → confrontation des documents et des natifs désignés → `T-CARTO-V3-A2-EVIDENCE` | Divergence TE/déconnexion manuelle conservée. Le PDF JBD LiFePO₄ A.1 explicite J2 pour cette variante. La contradiction J2/J3 de la notice Li-ion candidate et l’identification des lots restent ouvertes. [Registre des huit issues](verification/v3/a2/evidence_register.json) |
| `MEC-INT-001` | Isolateur, guides, porteurs et voisins → réouverture FreeCAD, poses, BRep et gabarits → `T-CARTO-V3-A2-NATIVE` | Mesures du modèle et des témoins GO3B. Les repères des proxies et les axes restent des représentations CAO. [Reçu natif et portée IF-03 à IF-07](verification/v3/a2/cad_interface_measurements.json) |
| `V3-A1-01`, `METH-001` | Dossier par opération → admission L5 et contre-épreuves de provenance et de métrologie | Les trois demandes d’impact A.1 sont admissibles sur copie scellée en lecture seule. Aucun domaine de pose ou de cheminement n’est autorisé pour la mutation cartographe. [Scopes](verification/v3/a2/operation_scopes.json) · [Contrôles](verification/v3/a2/REPORT.md) |

La mesure d’un proxy permet de réfuter une configuration géométrique
dans le périmètre du gabarit utilisé. L’autorité d’un connecteur exige
l’identité de lot et les datums applicables. Les preuves de montage exigent
également l’engagement des fixations, les cas de charge, les volumes balayés
et les rayons documentés. Le B− brut, les NC, les protections et le voisinage
CAN1/F31/F35 restent des contraintes impératives.

Les octets des sources scellées A et A.1 servent à leur rejeu sur la branche,
y compris les éditions DOC-MEC et DOC-ELEC référencées par le graphe A.
Le test sur banc B.1 conserve sa portée propre. Construction cartographe,
candidats B.1, V3-C, V3-D et GO4 sont `NOT_RUN` dans cette campagne.

<a id="cartographe-v3-i"></a>
#### Intégration V3-I — 19 novembre 2026

`V3_INTEGRATION_GO` sur Windows amd64. Le constructeur B.1 et le dossier
A.2 cohabitent sur une fusion à deux parents issue d’A.1. Les reçus scellés
restent rattachés à leur révision d’origine. La jonction conserve les
règles d’empreinte des workers et autorités C4, ainsi que les natifs.
[Reçu d’intégration](verification/v3/i/acceptance.json) ·
[Manifeste Git et empreintes](verification/v3/i/merge_manifest.json).

| Exigence | Contrôle | Résultat |
|---|---|---|
| `V3-A1-01`, `V3-B1-01` à `V3-B1-04` | `T-CARTO-V3-I` → compilation C++17/Qt6, CTest et rejeux scellés B.1 | Trois candidats admis, quatre cas rejetés et quinze contre-épreuves de frontière exécutées. Deux clones locaux reproduisent les octets des trois fermetures de banc. |
| `CAB-CARTO-001`, `MEC-INT-001` | `T-CARTO-V3-I` → intégrité et réouverture indépendante A.2 | Référence et trois témoins GO3B observés en lecture seule. Trois analyses d’impact admises. Huit issues UART ouvertes et zéro révision physique confirmée. |
| `V3-A1-01`, `METH-001` | `T-CARTO-V3-I` → non-escalade et rejeux historiques privés | Le dossier A.2 brut est refusé comme contrat d’entrée. Les six opérations testées à raison d’une occurrence chacune sont refusées avec zéro transaction. L2 réussit sur son témoin CRLF et refuse le manifeste actif LF, qui conserve son empreinte. |

V3-B.2 sur banc et la collecte V3-A.3 peuvent suivre en soutien de
`ORCH-CAO-MASSE-1`. Pour le cartographe, `READ_ONLY_IMPACT` reste la portée
d’observation, la mutation et l’admission de conception restent `DENY`,
et la réception physique `NOT_RUN`. Les 1 609 paires et sept interférences
V2.1 B.2 restent historiques dans cette passe.
[Régressions](verification/v3/i/regressions.json) ·
[Recette](verification/v3/i/REPORT.md) · [Portées](verification/v3/i/scope_matrix.json).

<a id="cartographe-v3-b2"></a>
#### Contre-validation XLink V3 B.2 — 19 novembre 2026

`V3_B2_VALIDATION_GO` est **Qualifié** sur bancs synthétiques scellés sous
Windows amd64. Les sept plans B.1 reproduisent trois admissions et quatre
rejets. Deux nouvelles compositions conservent les poses, seuils et sources
du banc Workholding et explorent des rayons de 5,2 et 5,4 mm.
[Reçu](verification/v3/b2/acceptance.json) · [Recette](verification/v3/b2/REPORT.md).

| Exigence | Contrôle | Résultat |
|---|---|---|
| `V3-B1-01` à `V3-B1-04` | `T-CARTO-V3-B2` → `v3-build`, contre-mesure FreeCAD sur fermeture distincte, rapprochement et T0 | Neuf plans, cinq candidats admissibles, trois mesures rejetées en quarantaine et un rollback sans natif. Les deux variantes et les sept plans ont une preuve T0. |
| `V3-A1-01`, `METH-001` | `T-CARTO-V3-B2` → garde d’agrégation, réouverture, défauts injectés et reprise | Détection des repères et contacts divergents, cache géométrique, collision, rayon et appui. Un rapport contradictoire, une empreinte altérée et l’interruption avant sauvegarde bloquent la publication du natif. |
| `CAB-CARTO-001`, `MEC-INT-001` | `T-CARTO-V3-B2` → L2 historique, projection L4 XLink et Q1–Q3 | L2 vérifie quatre conducteurs et huit contrôles de contact sur le dossier C4 historique. L’adaptateur L4 mesure la paire câble/obstacle et le rayon. Les règles globales de dégagement L4 et l’appui Workholding ont des portées distinctes. Les 1 609 mesures du cartographe V2.1 restent historiques. |

La suite admise est V3-C sur banc scellé. Les résultats soutiennent la
reprise d’appui et de cheminement sous `ORCH-CAO-MASSE-1`. L’autorité
cartographe se décide par occurrence et opération. La réception physique
reste `NOT_RUN`.
[Matrice croisée](verification/v3/b2/cross_validation_matrix.json) ·
[Contre-épreuves](verification/v3/b2/adversarial.json).

<a id="cartographe-v3-c"></a>
#### Convergence paramétrique V3-C — 19 novembre 2026

`V3_C_AUTONOMY_GO` est **Qualifié** sur les deux bancs synthétiques
scellés sous Windows amd64. L3 et L5 génèrent des poses et des parcours
dans les domaines d’autorité, criblent les obstacles observés, construisent
les candidats et les rouvrent pour contre-validation B.2 et validation T0.
[Acceptation](verification/v3/c/acceptance.json) · [Recette](verification/v3/c/REPORT.md).

| Exigence | Contrôle | Résultat |
|---|---|---|
| `V3-B1-01` à `V3-B1-04` | `T-CARTO-V3-C` → génération, admission v2, FreeCAD et B.2 | T1, T2 et T3 évaluent respectivement 30, 30 et 15 propositions. Six candidats par phase sont construits, rouverts et admis par B.2. Les témoins de faisabilité Workholding et C4 sont exécutés séparément. |
| `V3-A1-01`, `METH-001` | `T-CARTO-V3-C` → gel T0, perturbation T2, contre-épreuves T4 | Workholding retient `[79, 44, 8]` mm en T1 et `[79, 41.5, 8]` mm en T2 après resserrement de la boîte. T4 obtient sept refus avant transaction. |

L’essai varie la translation et le parcours. Les rotations et les ancrages
de supportage sont fixés par les domaines scellés. T2 modifie seulement
la boîte de translation. Les données, les binaires et les seuils conservent
leurs empreintes. La preuve soutient la reprise géométrique sous
`ORCH-CAO-MASSE-1`. L’admission cartographe relève des autorités A.3 par
occurrence et opération. La réception physique reste `NOT_RUN`.
[Scénarios et natifs](verification/v3/c/generalization.json) ·
[Régressions](verification/v3/c/regressions.json).

<a id="cartographe-v3-c1"></a>
#### Convergence couplée V3-C.1 — 24 novembre 2026

`V3_C1_COUPLED_ENGINE_GO`, **Qualifié** sur les deux bancs
`SYNTHETIC_BENCH` sous Windows amd64, FreeCAD 1.1.3, OCCT 7.8.1 et
Cables 0.3.7. Le couplage sert la reprise géométrique sous
`ORCH-CAO-MASSE-1`. Le cartographe reste `DENY` et GO4 `NOT_RUN`.
[Acceptation](verification/v3/c1/acceptance.json) ·
[Recette](verification/v3/c1/REPORT.md)

| Phase | Propositions | Construits, rouverts et contre-mesurés | Admis | Longueur retenue | Dégagement du parcours |
|---|---:|---:|---:|---:|---:|
| T0 | 0 | 0 | 0 | Repères et autorités des deux fermetures mesurés | — |
| T1 | 29 | 4 | 3 | 76,529 mm | 1,250 mm |
| T2 | 30 | 6 | 5 | 79,529 mm | 1,250 mm |
| T3 | 30 | 6 | 2 | 88,538 mm | 4,341 mm |

| Exigence | Contrôle | Résultat |
|---|---|---|
| `V3-B1-01` à `V3-B1-04`, `MEC-INT-001` | `T-CARTO-V3-C1` → pose du lien, datum natif, câble Cables, retenue et réouvertures B.1/B.2 | Le port fixe et le port mobile orientent le parcours. L’appui sur Face6 mesure 48 mm², l’engagement du goujon 1,131 mm³ et le rayon analytique minimal 5 mm pour les trois sélections. Le maximum brut des volumes communs comprend l’engagement autorisé du goujon. Les processus constructeur et lecteur indépendant sont distincts. [Mesures](verification/v3/c1/coupling_proofs.json) |
| `V3-A1-01`, `METH-001` | `T-CARTO-V3-C1` → gel, restriction, sensibilité et Pareto | La restriction scellée de x à 104 mm au minimum exclut le gagnant T1 à 102 mm. T2 reconstruit à 105 mm, translate le port et augmente la longueur mesurée de 3 mm. Le front T1 contient un parcours de 76,529 mm et un détour de 79,686 mm avec des dégagements respectifs de 1,250 et 4,450 mm. [Gel](verification/v3/c1/perturbation_freeze.json) · [Sensibilité](verification/v3/c1/sensitivity.json) · [Pareto](verification/v3/c1/pareto.json) |
| `V3-A1-01`, `METH-001` | `T-CARTO-V3-C1` → refus, régression et contrôle tiers | Sept plans refusés avant construction et cinq défauts détectés après réouverture. V3-I, B.1, B.2, C et les suites ciblées L3/L5 repassent. La revue indépendante vérifie les SHA du gel, les dix candidats admis et la restriction T2. [Injections](verification/v3/c1/adversarial.json) · [Régressions](verification/v3/c1/regressions.json) · [Revue](verification/v3/c1/independent_review.json) |

Le deuxième banc ajoute un obstacle latéral et un niveau de parentage
XLink au port mobile. La recherche de parcours est plane, avec translation
bornée et orientation fixe. Les rotations variables et les changements
de connectique ou de topologie restent `UNSUPPORTED`. La restriction T2
entre dans L3/L5 après gel. Son fichier préenregistré était consultable
dans le dépôt, ce qui limite l’aveuglement à la séquence d’exécution.

<a id="cartographe-v3-a3"></a>
#### Autorités opérationnelles du cartographe V3‑A.3 — 19 novembre 2026

Le dossier livré conclut `V3_A3_EVIDENCE_CONDITIONAL` pour le prototype
cartographe sans dock. Il couvre douze couples occurrence–opération sur
six opérations. Le lot reste `LOT_NOT_INSPECTED`, avec huit issues UART
ouvertes, zéro révision montée et zéro ancrage physique confirmé.
L’observation reste `READ_ONLY_IMPACT`. La mutation et l’admission de
conception restent `DENY`. La réception physique est `NOT_RUN`.
[Acceptation A.3](verification/v3/a3/acceptance.json) ·
[Matrice par occurrence](verification/v3/a3/operation_admission.json)

| Exigence | Contrôle et résultat | Preuve |
|---|---|---|
| `CAB-CARTO-001` | Rapprochement W40/W41, JBD, Waveshare, Holybro et séparateur. La notice LiFePO₄ A.1 éclaire J2 et reste écartée de la cible Li-ion. Le choix TE ou manuel, J2/J3 Li-ion et l’embase W41/B restent **À valider**. | [Registre](verification/v3/a3/evidence_register.json) |
| `MEC-INT-001` | Réouverture XLink et reprise IF-03 à IF-07 sur quatre copies. Les supports H03 ont un jeu de 0,300 mm au module et une intersection P72 de 109,734 mm³. Les faces des porteurs et l’accès aux interfaces restent **À valider**. | [Observations](verification/v3/a3/native_observations.json) |
| `V3-A1-01`, `V3-B1-01` | L5 refuse deux dossiers soumis comme demandes, les douze mutations et dix-neuf injections. Les trois témoins de lecture et les bancs A.1/B.1 maintiennent leur portée. | [Régressions](verification/v3/a3/regressions.json) · [Injections](verification/v3/a3/adversarial.json) |

L’action minimale porte sur l’identité des pièces et leurs cavités,
les datums de l’appui P64/P66, les interfaces TTL/USB et le geste de
retrait sur batterie inerte. Un relevé signé et rattaché au lot doit
établir une autorité et un domaine propres au couple occurrence et
opération avant une nouvelle décision. Le résultat numérique soutient
ORCH-CAO-MASSE-1 et laisse les essais sur banc V3 indépendants.
[Fiche opérateur](verification/v3/a3/measurements_required.md)

<a id="cartographe-v3-d"></a>
#### Admission du démonstrateur cartographe V3-D — 19 novembre 2026

`V3_D_CARTO_NOT_ADMITTED` · `PREPARATION_ONLY`. La jonction vérifie le
reçu V3-C sur banc et les décisions A.3 par occurrence. L5 admet trois
analyses en lecture seule et refuse les douze demandes de mutation. Les
huit issues UART et l’absence de révision ou d’ancrage confirmés maintiennent
le montage **À valider**. [Admission](verification/v3/d/admission.json) ·
[Acceptation](verification/v3/d/acceptance.json).

| Exigence | Contrôle | Résultat |
|---|---|---|
| `V3-A1-01`, `METH-001` | `T-CARTO-V3-D` → jonction, revue des SHA et rejeu de la porte | Quatorze refus de portée, dix-neuf injections bloquées et zéro transaction. Les verdicts C et A.3 gardent leur portée. |
| `CAB-CARTO-001`, `MEC-INT-001` | `T-CARTO-V3-D` → fermetures V3-A/GO3B, gabarits de service et paires héritées | Les quatre fermetures reproduisent A.2 en lecture seule. Les sept interférences V2.1 concordent. Le criblage hypothétique retrouve neuf gabarits TTL en conflit avec PDB, cinq gabarits USB-B de 50 mm en conflit avec P72 et douze parcours temporaires avec interférence. Soixante paires GO3B restent `NOT_RUN`. |

La reprise sous `ORCH-CAO-MASSE-1` dépend des relevés hors tension sur
les lots, les datums, les appuis et le geste batterie. Les valeurs de pose
admissibles et la réception physique restent respectivement inconnues et
`NOT_RUN`. Le budget de création native cartographe est nul dans cette
passe. [Diagnostic](verification/v3/d/independent_validation.json) ·
[Relevés et critères de reprise](verification/v3/d/measurement_actions.md).

<a id="cartographe-v3-a4"></a>
#### Autorités du lot cartographe V3-A.4 — 24 novembre 2026

`V3_A4_EVIDENCE_CONDITIONAL`. L'import préliminaire C++17/Qt6 est
**Implémenté**. Les huit issues UART restent ouvertes, les douze couples
occurrence–opération ont la décision `DENY` et leurs domaines restent
indéterminés. Aucun lot installé, aucune révision physique et aucun
ancrage ne sont confirmés. La réception physique GO4 reste `NOT_RUN`.
[Acceptation](verification/v3/a4/acceptance.json) ·
[Matrice](verification/v3/a4/operation_admission.json)

| Exigence | Contrôle | Résultat |
|---|---|---|
| `V3-A1-01`, `METH-001` | `T-CARTO-V3-A4-IMPORT` → identité/révision, preuves brutes, repères, unités et incertitudes | 41 cas d'import réussis et un refus `MUTATION_DOMAIN_DENIED` avant construction, avec conservation de la fermeture de 142 sources. Le contenu des photos et la chaîne de revue authentifiée restent **À valider**. |
| `CAB-CARTO-001`, `MEC-INT-001` | `T-CARTO-V3-A4-REGRESSION` → A.1, A.2, A.3 et D sur Windows amd64/FreeCAD 1.1.3 | Quatre fermetures rouvertes en lecture seule, sept paires historiques concordantes, douze cas Q2 réussis, trois analyses admises et 33 refus d'admission rejoués. Les gabarits de service restent hypothétiques. |

Le premier dossier à instruire sous `ORCH-CAO-MASSE-1` concerne
`CREATE_SUPPORT(iso)` pour `anchor:iso-carrier`. La quantité d'information
suffisante pour décider dépend d'un lot identifié, d'un appui et de ses
fixations sur P64 ou P66, des volumes de service et du geste batterie. Les
observations brutes et une revue habilitée sont requises avant de borner
le domaine de l'opération. Les autorisations restent propres à l'occurrence,
à l'opération et à la révision du lot. [Collecte opérateur](verification/v3/a4/measurement_packet.md) ·
[Préflight](verification/v3/a4/create_support_iso_preflight.json) ·
[Rejeu](verification/v3/a4/REPORT.md)

<a id="cartographe-v3-int1"></a>
#### Intégration V3-INT.1 — 25 novembre 2026

La fusion `b00d371` réunit C.1 et A.4 à partir de la référence V3-D.
Le verdict calculé `V3_INT1_GO` qualifie la jonction sur banc synthétique
Windows amd64.
Les deux cas supplémentaires de l’import et les deux fautes de fermeture
privée ont été figés dans `b99cd86`, avec les mêmes sources C++ compilées.
Le rejeu de cette base est borné aux budgets C.1 existants et aux
régressions A.4. Il fournit les contrôles nécessaires à l’étude des
cheminements et de l’ancrage prévues par `ORCH-CAO-MASSE-1`.
[Acceptation calculée](verification/v3/int1/acceptance.json) ·
[Provenance](verification/v3/int1/merge_manifest.json)

| Exigence | Contrôle | Résultat |
|---|---|---|
| `V3-B1-01`, `CAB-CARTO-001` | `T-CARTO-V3-INT1` · constructions T1/T2/T3, réouverture B.2 et validateur T0 neuf ; restriction T2, sensibilité et Pareto | 29/30/30 propositions, 4/6/6 constructions et 3/5/2 candidates qualifiées. Revue et validation T0 des dix candidates sur Windows amd64, FreeCAD 1.1.3, OCCT 7.8.1 et Cables 0.3.7. La restriction T2 est préenregistrée et visible dans Git. |
| `V3-A1-01`, `METH-001` | `T-CARTO-V3-INT1` · import A.4, refus L5 et invariance des fermetures | 43 cas A.4 vérifiés, 17 contrôles B.1, 7 refus de plans C.1 et 5 fautes natives détectées. Le paquet vide rend `NOT_RUN`, l’exemple est refusé et zéro transaction cartographe est publiée. |
| `CAB-CARTO-001`, `MEC-INT-001` | `T-CARTO-V3-INT1` · A.2/A.3/D et Q2 | Quatre fermetures rouvertes, sept paires D et douze cas Q2 concordants. Les 24 sondes et 12 routes reproduisent un criblage `INCONCLUSIVE`. |

Le CTest L3 large rend 8 avec les deux écarts historiques de `l2_reconcile`
et `technical_research_engine`. La conversion CRLF vers LF des entrées
scellées explique les divergences d’empreinte du checkout neuf. Les 7 tests
L2 et 24 tests Research réussissent avec les octets de référence et les
binaires intégrés. Les résultats initiaux et les reprises sont conservés.
Le CTest L5 initial rend 8 avec `l5_cli` en échec. Les deux assertions
concernent la même tentative `upper`, observée `ERROR` en nominal et
`PASS` à la reprise. Le CTest `l5_cli` exécuté seul passe en 277,09 s. La
cause exacte de l'erreur initiale demeure **À valider**. Les campagnes
natives se chevauchaient lors du premier essai.
[Commandes, codes et empreintes](verification/v3/int1/regressions.json) ·
[Preuves des refus](verification/v3/int1/adversarial.json)

A.4 conserve `V3_A4_EVIDENCE_CONDITIONAL`. Les huit issues restent ouvertes,
zéro lot a été inspecté, zéro couple occurrence–opération est admis et la
réception physique reste `NOT_RUN`. Le cartographe garde `DENY` pour la
mutation. La suite C.2/A.5 est soumise au verdict INT.1 et au
[contrat de passage](verification/v3/int1/next_stage_contract.md).

<a id="cartographe-v3-c2"></a>
#### Convergence multi-faisceaux V3-C.2 — 25 novembre 2026

`V3_C2_MULTIHARNESS_ENGINE_GO`. Le moteur est **Qualifié** sur les deux
bancs `SYNTHETIC_BENCH` sous Windows amd64, FreeCAD 1.1.3, OCCT 7.8.1
et Cables 0.3.7. Le gel `772732c` conserve les profils et les six natifs
XLink. Deux câbles distincts et leurs quatre ports sont mesurés en B.2
sur les huit candidates, puis chaque candidate repasse T0. Les profils
du cartographe restent hors de ce périmètre.
[Acceptation](verification/v3/c2/acceptance.json) ·
[Fermetures et domaines](verification/v3/c2/domain_contract.json)

| Phase | Propositions | Constructions | Candidates qualifiées | Appui retenu | Longueur totale | Garde entre câbles |
| --- | ---: | ---: | ---: | --- | ---: | ---: |
| T1, banc primaire | 79 | 7 | 3 | `plate-b` | 168,00 mm | 3,96 mm |
| T2, restriction externe | 79 | 7 | 3 | `plate` | 168,00 mm | 3,96 mm |
| T3, second banc XLink | 79 | 7 | 2 | `plate-b` | 169,93 mm | 6,97 mm |

T1 a admis les deux options d’appui. Le front conserve un compromis de
longueur et de garde. Après le gel et la finalisation de T1, l’évaluateur
a retiré `plate-b` du domaine T2 dans un fichier empreinté. Le moteur a
construit, rouvert et classé une variante distincte avec `plate`. Les
trois résultats retenus mesurent 0 mm³ d’interférence interdite. Les
engagements autorisés et contacts attendus sont contrôlés individuellement.
[Perturbation et résultats](verification/v3/c2/generalization.json) ·
[Contacts et interférences](verification/v3/c2/interference_classification.json) ·
[Classement](verification/v3/c2/pareto.json)

Les 9 refus de contrat et 11 injections natives vérifient notamment la
continuité, la terminaison mobile, les collisions et le rollback complet.
C.1 reproduit 3/5/2 candidates qualifiées. B.1, B.2, C, A.4 et les gardes
L5 applicables passent. Le budget de temps borne l’admission. Une
transaction atomique déjà engagée peut se terminer après l’échéance et
reste exclue du classement. Le cartographe conserve `DENY`, avec
réception physique `NOT_RUN`.
[Rejeu et refus](verification/v3/c2/adversarial.json) ·
[Régressions](verification/v3/c2/regressions.json)

<a id="cartographe-v3-a5"></a>
#### Revue et admission V3-A.5 — 25 novembre 2026

`V3_A5_AUTHORITY_PIPELINE_GO`. Le circuit de revue authentifiée et de
préadmission est **Qualifié** pour le témoin `TEST_ONLY` sous Windows
amd64, Qt 6.11.2 et OpenSSL 3.6.4. Les 50 cas donnent 48 refus et deux
admissions signées sur banc, dont une seule lors de deux demandes concurrentes.
Les gardes vérifient les signatures, la séparation de la confiance, les
empreintes, la période de validité, la révocation, la consommation unique,
les bornes de pose et la fermeture XLink. Le build sans OpenSSL rend
`REVIEW_NOT_CONFIGURED`. A.4 passe ses 43 cas et ses imports de référence.
[Acceptation](verification/v3/a5/acceptance.json) · [Rejeux](verification/v3/a5/regressions.json)

Le CTest complet rend 8 avec 11 tests réussis, dont `l5_cli`. L'empreinte
de `cartographe_action3_interconnexions.json` change avec la normalisation
LF du checkout de `l2_reconcile`. Les sept tests L2 réussissent sur les
octets de référence. Les 137 natifs du cartographe concordent avec le gel
historique. Pour le précontrôle d'une future copie, les trois auxiliaires
du gel V3-A requièrent les octets scellés documentés dans INT.1.

`V3_A5_EVIDENCE_CONDITIONAL`. Huit sujets restent à instruire, avec zéro
lot inspecté, zéro autorisation cartographe et réception `NOT_RUN`.
`CREATE_SUPPORT` sur `anchor:iso-carrier` reste `DENY` tant que le lot,
l'appui, la visserie, le geste de service et la revue habilitée ne sont
pas établis. La collecte précède la qualification matérielle.
[Matrice de collecte](verification/v3/a5/lot_and_measurement_matrix.json) ·
[Disponibilité du support](verification/v3/a5/create_support_iso_readiness.json)

### 12.2 Carte avionique CA01 — ébauche schématique, 20 septembre 2026

Résultat historique V0.1 ; la révision courante est décrite au §12.3.

Périmètre : schéma éditable de la carte commune du cartographe, décrit dans
[DOC-ELEC §4.2](architecture/ARCHITECTURE_ELECTRIQUE_RESEAUX.md#42-cahier-des-charges-de-la-carte-avionique-commune-ca01).
L'ébauche est **Implémentée** ; le matériel reste **Planifié / À valider**.
Le projet KiCad comporte une racine, cinq feuilles et une bibliothèque locale.
Le PCB est un canevas vide, sans contour ni routage.

Environnement : Windows `amd64`, KiCad 10.0.6, pont MCP local au commit
`ac716d1a8bfad325b4aa93a398222645b3f78fd7`, backend fichier.
Les composants et connexions ont été créés par appels MCP ; la normalisation
de bibliothèque, les exclusions de fabrication et la recette de vérification
utilisent aussi des corrections ciblées de fichiers et le CLI KiCad.

Résultats statiques :

- 6/6 fichiers relus par KiCad ; 46 symboles et 46 nets exportés.
- 14/14 contrôles de connexion conformes : contacts PM doublés, I²C,
  séparation des nets positifs vol/auxiliaires, cavalier Airy ouvert,
  rappel du buffer, chaîne transistor/Basler, bootstrap/VCC des bucks et
  résistances UART DNP.
- Revue visuelle des six feuilles ; cette lecture ne constitue pas une revue
  de routage. Le détecteur automatique de chevauchements ne suffit pas à
  valider la lisibilité des champs, corrigés après lecture des rendus.
- ERC **non conforme**, 3 erreurs et 0 avertissement : absence de source de
  puissance déclarée sur `VIN_PAYLOAD_PROT`, `GND` et `3V3_SYNC`.
  Aucun effacement ou waiver de ces trois erreurs. Les vérifications désactivées
  par les réglages KiCad sont consignées dans `erc.json` ; l'ERC n'est pas
  exhaustif et ne valide ni le dimensionnement ni l'assemblage.

La revue indépendante a couvert DOC-ELEC §4.2 et les feuilles énergie, radio
et synchronisation. Elle a confirmé le retour Basler commuté, l'absence de
pont entre rails positifs et le maintien des interfaces inconnues ouvertes.
Son point P2 a été corrigé : R401/R402 sont DNP avant validation UART.
R503, 100 kΩ candidat, fixe l'entrée du buffer au repos. La revue ne couvre
pas le calcul détaillé des convertisseurs, les empreintes ou la thermique.

Preuves : [contrôle statique et empreintes](../hardware/electronique/cartographe/carte_avionique/verification/history/20260920/controle_statique.json),
[rapport ERC](../hardware/electronique/cartographe/carte_avionique/verification/history/20260920/erc.json),
[contrôles MCP](../hardware/electronique/cartographe/carte_avionique/verification/history/20260920/mcp_controles.json)
et [recette exécutable](../hardware/electronique/cartographe/carte_avionique/verification/verify_ca01.ps1).
La recette réexporte la netlist et l'ERC et vérifie les invariants ; un succès
des invariants n'implique pas le succès ERC. Conclusion : **préliminaire**,
dossier de fabrication **non conforme / incomplet**, aucune qualification
matérielle revendiquée.

Campagne de recette à réaliser, traçable à `CARTE-001..012` dans DOC-ELEC.
Avant chaque banc, figer les références, les seuils, les charges et le nombre
de répétitions ; aucun seuil ne sera choisi après observation du résultat.
Utiliser une alimentation limitée, sans hélices, avec arrêt sur surtension,
surcourant, échauffement hors limites ou reset du domaine vol.

| Test / exigence | Protocole et critère | État au 2 octobre 2026 |
|---|---|---|
| `T-CA01-01 / CARTE-001` | revue schéma/netlist puis inspection du faisceau : aucun chemin propulsion ; mesure globale identifiée | netlist partielle vérifiée ; faisceau et mesure globale **À valider** |
| `T-CA01-02 / CARTE-002` | défauts limités sur chaque départ charge utile : aucun reset Pixhawk ; si le 5 V radio CA01 est perdu, perte RC détectée et repli PX4 sûr | non exécuté ; critère cible V0.5 |
| `T-CA01-03 / CARTE-003` | rampes 6S, inversion contrôlée, appel et transitoires selon enveloppe approuvée : protections et seuils respectés | protections **À valider** ; protocole T-CA01-E02/E04 et TH03 défini §12.7.11, critères non approuvés, banc non exécuté |
| `T-CA01-04 / CARTE-004` | charges statiques/dynamiques 12 V calcul vers XT30 Holybro, puis Orin NX/USB/SSD : stabilité, polarité, limite porteuse et thermique respectées | buck/routage candidat **Implémenté** §12.7.13 ; T-CA01-E03/E06 et TH01/02 planifiés, boucle/Ceff/charges/banc **À valider** |
| `T-CA01-05 / CARTE-005` | source 12 V capable d'au moins 2 A, démarrages et acquisition Airy à chaud : aucun reset | routage candidat **Implémenté** ; T-CA01-E03/E06 et TH01/02 planifiés ; démarrage Airy réel non exécuté |
| `T-CA01-06 / CARTE-006` | 5 V local CA01, charges radio/auxiliaires, défauts et séquences : budgets fermés, plages respectées, aucun retour vers POWER1/2 | 5 V/routage candidat **Implémenté** ; T-CA01-E03/E04/E05/E06 planifiés ; budgets/séquences/protections/banc **À valider** |
| `T-CA01-07 / CARTE-007` | révisions PM/porteuse et faisceau identifiés ; BEC1→POWER1, BEC2→POWER2, CAN1 distinct ; budgets ≤3 A chacun, bascule et calibration PX4 conformes | schéma V0.3 historique ; matériel V0.5 non exécuté |
| `T-CA01-08 / CARTE-008` | mesurer UART et état hors tension avant de monter R401/R402 ; essais RC/QGC avec Jetson arrêté, puis `T-RF-01..06` | DNP vérifié ; banc et RF non exécutés |
| `T-CA01-09 / CARTE-009`, `ELEC-TIM-001` | qualifier CA01 : W36 GNSS→CA01 sans retour +5 V, W23/W24 PPS/GPRMC tamponnés vers Airy/Orin, référenceIO J509, adaptation AUX Pixhawk vers opto Basler Line1, retour réel ExposureActive Line2 vers FMU_CAP1, niveaux et isolement ; suivre `T-AIRY-SYNC-01` (§12.8) | schéma physique temps/trigger/capture candidat Implémenté ; sortiesR530–R533DNP, niveauxOEM/référenceIO et banc À valider ; recette§12.7.2 |
| `T-CA01-10 / CARTE-010` | CAO avec porteuse Holybro/Orin NX/PM08/CA01 et vrais connecteurs puis montage SA03/SA04 : accès, fixations, isolation et thermique conformes | contrôles CAO candidats §12.7.5/9, placement électrique repris §12.7.13 ; montage SA03/thermique TH02 non exécutés |
| `T-CA01-11 / CARTE-011` | charges simultanées, thermique, bruit et CEM puis progression moteurs autorisée : marges et capteurs conformes | T-CA01-TH01..03 et CEM01..04 définis §12.7.11 ; critères/marges/référentiel **À valider**, aucun essai matériel |
| `T-CA01-12 / CARTE-012` | sources, BOM, empreintes, netlist, ERC puis DRC : aucune valeur ouverte et revue complète avant fabrication | V0.5-pre : 230 invariants/ERC0 ; routage complet §12.7.13, DRC0/parité0/connexion0 selon configuration ;44 MPN/protections/DFM/process ouverts, **non conforme pour fabrication** |

Aucun essai de charge, thermique, RF, synchronisation sur capteurs,
simulation électrique ou vol réalisé ; matériel non assemblé, protections
et qualification ouvertes. Le DRC du PCB intégralement routé est désormais
exécuté (§12.7.13) ; il ne compense pas l'absence de ces essais matériels.


### 12.3 CA01 V0.2 et câblage global, 21 septembre 2026

Le PM02D est désormais externe, sur un support mécanique séparé. Son câble
POWER1 vers Pixhawk évite CA01. J101 reçoit uniquement le départ radio à
deux contacts ; J102 et les nets PM_SCL/PM_SDA ont été retirés via MCP.
La dérivation et sa protection externe restent **À valider**.

Contrôles Windows amd64 / KiCad 10.0.6 : 45 symboles et 44 nets ; 14/14
invariants conformes. Les contrôles de l'ancien transit sont remplacés par
l'absence de J102/I²C PM et l'entrée radio dédiée. ERC toujours **non conforme** :
3 erreurs (VIN_PAYLOAD_PROT, GND, 3V3_SYNC sans source de puissance déclarée)
et 0 avertissement. Relecture KiCad et inspection des deux feuilles modifiées.

Contrôle du registre : 22 groupes de modules, 30 liaisons uniques, aucun endpoint inconnu et 21 broches CA01 concordantes avec la netlist. La copie Mermaid dans DOC-ELEC correspond au fichier source ; preuve [câblage global](../hardware/electronique/cartographe/verification/cablage_global_20260921.json).

Le [schéma global](../hardware/electronique/cartographe/cablage_global.mmd)
et le [registre E/S](../hardware/electronique/cartographe/cablage_global.json)
décrivent 30 liaisons W01..W30. Ils couvrent propulsion, vol, charge utile,
données, synchronisation, RF et corrections RTCM, avec les ports et références
inconnus explicitement laissés ouverts. Aucun faisceau n'est prêt à fabriquer.

| Exigence | Contrôle de cette révision | Résultat / limite |
|---|---|---|
| CARTE-001/002/007 | PM direct hors carte, absence de transit I²C, entrée radio distincte | netlist conforme ; câble externe et sélectivité non testés |
| CARTE-008/009 | invariants UART DNP et trigger conservés | conforme statiquement ; interfaces physiques non qualifiées |
| CARTE-010 | support PM externe décrit dans DOC-MEC | **Planifié**, CAO inchangée |
| CARTE-012 | cohérence schéma, registre, manifeste et revue des frontières | ébauche contrôlée ; dimensionnement/fabrication incomplets |
| CAB-CARTO-001 | identité des modules et E/S de W01..W30 | revue documentaire ; continuité/isolement et brochages réels non testés |

Preuves V0.2 archivées : [contrôle statique](../hardware/electronique/cartographe/carte_avionique/verification/history/20260921/controle_statique.json),
[ERC](../hardware/electronique/cartographe/carte_avionique/verification/history/20260921/erc.json)
et [contrôles MCP V0.2](../hardware/electronique/cartographe/carte_avionique/verification/mcp_controles_20260921.json).
Les preuves V0.1 du §12.2 sont archivées dans `verification/history/20260920`.
La revue indépendante de cette évolution couvre les frontières PM/CA01,
le registre des interfaces et les critères de clôture ; les calculs de
conversion, protections, empreintes et thermique restent hors périmètre.

Les trois étapes « schéma terminé », « PCB fabricable » et « matériel qualifié »
sont distinguées dans DOC-ELEC §4.2.7. T-CA01-07 porte désormais sur le câble
POWER1 direct et la dérivation externe, pas sur un transit CA01.
Aucun essai matériel, FreeCAD ou DRC réalisé : support non modélisé, PCB vide,
composants non dimensionnés et faisceau non réalisé. Les douze recettes
T-CA01 restent ouvertes. Conclusion : **préliminaire**.

### 12.4 Audit du dimensionnement courant, 22 septembre 2026

Périmètre : recalcul documentaire sous Windows amd64, sans matériel, associé
à `CAB-CARTO-001` et au dimensionnement amont de `ELEC-PWR-001`.
Le calcul reproduit les valeurs historiques à 10⁻⁹ A près : 51,823 A au point
de référence, 58,105 A à puissance constante sous 19,8 V, 65,054 A dans le
scénario extrapolé à 25,2 V, puis 81,318 A avec marge, arrondis à 85 A.
L'arithmétique est **conforme** ; le besoin continu reste **À valider**.

[Preuve, formules de recalcul et empreinte de l'entrée](../hardware/electronique/cartographe/verification/audit_courant_20260922.json).
La relecture indépendante confirme l'arithmétique et distingue les hypothèses
des deux scénarios de tension. DOC-ELEC §5.1 corrige l'interprétation comme
besoin continu. Le bilan historique et les preuves KiCad du 21 septembre
restent conservés, sans extension de leur portée.

Le budget de masse, le courant avec hélices réelles, la durée des pointes,
la température et le rendement effectif ne sont pas mesurés. Aucun essai
matériel ni nouveau contrôle KiCad : le schéma ne change pas dans cet audit.
Conclusion du dimensionnement : **préliminaire**, aucune qualification PM02D.

### 12.5 PM02D en tête et câblage V0.3, 22 septembre 2026

Décision de conception : conserver le PM02D complet et son BEC, remplacer son
faisceau de puissance et le placer entre batterie et toute la distribution.
POWER1 reste direct vers Pixhawk ; CA01 conserve son entrée radio J101.
L'option support sur cassette est **Planifiée**, sans modification CAO exécutée.

La révision V0.3 met à jour le registre et les annotations : 21 groupes de
modules, 29 liaisons actives W01..W29 ; MEAS/W30 retirés, fonction portée par
PM02D/W06. W01 = BAT→PM IN et W05 = PM OUT→DIST. La connectivité de CA01
reste celle de V0.2 ; seules les annotations changent. Le contrôle des
connexions et ERC est réexécuté ; les résultats sont consignés dans les preuves
ci-dessous. Résultat : 45 symboles, 44 nets, 14/14 invariants conformes ;
21 broches de registre concordantes, aucun endpoint inconnu et diagramme
identique au registre. Les deux feuilles annotées sont valides à la relecture
MCP/KiCad. ERC **non conforme**, 3 erreurs de puissance existantes et 0
avertissement. Les résultats historiques des §12.3–12.4 restent datés.
La revue indépendante a fait corriger deux annotations ambiguës ou obsolètes ;
elle ne constitue pas une qualification électrique.

| Exigence / test | Critère et périmètre | État |
|---|---|---|
| CAB-CARTO-001 / contrôle documentaire | BAT→PM→DIST, aucun départ contournant PM, pas de MEAS/W30 actif, concordance registre/diagramme/CA01 | résultat dans la preuve de câblage |
| CARTE-001/007 / T-CA01-01/07 | PM externe, POWER1 direct, BEC 5,2 V partagé ≤3 A, aucune propulsion sur CA01 | invariants statiques contrôlés ; qualification physique ouverte |
| CARTE-007 / T-PM-01 | comparer courant/énergie PM avec référence batterie : charge BEC seule, charge OUT seule, puis charges simultanées ; précision/tolérance à figer avant essai | **Planifié** |
| ELEC-PWR-001 / T-PM-02 | profil courant continu/pointes/durée et thermique du PM et du faisceau adapté conformes aux limites fabricant et marges définies ; charge utile en défaut sans perte du vol | **Planifié** |
| CARTE-010/011 / T-PM-03 | support fixe ou cassette, isolation, vibrations, traction, accès et coupure de stockage ; puissance et POWER1 détachables sans effort parasite | **Planifié** |
| T-PM-04 / modèle énergie mission | masse/inerties CAO, courbes propulsion hélice réelle et consommation avionique identifiées ; comparaison du modèle aux mesures avec critères fixés avant campagne | **Planifié** |

Gazebo/PX4 sert à analyser les sollicitations et les réactions aux états
batterie simulés. Une charge batterie paramétrée n'est pas une preuve du
courant réel. Les limites PCB de 60 A continus et 100 A moins de 60 s restent
à confronter au profil mesuré ; aucune simulation standard ne qualifie les
câbles, soudures, connecteurs ou la thermique. La progression du §2 demeure.

Preuves : [câblage V0.3](../hardware/electronique/cartographe/verification/cablage_global_20260922.json),
[contrôle statique CA01](../hardware/electronique/cartographe/carte_avionique/verification/controle_statique.json),
[ERC](../hardware/electronique/cartographe/carte_avionique/verification/erc.json)
et [lecture MCP](../hardware/electronique/cartographe/carte_avionique/verification/mcp_controles_20260922.json).
Les trois sorties statiques V0.2 précédentes sont conservées dans
`carte_avionique/verification/history/20260921`. Aucun essai matériel ni
simulation nouvelle, support non modélisé, PCB toujours non fabricable :
conclusion du dimensionnement **préliminaire**.

### 12.6 Historique du câblage PM08-CAN V0.4, 22 septembre 2026

Le câblage global retient PM08-CAN fixe au châssis : BEC1 alimente POWER1,
périphériques vol et radio ; BEC2 alimente les auxiliaires et la synchronisation
via AUX_IN à créer. Les deux budgets sont 5,3 V/3 A chacun, non fermés.
POWER2 Pixhawk est non raccordé et les BEC ne sont pas mis en parallèle.
Le monitoring emprunte W31/DroneCAN CAN1 ; W06 transporte uniquement l'énergie.
W30 reste retiré. W32 ajoute le départ BEC2 vers CA01.

Le contrôle documentaire Windows amd64 porte sur 21 groupes, 31 liaisons
actives, leurs endpoints/identifiants, le brochage séparant puissance et CAN,
les limites BEC, l'absence de départ contournant PM et le statut de migration.
Il compare 17 broches CA01 conservées à la netlist V0.3. Les interfaces
W07/W18/W26 et W32 nécessitent migration ou validation ; elles ne sont pas
déclarées raccordables sur le schéma V0.3.

[Preuve V0.4](../hardware/electronique/cartographe/verification/cablage_global_v04_20260922.json) ;
[recette](../hardware/electronique/cartographe/verification/verify_cablage.ps1).
L'ancienne définition V0.3 est conservée dans
`hardware/electronique/cartographe/verification/history/v03`.

| Exigence / test | Évolution à vérifier | État |
|---|---|---|
| CAB-CARTO-001 | BAT→PM→DIST, BEC1/BEC2 séparés et W31 distinct de POWER1 | contrôle documentaire ; aucun faisceau assemblé |
| CARTE-006 / T-CA01-06 | AUX_IN, protection/filtrage, retrait U301, compatibilité5,3V et régulateur3,3V | **Planifié** |
| CARTE-007 / T-CA01-07, T-PM-01 | calibration PM08 pour OUT, BEC1 et BEC2 ; CAN-H/L jamais sur POWER1 SCL/SDA | brochage documentaire revu ; banc **Planifié** |
| CARTE-002/011 / T-PM-02 | charges simultanées et défaut BEC2 sans reset Pixhawk/radio ; absence de réalimentation | **Planifié** |
| T-PM-03 | support PM08 fixe, câbles et températures ; masse installée | **Planifié**, CAO non migrée |
| T-PM-04 | modèle de consommation et perte DroneCAN batterie dans PX4 | **Planifié**, aucun paramètre réel modifié |

**Le schéma interne KiCad V0.3 n'a pas été migré.** Il contient encore PM02D
dans ses annotations et le buck5V_AUX. Son dernier contrôle (14 invariants,
3 erreurs ERC ouvertes) reste une preuve historique, pas une validation du
raccordement PM08. Aucun nouvel ERC/DRC, essai matériel ou simulation exécuté :
la tâche porte sur le câblage cible, la migration de CA01 reste à réaliser.
Conclusion : **préliminaire**, pas de faisceau ni de carte fabricables.

### 12.7 Cible alimentation et avionique V0.5, 24 septembre 2026

La V0.4 du §12.6 et sa preuve datée restent historiques. La cible V0.5,
**Planifiée / À valider**, associe la Holybro Pixhawk Jetson Baseboard, un
module Pixhawk 6X, un Jetson Orin NX 16 Go et le PM08-CAN. BEC1 et BEC2 du PM
alimenteraient respectivement POWER1 et POWER2 du Pixhawk ; la mesure batterie
passerait par CAN1, séparément des entrées d'alimentation. CA01 retrouverait
un 5 V local protégé pour la radio, ses auxiliaires et sa synchronisation. Un rail 12 V
régulé est candidat pour l'entrée XT30 du Jetson sur la baseboard. Batterie,
PM08-CAN et baseboard restent des éléments communs : deux BEC ne démontrent
pas une redondance du système complet.

Avant le banc, identifier références, révisions et numéros de série du PM,
de la baseboard, du Pixhawk, du Jetson et des câbles ; obtenir le schéma du
faisceau et fixer sections, protections et terminaisons CAN. La fourniture
d'un faisceau séparant POWER1, POWER2 et CAN1 n'est pas établie. Critères
chiffrés, marges et limites d'injection de défaut restent **À valider**.
Chaque essai conservera configuration, empreintes, mesures, traces PX4/CAN,
oscillogrammes, températures et anomalies dans une preuve technique liée à la
révision réellement essayée. Le [contrôle documentaire V0.5](../hardware/electronique/cartographe/verification/cablage_global_v05_20260924.json)
vérifie le registre, le diagramme et la netlist CA01 V0.5-pre, sans valider le
faisceau ni le matériel. Aucune preuve V0.4 ne vaut résultat V0.5.

| Exigence / essai V0.5 | Protocole et critère de sortie à approuver | État |
|---|---|---|
| CAB-CARTO-001, CARTE-007 / T-PM-V05-01 | Continuité et isolement hors tension, contact par contact : BEC1 +5,3 V/GND vers POWER1, BEC2 +5,3 V/GND vers POWER2, CAN-H/L et masse vers CAN1 ; aucun CAN sur SCL/SDA des POWER, aucune injection sur le +5 V sortie de CAN1, aucun pont externe entre BEC. Vérifier orientation, détrompage, sertissages et terminaisons sur les révisions réelles. | **Planifié / À valider** ; faisceau non vérifié |
| CARTE-002/007 / T-PM-V05-02 | Source limitée, BEC1 seul, BEC2 seul puis simultanés ; couper chaque BEC à tour de rôle et mesurer tensions, transitoires, états PX4 et resets. Critère : Pixhawk maintenu dans l'enveloppe approuvée après perte d'un seul BEC, sans réalimentation de la sortie perdue. Mesurer aussi disponibilité du GNSS et des capteurs de vol essentiels ; toute perte doit être détectée et conduire au repli PX4 défini. La radio doit rester alimentée depuis CA01 lors d'une coupure isolée de BEC1 ou BEC2 ; les défauts communs sont traités séparément. | **Planifié / À valider** ; bascule et radio non essayées |
| CARTE-006, ELEC-PWR-001 / T-PM-V05-03 | CA01 avec 5 V local protégé : charges auxiliaires et synchronisation, séquences de marche/arrêt, court-circuit et défaut du convertisseur sous limites approuvées. Critère : rails 5 V/3,3 V et température conformes en régime sain, aucun retour vers les BEC ni reset Pixhawk sous défaut ; perte radio détectée et repli PX4 sûr si le 5 V CA01 disparaît ; schéma, netlist, ERC et DRC revus avant fabrication. | **Planifié / À valider** ; schéma V0.5-pre, circuits candidats dimensionnés ; protections, PCB et banc à fermer |
| CARTE-004, ELEC-PWR-001 / T-PM-V05-04 | Rail 12 V candidat vers XT30 : vérifier polarité et plage d'entrée de la baseboard réelle, appel et charges Jetson Orin NX 16 Go, SSD, ventilation et USB/caméra ; arrêter puis mettre en défaut le rail calcul sous limites approuvées. Critère : tensions et températures conformes et aucun reset Pixhawk. | **Planifié / À valider** ; spécification du kit développeur Orin Nano non transférable |
| CARTE-007 / T-PM-V05-05 | Vérifier topologie, terminaisons, configuration DroneCAN/PX4 et mesure tension/courant contre référence ; étudier d'abord en SITL la réaction à la perte CAN, puis reproduire celle-ci au banc. Critère : mesure dans la tolérance approuvée, perte signalée et comportement PX4 sûr. | **Planifié / À valider** ; aucun paramètre réel ni essai V0.5 |
| ELEC-PWR-002, CARTE-011 / T-PM-V05-06 | Fermer budgets de chaque BEC (3 A annoncés par port), du 5 V CA01, du 12 V Jetson et du chemin batterie ; mesurer charges permanentes, pointes, chutes et températures des modules, câbles, connecteurs et support, séparément puis simultanément. Critère : profil mission et marges approuvées respectés sans dépasser les limites fabricant. | **Planifié / À valider** ; profils et marges non fixés |
| CAB-CARTO-001, ELEC-PWR-002, CARTE-003/010/011 / T-PDB-V05-01 | Sur la PDB Holybro 300 A top-entry candidate, relever référence/révision et schéma des ports, puis vérifier hors tension la chaîne batterie → PM08-CAN → PDB → XT30 W08 → protection de branche au plus près du port → J103 CA01, continuité, isolement, polarité et détrompage du connecteur XT30 candidat de W08, section/sertissage et absence de contournement du PM. Minimiser et justifier le segment PDB/XT30 en amont de la protection, exposé au courant de défaut batterie. Sous alimentation limitée et charge représentative, mesurer courant permanent/appel, chute de tension, transitoires et températures au port, au câble et à la protection ; injecter les défauts admissibles selon procédure approuvée. Vérifier fixation, isolation, accès, rayon de courbure et retenue du faisceau. Critère : profil et limites fabricant approuvés respectés, sans reset du domaine vol ni réalimentation indésirable ; le marquage « 300 A » de la PDB ne qualifie ni W08 ni XT30. | **Planifié / À valider** ; ports, calibre/protection, implantation et charges non figés ; aucun banc |

Continuité et isolement précèdent toute mise sous tension. Les réactions
logicielles aux défauts sont d'abord étudiées en simulation/PX4 SITL, puis
les défauts sont injectés sur banc sans hélices avec limitation de courant,
coupure manuelle accessible et procédure approuvée. Ces étapes ne qualifient
pas le vol. **Aucun essai V0.5 n'a été exécuté.** Conclusion : **À valider**.

La reprise **historique avant dimensionnement** du schéma KiCad CA01 **V0.5-pre** (Windows amd64, KiCad
10.0.6) est une preuve statique supplémentaire :
[22 invariants et ERC avant dimensionnement](../hardware/electronique/cartographe/carte_avionique/verification/controle_statique_avant_dimensionnement_20260929.json),
53 composants, 51 réseaux, 4 erreurs ERC et aucun avertissement.
J101/5V2_FLIGHT est retiré ; le 5 V radio local passe par F102 ; J503
laisse le +5 V UART2 GNSS non raccordé ; PPS/GPRMC, AUX1 et retour CAP1
ont des nets distincts ; J501/JP501 restent DNP. Le BIAS des deux
LM76003 est repris vers VOUT par R/C candidats suivant TI. Les erreurs
ERC sur U201 PVIN/AGND/BIAS et U301 BIAS ne sont pas masquées.
U101/U102/U503–U509 et les empreintes/protections restent incomplets.
La reprise du 29 septembre conserve la topologie des retouches utilisateur :
les fils remplacent les labels locaux répétés dans les circuits 12 V et
de synchronisation, sans pont entre PPS, GPRMC, trigger et exposition.
Les contrôles acceptent les noms de réseaux internes automatiques et les
résistances retournées ; les deux diviseurs FB sont désormais contrôlés.
Bootstrap, découplages VCC/BIAS et résistances de feedback reçoivent des
valeurs candidates documentées dans DOC-ELEC §4.2.6. Ces calculs nominaux
ne constituent ni une simulation de stabilité ni une mesure de régulation.
La [preuve de reprise compacte](../hardware/electronique/cartographe/carte_avionique/verification/reprise_compacte_20260929.json)
conserve les empreintes des netlists de référence et finale, les différences
de valeurs et le résultat de comparaison : 53 composants et 51 réseaux
inchangés, aucune différence de connexion, DNP et propriétés protégées conservés.
La skill HW Design schématique est validée avec le validateur de skill
et ses métadonnées YAML sont vérifiées.
Le contrôle du câblage global passe également : 21 modules, 34 liaisons,
26 broches CA01 concordantes, aucun endpoint inconnu et diagramme conforme
à DOC-ELEC.
La revue indépendante n'a trouvé aucun défaut de connectivité critique ;
elle ne qualifie pas les valeurs ni le comportement. Le PCB est vide,
aucun essai sous tension ni de synchronisation n'a été réalisé. L'état
demeure **À valider** et **non fabricable**.

### 12.7.1 Dimensionnement CA01, 29–30 septembre 2026

Périmètre : CARTE-003/004/005/006/009/012 ; circuits énergie, régulation et
trigger/capture du schéma. Résultat **Implémenté / matériel À valider**.
Hypothèses, calculs, références et limites : DOC-ELEC §4.2.6–4.2.7 ;
[dimensionnement](../hardware/electronique/cartographe/carte_avionique/dimensionnement.json),
[BOM candidate](../hardware/electronique/cartographe/carte_avionique/bom_candidate.json),
[sources et SHA256](../hardware/electronique/cartographe/sources_fabricants/manifest_sources.json).

| Validation exécutée | Critère / résultat | Limite |
|---|---|---|
| Netlist KiCad10.0.6 Windowsamd64 | 151 composants, 111 réseaux, 221 contrôles de broches/DNP conformes ; [recette et preuve](../hardware/electronique/cartographe/carte_avionique/verification/controle_statique.json) | pas simulation des composants |
| ERC neuf | 0erreur/0avertissement suivant configuration consignée ; sources physiques déclarées à travers passifs | contrôles ignorés listés dans rapport ; aucune qualification empreinte/protection |
| Reproduction analytique | 44 contrôles : eq.TI23/24/Cff, Icrête/limiteHS, Cmin/ESR, feedback, budget d'entrée, LDO/trigger et interfaces temps ; [preuve](../hardware/electronique/cartographe/carte_avionique/verification/calculs_reproduits.json) | hypothèses Ceff/L, niveauxOEM, seuilsSchmitt, température et régime PWM ; pas Bode ou simulation transitoire |
| [Revue indépendante du dimensionnement initial](../hardware/electronique/cartographe/carte_avionique/verification/dimensionnement_revue_20260930.json) | pinmaps TI/Nexperia, polarités, masses, NC/DNP et rendus relus ; bootstrapC111 corrigé, shunt2512/0,5%1W, C103Ceff≥100nF, OV ajustée au réarmement25,2V, F501 réinclus enBOM | revue initiale : ne vaut pas revue finale du lottemps§12.7.2 ; TVS/SOA, empreinteTIQ5A et charge réelle ouvertes |
| Documentation de sources | 29 PDF selon le [contrôle des sources](../hardware/electronique/cartographe/carte_avionique/verification/sources_controle_20260930.json) ; provenance URL/miroir/fichier fourni et empreintes consignées dans le manifeste | variantes réelles OEM et courbesDCbias à vérifier |

Recettes : lancer verify_ca01.ps1 puis verify_dimensionnement.py dans
carte_avionique/verification, et verify_cablage.ps1 pour le registre global.
La preuve de reprise compacte précédente conserve les netlists historiques,
elle n'est pas la preuve du schéma dimensionné actuel.

**Non exécutés :** simulation/Bode, PCB/DRC, mesure des consommations et
transitoires, SOA/sélectivité, thermique/CEM, essais hors tension de toutes
les cibles, banc rails/défauts, synchronisation etRF. Raisons : niveaux
GNSS/Airy et enveloppes réelles ouverts, protectionTVS absente, PCB vide
et carte non assemblée. Pas de compilation logicielle : lot schématique,
documentaire et vérification d'infrastructure uniquement. Aucun niveau
supérieur d'essai n'est validé par ces résultats. **Non fabricable.**

### 12.7.2 Réalisation physique candidate des interfaces temps, 30 septembre 2026

Chaîne : `ELEC-TIM-001 / CARTE-009` → feuille
`05_synchronisation.kicad_sch` → `T-CA01-09 / T-AIRY-SYNC-01` → preuves
statiques ci-dessous, puis banc §12.8. Les circuits temps sont **Implémentés**
dans le schéma ; leurs valeurs, interfaces OEM et matériel restent **À valider**.
R530–R533 sont DNP et `manufacturing_ready=false` : aucun raccordement
au drone ni qualification matérielle n'est acquis.

La méthode de contrôle est de régénérer la
[netlist](../hardware/electronique/cartographe/carte_avionique/verification/netlist.xml),
l'[ERC](../hardware/electronique/cartographe/carte_avionique/verification/erc.json)
et le [contrôle de broches/DNP](../hardware/electronique/cartographe/carte_avionique/verification/controle_statique.json)
avec `verify_ca01.ps1`, puis de reproduire les 44 contrôles arithmétiques
avec `verify_dimensionnement.py` et leur
[preuve](../hardware/electronique/cartographe/carte_avionique/verification/calculs_reproduits.json).
La recette exécutée sous KiCad10.0.6 Windowsamd64 confirme 151 composants,
111 réseaux et 221 invariants dans les preuves
régénérées, avec ERC0/0. Le rendu du
[PDF schématique](../hardware/electronique/cartographe/carte_avionique/verification/CA01_schema_preliminaire.pdf)
a été inspecté ; les empreintes fabricant restent à valider. `verify_sync_preservation.py` passe :
les trois contrôles de conservation de netlist sont consignés dans
[conservation_sync_20260930.json](../hardware/electronique/cartographe/carte_avionique/verification/conservation_sync_20260930.json).
Ces vérifications ne simulent pas les circuits.

La [revue indépendante du lot](../hardware/electronique/cartographe/carte_avionique/verification/synchronisation_revue_20260930.json)
ne relève aucun blocage de topologie. Les valeurs C515/C520, la référence
Orin, les exclusions des connecteurs et le rendu ont été harmonisés ;
les marges électriques demeurent conditionnelles aux mesures prévues.

Points à vérifier dans cette recette : U512/U513 G17 avec TVS TPD1E05U06
avant330 Ω et22 kΩ GND ; U504/U505/U507/U511 LVC1T45 avec DIR A→B et
rails distincts ; U506 TRS3232EIDR sur5V_AIRY_IO, quatre capacités de pompe,
DIN inutilisé défini et sorties inutilisées NC ; U510 TPS70950DBVR depuis
12V_LIDAR avec EN flottant autorisé et C514/C51510 µF/25 V X7R1206 ; référenceOrin J509 issue deCamera0
ou1 pin22VDD3,3 V/pin1GND, rappel10 kΩ, sans +5 V GPIO/Debug.
Conserver les sorties Airy47 Ω et Orin100 Ω DNP avant banc.

Les marges calculées reposent sur GNSS3,3 V/VOH2,9 V supposés ; la borne
Schmitt2,74 V à3,3 V est une hypothèse de monotonie issue de seuils TI
discrets, pas une garantie. Le railAiry4,89–5,11 V/budget25 mA et
jonction≈101 °C àVIN12,6 V/ambiante60 °C sont des estimations JEDEC.
Les quatre capacités de pompe1 µF/25 V doivent conserver respectivement
au moins100 nF/470 nF/470 nF/470 nF effectifs ; le bypass U506 exige
≥1 µF effectif surC5202,2 µF/25 V X7R, plus100 nF.
ChargePPSAiry≤12 mA candidate avant câble.

**Non exécutés :** mesures OEM, Ceff aux coins, PCB/DRC, stabilité et
thermique réelle, ESD système, délais/fronts, arrêt/redémarrage des rails
et courants vers GNSS/Airy/Orin éteints. Le railCSI doit suivre les
domainesGPIO/UART réels ; un railAiry dérivé du12 V ne prouve pas la
séquence d'arrêt de ses IO. PCB vide et carte non assemblée : ces essais
restent planifiés au§12.8. La TVS d'entrée puissance demeure ouverte.

### 12.7.3 Lisibilité de la feuille radio, 30 septembre 2026

Chaîne : `CARTE-008 / CARTE-012` → `04_radio.kicad_sch` →
contrôle graphique et conservation statique de `T-CA01-12`.
La reprise est **Implémentée** : Pixhawk à gauche, radio à droite,
symboles de connecteurs agrandis, liaisons UART directes et sens explicites.
Le [PDF](../hardware/electronique/cartographe/carte_avionique/verification/CA01_schema_preliminaire.pdf)
exporté par KiCad 10.0.6 a été inspecté sur sa page 3 après correction
des champs et espacements.

`verify_ca01.ps1` confirme 151 composants, 111 réseaux, 221 invariants
et ERC 0 erreur / 0 avertissement, avec les exclusions du projet conservées.
`verify_radio_layout.py` compare la netlist avant reprise à la netlist
régénérée : trois contrôles réussis, aucune modification des groupes
de broches ni des champs électriques, identités, valeurs et exclusions
des composants. La [preuve](../hardware/electronique/cartographe/carte_avionique/verification/reprise_radio_20260930.json)
et sa netlist de référence permettent de reproduire ce contrôle sur les
six feuilles. Aucun essai matériel n'est exécuté pour cette reprise
graphique ; la qualification électrique reste **À valider**.

### 12.7.4 Lisibilité énergie et symboles d'alimentation, 1 octobre 2026

L'[export PDF complet](../hardware/electronique/cartographe/carte_avionique/CA01_Avionique.pdf)
est disponible à côté du projet KiCad. Il est régénéré après attribution
des empreintes au §12.7.5 ; la
[preuve d'export](../hardware/electronique/cartographe/carte_avionique/verification/export_pdf_20261001.json)
consigne les empreintes historiques des sources et du PDF de la retouche,
l'ordre des six feuilles et
l'identité de la copie `verification/CA01_schema_preliminaire.pdf`.
Les pages 2 et 3 réexportées ont été inspectées ; aucun circuit n'est modifié.
La reprise complémentaire de U101 (LM74800) en page 2 agrandit son symbole
et dégage les mesures, diviseurs UVLO/OV, commandes de grille et pompe
de charge. La netlist fraîche exportée avant cette retouche est identique
à la netlist finale par ensembles de broches ; les valeurs et identités
des composants sont conservées. Le convertisseur U102 et la branche F102
restent inchangés. Le contrôle de rendu de cette retouche est effectué
sur le PDF final ; la revue indépendante ci-dessous porte sur la reprise
antérieure de U102 et des symboles d'alimentation.

Chaîne : `CARTE-003 / CARTE-004 / CARTE-012` → feuille `01_energie_pm`
et convention graphique des cinq sous-feuilles → contrôle statique et
revue de `T-CA01-12`. Reprise **Implémentée** : symbole U102 agrandi,
passifs FB/COMP dégagés, entrée à gauche et sortie à droite ; alimentations
à barre supérieure orientée vers le haut et masses GND standard.

Recette : `verify_ca01.ps1`, puis `verify_power_layout.py`,
`verify_sync_preservation.py`, `verify_radio_layout.py` et
`verify_cablage.ps1`. La [comparaison de conservation](../hardware/electronique/cartographe/carte_avionique/verification/reprise_energie_power_20261001.json)
utilise une netlist avant reprise : 151 composants et leurs champs électriques
conservés, 111 groupes de broches identiques ; cinq contrôles réussis,
221 invariants et ERC 0 erreur / 0 avertissement. Les trois flags ajoutés
représentent des sources après inductance ou fusible ; les exclusions ERC
existantes sont conservées. Le [PDF](../hardware/electronique/cartographe/carte_avionique/verification/CA01_schema_preliminaire.pdf)
est inspecté sur la page 2 et les autres feuilles affectées ; la
[revue indépendante](../hardware/electronique/cartographe/carte_avionique/verification/revue_energie_power_20261001.json)
consigne le contrôle de topologie et de rendu.

Aucun essai matériel ou nouvelle simulation électrique : changement de
présentation uniquement. La qualification matérielle reste **À valider**.

### 12.7.5 Empreintes et préplacement mécanique CA01, 1 octobre 2026

Chaîne : `CARTE-010 / CARTE-012` → schéma, BOM, empreintes locales,
PCB et stack FreeCAD candidate → `T-CA01-10 / T-CA01-12` →
[preuve de placement](../hardware/electronique/cartographe/carte_avionique/verification/placement_mecanique_20261001.json)
et trois revues indépendantes composants, connecteurs et mécanique.
État **Implémenté**, qualification **À valider**, `manufacturing_ready=false`.

Les 23 empreintes manquantes sont attribuées ; les quatre MOSFET Q5A et
le shunt R116 reçoivent des cuivres spécifiques aux références TI/Vishay.
Les connecteurs sont confrontés aux destinations et aux broches CA01,
sans recopier implicitement un connecteur OEM ayant davantage de contacts.
Le brochage XT30 local conserve 1 = positif et 2 = GND du schéma.
Les fichiers `empreintes_composants.json` et `empreintes_connecteurs.json`
portent candidats, sources, pinmaps et limites de qualification.

Recette dans le README CA01 : exporter netlist/ERC avec `verify_ca01.ps1`,
exécuter `verify_dimensionnement.py`, reconstruire avec `build_placement.py`
sans `--initialise`, lancer le DRC KiCad avec parité schématique, puis
`verify_placement.py`. Résultats : 151 composants et valeurs conservés,
111 groupes de broches inchangés, huit DNP conservés, 221 invariants,
ERC 0 erreur / 0 avertissement avec la configuration existante,
44 contrôles arithmétiques conformes. Les 155 empreintes PCB comprennent
quatre fixations ; zéro problème de parité, modèle de corps manquant,
chevauchement de courtyards ou intrusion dans les réserves RP4TD/TVS.
Zéro piste et zéro zone ; 348 connexions non routées sont attendues.

Le DRC conserve **30 perçages thermiques de 0,2 mm** sur U201/U301 face
au minimum projet de 0,3 mm. Aucune règle n'est abaissée pour les masquer ;
empreinte thermique et procédé fabricant restent ouverts avant fabrication.
Le placement mécanique ne démontre pas les boucles de commutation, Kelvin,
retours de courant, distances électriques et dissipation du PCB routé.

Les [revues composants](../hardware/electronique/cartographe/carte_avionique/verification/revue_composants_placement_20261001.json)
et [connecteurs](../hardware/electronique/cartographe/carte_avionique/verification/revue_connecteurs_placement_20261001.json)
confirment pads, réseaux, DNP, BOM et orientation. L'export graphique
SVG et les six pages du PDF ont été inspectés ; la
[preuve d'export de cette étape](../hardware/electronique/cartographe/carte_avionique/verification/export_pdf_empreintes_20261001.json)
consigne leurs sources et l'identité des deux PDF.

La [revue mécanique](../hardware/mecanique/cartographe/verification/revue_stack_ca01_20261001.json)
relit indépendamment les 155 placements, réouvre les trois documents
FreeCAD et résout les deux liens externes. Le PCB natif et ses quatre
perçages sont valides ; les 163 solides composants correspondent au STEP
final. À l'écart candidat de 10 mm, les intervalles Z sont disjoints,
séparation conservative ≥1,9446 mm pour les géométries représentées.
Source Holybro, repères, hypothèses et limites : DOC-MEC §4.4.1.

**Non exécutés :** routage, qualification fabricant, montage réel,
accouplement des faisceaux/queues THT, thermique, CEM, vibrations,
mesures de rails et de synchronisation. Carte non fabriquée ni assemblée ;
les boîtes composants servent au contrôle d'encombrement candidat.
La sélection TVS, F101/Icc, Ceff, détrompage 12 V/5 V et variantes
matérielles restent ouverts. Aucune qualification matérielle déduite.

### 12.7.6 Enveloppe analytique du shunt et dissipation PCB, 1 octobre 2026

Chaîne : `CARTE-004 / CARTE-011 / CARTE-012` → R116, DAP/EP et plans/vias
planifiés → `T-CA01-04 / T-CA01-11 / T-CA01-12` →
[recette reproductible](../hardware/electronique/cartographe/carte_avionique/verification/verify_shunt_thermique.py)
et [preuve analytique](../hardware/electronique/cartographe/carte_avionique/verification/shunt_thermique_20261001.json).
Les hypothèses et la cible utilisateur sont dans `dimensionnement.json` ;
DOC-ELEC §4.2.9 distingue composant actuellement représenté et remplacement.

Le calcul intègre la conduction pendant l'état bas du buck, l'ondulation,
les coins VIN/VOUT/L/fréquence et la variation de résistance. Enveloppes
arrondies : 0,20 W à 6 A et 0,62 W en limitation soutenue. La comparaison
au derating fabricant favorise CSM3637 3 W, encore 1,35 W à 125 °C
d'ambiance locale candidate ; le domaine TCR vise la température résistive
jusqu'à 125 °C, autoéchauffement compris.
Dix contrôles arithmétiques passent ; les 44 contrôles de dimensionnement
existants restent conformes. La
[revue indépendante](../hardware/electronique/cartographe/carte_avionique/verification/revue_shunt_standard_20261001.json)
reproduit les chiffres en mémoire, vérifie les empreintes SHA256 et les
affectations drain/GND sur le PCB ; aucune erreur factuelle relevée.
Le résultat est **À valider**, aucune qualification matérielle déduite.
L'utilisateur accepte ±0,1 %. R116 est remplacé par CSM3637
Y14880R01000B9R 10 mΩ /15 ppm/K /3 W, avec empreinte quatre bornes,
préplacement et modèle de stack synchronisés. La topologie et la valeur
10 mΩ restent inchangées ; tolérance, puissance et boîtier sont déclarés
comme modification autorisée dans la configuration de placement.
ERC : zéro erreur/avertissement, 221 invariants conformes ; placement :
155 empreintes, zéro chevauchement, zéro problème de parité, aucune piste
ni zone. Les 30 perçages thermiques de 0,2 mm sous la règle de 0,3 mm restent
ouverts. Le PDF final comporte six pages : page 2 rendue et inspectée,
texte des cinq autres pages identique à l'export précédent ;
[provenance](../hardware/electronique/cartographe/carte_avionique/verification/export_pdf_shunt_standard_20261001.json).

Critères de fermeture : pièces reçues conformes à 10 mΩ ±0,1 % / ≤25 ppm/K,
connexion Kelvin conforme, puissance et énergie de défaut admissibles,
température mesurée sous le derating avec marge déclarée, répétition de
défauts sans dommage ni dérive hors spécification, températures DAP/EP
compatibles avec les limites de chaque composant. Le banc utilisera les
charges simultanées, l'ambiance maximale et le débit minimal mesuré dans
la stack finale, après fermeture du routage et des protections.

**Non exécutés :** essais thermiques et défauts sur carte, validation des
impulsions par le fabricant, mesures LFM et routage. Carte non assemblée,
stackup ouvert ; plans/vias **Planifiés**, `manufacturing_ready=false`.

### 12.7.7 Étape mécanique RP4TD antérieure, 1 octobre 2026

L’étape filaire précédente ajoutait MOD401 propre au PCB, sans pads,
en conservant J401/W11 : 156 empreintes, zéro chevauchement et parité.
Sa [revue](../hardware/electronique/cartographe/carte_avionique/verification/revue_rp4td_20261001.json)
reste une preuve historique. Cette variante est remplacée par la cible
directe du §12.7.8 ; les fichiers de placement et de stack courants ne
constituent plus les entrées de cette revue ancienne.

### 12.7.8 Symbole et empreinte RP4TD sur broches, 1 octobre 2026

Chaîne : `CARTE-008 / CARTE-010 / CARTE-012` → MOD401 →
`T-CA01-08 / T-CA01-10 / T-CA01-12` →
[inventaire](../hardware/electronique/cartographe/carte_avionique/empreinte_rp4td.json),
[placement](../hardware/electronique/cartographe/carte_avionique/verification/placement_mecanique_20261001.json),
[revue THT](../hardware/electronique/cartographe/carte_avionique/verification/revue_rp4td_tht_20261001.json)
et [export PDF](../hardware/electronique/cartographe/carte_avionique/verification/export_pdf_rp4td_tht_20261001.json).
Symbole, empreinte et préplacement **Implémentés**, géométrie et montage
**À valider**, `manufacturing_ready=false`. L’étape directe sans pads est
historique dans `revue_rp4td_direct_20261001.json` et la preuve de stack.

La demande de création est traitée par une empreinte **candidate** à
quatre pads THT à partir de la photo TOP constructeur, à défaut de plan coté.
Ce choix remplace l’absence de géométrie ; il ne transforme pas la photo
en métrologie. Protocole KiCad10.0.6 Windowsamd64 : netlist/ERC, contrôle
de la seule bijection J401/n→MOD401/n et des autres réseaux/DNP, construction
normale du PCB, DRC avec parité, `verify_placement.py`, revue indépendante
du signe des axes/ordre RX/TX/5V/G, des quatre pads et de leurs dégagements.
Exporter PDF/SVG/STEP, inspecter page3 et placement ; réouvrir FreeCAD
dans un processus neuf avec quatre trous MOD401 paramétriques.

Résultats : **230 contrôles de connectivité réussis**, ERC **0 erreur / 0
avertissement**, 151composants/111réseaux. MOD401 est compté une fois,
J401/W11 sont retirés, les huit DNP sont conservés. PCB **155 empreintes**,
**0 erreur de parité**, **0 chevauchement**, quatre pads correctement
raccordés, aucun modèle absent, **0 piste / 0 zone**. Les 30 perçages
thermiques0,2mm préexistants restent ouverts ; 350 connexions non routées
sont attendues. Le contrôle de placement passe pour son périmètre,
sans qualifier les cotes des contacts ni la fabricabilité.

Candidate : X11,85mm,Y±3,9/±1,3mm (pas2,6mm), trou fini0,8mm/pad1,6mm
pour broche ronde0,5mm générique. Pixels et transformation sont consignés
dans l’inventaire, image originale archivée et hashée. Les rapports image
et corps nominal diffèrent d’environ2,5% ; aucune tolérance n’est garantie.
Les nouveaux trous sont présents dans STEP et natif ; 163solides composants,
un corps radio et liens externes valides. Huit features de perçage natives :
quatre M3 et quatre MOD401. La poseZ du corps reste illustrative, broches3D
et hauteur libre non définies. Assemblage SA03 actif historique inchangé.

PDF six pages : page3 rendue/inspectée, texte des cinq autres pages
identique à l’export précédent. Le symbole dédié est rechargeable dans
`CA01_Radio.kicad_sym`, avec affectation par `sym-lib-table`.

**Non exécutés :** mesure des centres/diamètres réels, contrôle broches
reçues, détermination de la hauteur et de l’appui isolant, brasage/montage
réel, continuité sur pièce, vibration, isolation, accès BIND/U.FL/antennes,
thermique et RF. Pas de plan coté et carte non assemblée ; l’empreinte
candidate doit être corrigée/confirmée avant fabrication.

### 12.7.9 Substitution des modèles3D CA01, 1 octobre 2026

Chaîne `CARTE-010 / CARTE-012` → modèles, PCB et variante native CA01/Holybro
→ `T-CA01-10 / T-CA01-12` →
[inventaire3D](../hardware/electronique/cartographe/carte_avionique/modeles_3d.json),
[preuve3D](../hardware/mecanique/cartographe/verification/modeles_3d_ca01_20261001.json)
et [preuve de placement](../hardware/electronique/cartographe/carte_avionique/verification/placement_mecanique_20261001.json).
**Implémenté**, qualification **À valider**, `manufacturing_ready=false`.

L'audit initial identifie onze familles de boîtes et aucun fichier manquant
inattendu : trous, points de test et cavalier ouvert ne sont pas des composants.
Dix familles /16occurrences sont remplacées par des modèles détaillés
issus de bibliothèques, auteurs ou plans fabricants, sans modification de
pad, réseau, UUID, valeur, DNP, pose ou règle électrique. Les sources originales
sont archivées, les21STEP de bibliothèque utilisés ont une copie locale,
et les dix références de pièces nouvelles possèdent un document natif distinct.
RP4TD standard reste une enveloppe : modèle détaillé fiable introuvable,
résultat RP4TD-M rejeté. Les MPN non sélectionnés restent génériques.

Recette Windows amd64 : `build_ca01_ti_models.py`,
`build_ca01_component_models.py` et `build_ca01_connector_models.py`
reproduisent les modèles nominaux. Le mapping `modeles_3d.json` est repris
par `build_placement.py`. Exporter avec KiCad10.0.6
`pcb export step --user-origin 50x50mm --no-dnp --subst-models`, puis
exécuter `update_ca01_models_native.py` et, dans un processus FreeCAD1.1.3
neuf, `verify_ca01_models_native.py`. Le rendu KiCad courant est inspecté.
Une [reconstruction isolée](../hardware/mecanique/cartographe/verification/reconstruction_modeles_ca01_20261001.json)
confirme que la recette reprend les 155 empreintes, leurs modèles, poses,
valeurs, pads et réseaux ; PCB et réglages du projet source restent inchangés.
Les positions de référence sont dans `positions_modeles_ca01_20261001.json`.

La revue indépendante révèle puis fait corriger quatre écarts de modèle :
axes DPY perpendiculaires aux pads, contacts force/sense CSM inversés enY,
translation PH absente du STEP et décalage de plaque Q5A rectifié àX+.65.
Le contact Kelvin sense recouvre91.93% de sa plage nominale, avec0.125mm
de dépassement intérieur ; ses tolérances et le brasage restent à valider.
La validation porte sur les STEP relus,
pas seulement la vue ou la matrice du document natif. Les centres des queues
XT30/VH sont alignés aux trous ; contacts DPY/CSM et PH concordants après
correction. Les tolérances d'assemblage restent ouvertes.

Résultats : **155 empreintes conservées**, zéro piste/zone, parité zéro,
zéro modèle attendu absent, zéro chevauchement de courtyards. Les30perçages
thermiques0,2mm sous la règle0,3mm et350connexions non routées restent
ouverts. Le STEP comporte308solides composants /141composants représentés ;
réouverture et recalcul des dix nouveaux natifs et de la stack sans erreur,
liens résolus, PCB paramétrique préservé, concordance STEP/natif et assemblage
actif conservés. Aucune interférence entre composants distincts ni volume
commun CA01/Holybro dans les shapes nominales. Distance minimale des formes
1,9446mm ; intervalles Z englobants recouvrants de0,0604mm, donc aucune
conclusion par disjonction des seules boîtes Z.

**Non exécutés :** métrologie des composants reçus, montage réel et tolérances,
faisceaux accouplés, broches/sous-face RP4TD, thermique, CEM, vibrations,
routage et fabrication. Les modèles détaillés ne sont pas des STEP OEM
garantis. Ces contrôles ne qualifient ni montage ni vol.

### 12.7.10 Démarrage du routage et vias thermiques CA01, 1 octobre 2026

Les §12.7.5–12.7.9 conservent les résultats datés des étapes précédentes
(PCB sans cuivre et trous thermiques Ø0,2 mm). Le présent paragraphe décrit
l’étape initiale des 1–2 octobre ; le routage final est décrit au §12.7.13.

Chaîne `CARTE-003/004/005/006/011/012` → stackup, plans, DC/DC et MOSFET →
`T-CA01-03/04/05/06/11/12` → [configuration](../hardware/electronique/cartographe/carte_avionique/routage.json),
[preuve de routage initial](../hardware/electronique/cartographe/carte_avionique/verification/routage_initial_20261001.json)
et [revue indépendante](../hardware/electronique/cartographe/carte_avionique/verification/revue_routage_20261001.json).
Réalisation **Implémentée**, résultat **préliminaire**, qualification **À valider**,
`manufacturing_ready=false`. Cible de contrôle : KiCad 10.0.6, Windows amd64 ;
les empreintes des fichiers/configurations sont consignées dans les preuves.

Protocole : exporter netlist/ERC avec `verify_ca01.ps1`, contrôler la
variante thermique par `verify_lm76003_thermal_variant.py`, construire
l’étape sur un PCB sans cuivre par `start_routing.py`, remplir les zones
et lancer le DRC avec parité, puis `verify_routing.py` et revue indépendante.
Après cette initialisation, `start_routing.py` et `build_placement.py`
refusent le PCB contenant des pistes/vias/zones ; poursuivre l’édition
dans le fichier courant. Aucun historique de routage n’est effacé.

Critères du lot : quatre couches et épaisseur 1,6 mm conformes à la
configuration ; GND et batterie protégée distincts ; vias thermiques sur
le potentiel réel des pads ; RTN13 flottant ; exclusion GND F.Cu des prises
Kelvin R116 ; contours, poses, modèles, valeurs/DNP et topologie conservés ;
zéro violation DRC de géométrie/parité. Les connexions restantes doivent
être comptées explicitement, sans être qualifiées comme un routage complet.

| Contrôle | Résultat courant / preuve |
|---|---|
| Empilage et cuivre | 4 couches ; 70/35/35/70 µm, diélectriques0,15/1,09/0,15 mm et FR4 candidats fabricant ; DOC-ELEC §4.2.9 |
| Cuivre créé | 10 zones, 111 vias Ø0,6/0,3 mm et quatre segments ; J103→F101 et Q101→Q102 seulement |
| Potentiels thermiques | U102/U201/U301→GND, Q101/Q102→drain commun, Q103→VIN_PAYLOAD_PROT, Q104→SW compact ; U101/13 sans via |
| DAP LM76003 | 30 trous Ø0,3/padsØ0,5 ; neuf contrôles de variante réussis, cuivre/XY conservés, anneau nominal0,1 mm et entre-trous minimal0,35 mm |
| Schéma | 151 composants/111 réseaux, 230 invariants réussis ; ERC0 erreur/0 avertissement selon configuration ; valeurs/DNP et groupes de broches conservés |
| DRC initial | 0 violation de géométrie, 0 problème de parité, **218 connexions non routées** ; [rapport](../hardware/electronique/cartographe/carte_avionique/verification/drc_routage_20261001.json) |
| Mécanique | 155 empreintes, poses/contour/fixations et mapping3D conservés ; aucune qualification physique supplémentaire |

La [preuve de variante](../hardware/electronique/cartographe/carte_avionique/verification/variante_lm76003_percages_20261001.json)
compare l’empreinte bibliothèque et la variante locale ainsi que les netlists
avant/après. Les seuls champs électriques modifiés sont les associations
U201/U301 ; le symbole bibliothèque standard est conservé. Les deux PDF
schématiques sont réexportés et identiques ; feuilles convertisseurs4/6
rendues et inspectées, avec [provenance dédiée](../hardware/electronique/cartographe/carte_avionique/verification/export_pdf_variante_lm76003_20261001.json).
La skill HW Design schématique est appliquée à ces associations sans modifier
la mise en page ni les circuits. Les couches PCB sont inspectées dans la revue.

Les vias utilisent des connexions directes au cuivre pour diffuser la chaleur ;
les reliefs thermiques destinés au brasage ne prouvent pas cette diffusion.
Les grilles, bootstrap, boucle SW/self, sorties, Kelvin et FB/COMP/ILIM
restent à placer/router ; l’exclusion Kelvin ne termine pas la mesure.
Des surfaces et sections de cuivre candidates n’établissent ni pertes,
chute de tension, température, stabilité ou CEM sur la carte réelle.

**Non exécutés :** simulation thermique/boucle, charges permanentes/appels,
mesures de chutes/températures, CEM, validation fabricant de l’empilage et
des tolérances, procédé via-in-pad/remplissage/stencil, métrologie RP4TD,
fabrication, brasage et montage réel. La carte reste non assemblée,
routage/protections/interfaces incomplets ; ces essais attendent la clôture
du design et des protocoles de banc. Aucun essai de vol ou pulvérisation.

La finalisation du **2 octobre 2026** confirme les 14 contrôles de la
revue indépendante. Une [reconstruction isolée](../hardware/electronique/cartographe/carte_avionique/verification/reproduction_routage_20261002.json)
à partir des empreintes et positions déclarées retrouve les mêmes composants,
modèles, pads/réseaux, pistes, vias et contours de zones, hors UUID.
Les [gardes de préservation](../hardware/electronique/cartographe/carte_avionique/verification/protection_routage_20261002.json)
refusent les deux reconstructions sur une copie déjà routée ; source, projet
et copie restent inchangés. La recette reproductible est
`verification/verify_routing_reproduction.py` ; les commandes sont dans le
README CA01. ERC, neuf contrôles de variante, 44 calculs et contrôle du
shunt ont été rejoués avec succès. DRC et parité restent à zéro, avec
218 connexions restantes. Ces résultats couvrent le démarrage du routage.


### 12.7.11 Plan de validation électrique, thermique et CEM CA01

Le [plan structuré](../hardware/electronique/cartographe/carte_avionique/validation_electrique_thermique_cem.json)
est **Planifié**, critères candidats et qualification **À valider**. Il
décline les essais existants sans les remplacer : CARTE-002..009/011/012
→ protection, convertisseurs, interfaces et montage CA01/SA03
→ T-CA01-E01..E06, T-CA01-TH01..TH03, T-CA01-CEM01..CEM04
→ résultats et mesures à produire. Aucun essai physique n'est exécuté
par la préparation de ce protocole.

**Prérequis et ordre.** Fermer les revues schéma/PCB/empreintes/BOM et
DFM, puis vérifier la carte assemblée hors tension. Justifier TVS,
fusibles et pouvoir de coupure DC, protection W08 proche PDB, SOA,
appel capacitif, charges et limites OEM. Les réactions aux défauts du
domaine vol suivent d'abord la simulation/PX4 SITL pertinente du §2.
Alimenter ensuite avec une source limitée et des charges fictives ;
les charges réelles se raccordent seulement après validation de leurs
rails et interfaces. Le banc intégré reste sans hélices, avec coupure
matérielle accessible ; aucun vol ni essai de traitement n'est prévu.

La matrice de caractérisation candidate couvre VIN **18 / 21,6 / 25,2 V**
et charges **0 / 25 / 50 / 100 %** des capacités de dimensionnement :
12 V calcul **6 A**, 12 V LiDAR **3 A**, 5 V auxiliaire **3 A total**
(radio, synchronisation et J301), budget 3,3 V **50 mA**. Ces valeurs
ne sont ni des consommations de mission ni des exigences figées.
Le courant réel Airy au démarrage est mesuré ; la source doit soutenir
le besoin d'au moins 2 A déjà identifié. Balayer aussi les faibles
charges en PFM et les transitions de régime. Fixer avant exécution
nombre de cycles/répétitions, températures, durées, fronts de charge,
rampes et conditions de séquencement.

Les critères numériques de tolérance des rails, ondulation, dépassements,
établissement, marge de boucle, température, stabilisation et CEM restent
**À valider**. Le plan expose les champs ouverts et un enregistrement
d'approbation : l'absence d'un critère ou d'une incertitude interdit
un verdict qualifiant. L'inversion, la surtension et les défauts limités
attendent amplitude/durée/énergie approuvées et compatibilité SOA/protection.
**Aucun court-circuit direct sur batterie.** Arrêter sur dépassement d'un
seuil sûr, limitation source inattendue, surchauffe, reset du domaine vol,
retour d'alimentation, odeur/arc ou perte des mesures. Décharger et contrôler
les tensions avant intervention.

| Sous-test / renvoi | Protocole et preuve attendue |
|---|---|
| T-CA01-E01 → T-CA01-01/10/12 | Inspection montage/MPN/DNP/polarités/EP, continuité et isolement hors tension, géométrie RP4TD reçue ; contrôle shunt quatre fils et prises Kelvin ; photos/inspection joints |
| T-CA01-E02 → T-CA01-03 | Rampes et démarrages avec limitation, appel et UVLO/OV/hystérésis ; VDS/VGS et profil SOA de Q101/Q102 ; inversion/transitoires seulement selon énergie approuvée |
| T-CA01-E03 → T-CA01-04/05/06 | Rails séparés puis simultanés, charge statique/dynamique et PFM ; tension/ondulation au COUT et à la charge, chutes, rendement, gates/bootstrap/SW et stabilité compute |
| T-CA01-E04 → T-CA01-02/03/06, T-PM-V05-03 | Défauts de branche limités, sélectivité/limitation/hiccup et reprise ; aucune réalimentation ni reset Pixhawk ; perte radio détectée et repli PX4 attendu |
| T-CA01-E05 → T-CA01-06/08/09, T-AIRY-SYNC-01 | Niveaux/fronts/courants hors tension et séquences OEM suivant §12.7.2/12.8 ; référence J509, PPS/GPRMC, trigger/ExposureActive/Frame ID ; DNP fermés uniquement après leurs conditions |
| T-CA01-E06 → T-CA01-04/05/06, T-PM-V05-04/06 | Orin/SSD/USB, Airy et RP4TD réels identifiés, démarrages séparés/simultanés et profil acquisition/calcul ; appels, charge continue, resets et budget J301 |
| T-CA01-TH01 → T-CA01-04/05/06/11 | Carte seule, pertes et carte de température, thermocouples/IR/ambiante/débit ; coins chauffants sélectionnés par mesure et stabilité thermique selon critère approuvé |
| T-CA01-TH02 → T-CA01-10/11, T-PM-V05-06 | Répéter à charges simultanées dans SA03 final, orientation/espacement/capots/câbles réels, chaleur Jetson, ambiance maximale et débit local minimal mesuré |
| T-CA01-TH03 → T-CA01-03/11 | Appels répétitifs et défauts limités approuvés, SOA/derating et protection ; contrôler dommages et régulation avant/après refroidissement |
| T-CA01-CEM01 → T-CA01-11 | Préconformité conduite entrée/sorties et cartographie E/H ; référence convertisseurs arrêtés, chacun actif puis simultanés, VIN/charges/PFM ; spectres et montage reproductibles |
| T-CA01-CEM02 → T-CA01-08/09/11, T-RF-01..06 | Comparer GNSS/radio/temps/acquisition à référence électrique équivalente avec géométrie identique ; qualité/pertes/corruption/reset/gigue et corrélation DC/DC |
| T-CA01-CEM03 → T-CA01-02/03/11 | Immunité pertinente par ports en laboratoire, après sélection du référentiel, niveaux/énergie/critères de performance ; fonctionnement avant/pendant/après et récupération |
| T-CA01-CEM04 → T-CA01-11 | Intégration ESC/moteurs suivant portes DOC-VAL au banc sécurisé sans hélices ; site/laboratoire rayonné final avec montage/faisceaux/antennes gelés ; aucun résultat de vol déduit |

**Mesures thermiques.** Instrumenter U101/U102/U201/U301/U503, Q101–Q104,
R116, selfs, fusibles, pistes/vias et connecteurs, avec sondes isolées sur
les drains. Consigner température boîtier, PCB, air local et débit, puis
estimer la jonction avec méthode adaptée, pertes et incertitudes. Pour
U201/U301, TI demande une jonction sous **125 °C** en exploitation ;
la marge de design et le seuil d'arrêt restent à approuver avant banc.
Les limites des autres MPN réellement montés sont relevées séparément.
L'arrêt thermique et les maximums absolus ne sont pas des critères nominaux.
Le plan n'utilise pas une résistance θJA de coupon fabricant comme preuve
de température sur CA01 ; la température IR du boîtier ne mesure pas
directement la jonction. La qualification carte seule ne s'étend pas à
SA03 ni au débit d'air supposé en vol.
Sources primaires : [LM76003, layout/thermique](https://www.ti.com/lit/ds/symlink/lm76003.pdf),
[LM5146-Q1](https://www.ti.com/lit/ds/symlink/lm5146-q1.pdf) et
[TI SPRA953D, interprétation des métriques thermiques](https://www.ti.com/lit/an/spra953d/spra953d.pdf),
consultées le 2 octobre 2026.

**Préconformité CEM.** Définir avant mesure le réseau de stabilisation
adapté au DC, protections analyseur, configuration câble/masse et
paramètres spectre (bande, RBW/VBW, détecteur et plancher de bruit).
Inclure faible charge/PFM et convertisseurs simultanés. Une sonde de
champ proche sert au diagnostic ; elle ne remplace ni un site rayonné
ni le référentiel/limites/critères de performance à sélectionner et
vérifier avec le laboratoire avant qualification. Aucun niveau arbitraire
d'ESD, RF ou impulsion n'est prescrit par ce plan.

Chaque exécution conserve révision/numéro de série, BOM montée/DNP, SHA256
des entrées, montage, firmwares/paramètres, instruments et étalonnages,
calibrations/émissivité/débit, profils des charges, unités/incertitudes,
captures brutes, critères approuvés, événements, anomalies et conclusion.
Les contrats T0 du §3 s'appliquent aux exécutions logicielles liées ;
le registre physique ajoute l'identité métrologique. Les données brutes
volumineuses restent hors Git, avec manifestes et synthèses légers liés.

**Résultats :** plan et traçabilité **Implémentés** dans les artefacts,
campagne **Planifiée**, qualification **À valider**. Simulation de boucle,
essais électriques, thermiques, CEM, laboratoire, montage et mesures
physiques **non exécutés**, car la carte n'est pas fabriquée/assemblée et
les gates de design, procédé et critères de banc restent ouverts.
La réussite d'un contrôle de fichiers du plan n'est pas un résultat matériel.

### 12.7.12 Dossier de fabrication candidat CA01

Le [dossier de contraintes](../hardware/electronique/cartographe/carte_avionique/fabrication/contraintes_fabrication.json)
est **Implémenté** comme dossier provisoire, manufacturing_ready=false : aucun fabricant sélectionné,
commande ou fabrication lancée. Il relie CARTE-012 → fichiers CAO/BOM et
procédés → T-CA01-12 / gates FAB-G01..06 → DFM et libération à finaliser.
Le contour nominal reste 126 × 80 mm ; le placement électrique courant
et les exports provisoires vérifiés sont décrits au §12.7.13. La fabrication
physique reste **Planifiée**. Aucun ancien résultat de préplacement ou
routage initial ne qualifie les données finales du fabricant.

| Élément candidat | À confirmer avant release |
|---|---|
| 4 couches, 1,6 mm ; cuivre 70/35/35/70 µm | Cuivre fini garanti et tolérances, matériau FR4/Tg/CTE/Td, résines/épaisseurs pressées ; plans GND et VIN_PAYLOAD_PROT distincts, SW compact |
| Diélectriques 0,15/1,09/0,15 mm | Somme diélectrique 1,39 mm + cuivre 0,21 mm = 1,60 mm nominal ; finition/vernis et tolérance d'épaisseur à intégrer avec le fabricant |
| Vias traversants Ø0,6 / trou0,3 mm | Anneau CAO nominal0,15 mm ; cuivre de barillet, diamètre fini/outil réel, décentrage et anneaux internes/externes à confirmer |
| EP U201/U301 : 30 trous Ø0,3 / padsØ0,5 mm | Anneau CAO nominal0,1 mm critique ; vérifier le diamètre outil et la métallisation, sans réduction automatique silencieuse des trous |
| H1..H4 : quatre NPTH Ø3,2 mm | Positions, tolérances et enveloppe vis/entretoises SA03 ; isolation et jeux cuivre/carbone |
| MOD401 : quatre PTH Ø0,8 / padsØ1,6 mm | Géométrie RP4TD/broches reçues mesurée, hauteur/appui isolant, brochage et séquence de soudure |
| Pistes/espaces signaux0,2 mm, zones0,25 mm, cuivre/bord0,5 mm | DFM au cuivre extérieur70 µm, vernis QFN et tolérances, inventaire de tous trous/slots depuis le PCB final |
| Via-in-pad, finition/stencil | Remplissage/cap cuivre plan candidats ou autre procédé démontré ; fuite de pâte, coplanarité, vides/joint EP et profil refusion approuvés assembleur |

Les anneaux CAO ne sont pas des anneaux de fabrication garantis : la taille
de l'outil et la métallisation changent le calcul. Le remplissage/cap est
un candidat à approuver ; le tenting global seul ne démontre pas l'absence
de pompage de soudure sous un pad EP ouvert.
Ces points sont étayés par les guides primaires fabricant
[Eurocircuits, perçages](https://www.eurocircuits.com/technical-guidelines/pcb-design-guidelines/drilled-holes/),
[anneaux et classes](https://www.eurocircuits.com/pcb-classification-drill-class/) et
[via-in-pad](https://www.eurocircuits.com/technical-guidelines/pcb-assembly-guidelines/via-in-pad/),
consultés le 2 octobre 2026 ; ils ne constituent pas une sélection du fabricant
ni l'acceptation du stack CA01.


La [BOM d'assemblage candidate CSV](../hardware/electronique/cartographe/carte_avionique/fabrication/bom_assemblage_candidate.csv)
et son [registre d'assemblage](../hardware/electronique/cartographe/carte_avionique/fabrication/assemblage_candidate.json)
consignent **151 références**, **141 pièces candidates à monter** (136 SMD,
5 THT), **8 DNP**, deux pastilles test sans composant et quatre fixations
NPTH présentes uniquement sur PCB. La quantité de montage est zéro pour
les DNP/objets sans pièce ; aucun montage physique n'est exécuté.
**44 références à monter ont encore leur MPN vide dans la BOM** ; les
champs sont conservés sans substitution. Les colonnes MPN BOM/netlist et
valeur BOM/PCB sont distinctes : 38 MPN BOM non renseignés en netlist
(dont quatre DNP) et quatre labels R201/R202/R301/R302 omettant le suffixe
25 ppm restent à réconcilier avant release. Empreintes et DNP concordent
entre les trois sources ; ces contrôles n'établissent pas la conformité
des pièces ni du brasage. Le CSV se vérifie par réimport intégral et
ses empreintes sont liées à l'instantané des sources ; il ne remplace
pas le fichier de placement CPL final.

Le dossier prévoit Gerber X2/job des quatre cuivres, vernis/serigraphie/contour
et pâte approuvée, Excellon **PTH/NPTH séparés** avec slots et tableau
d'outils/convention de taille, netlist IPC-D-356, BOM finale/CPL/pin1/DNP,
plan de montage/inspection EP et manifeste SHA256 des exports à révision
gelée. Les fichiers CAM doivent être inspectés et comparés aux sources ;
aucune correction fabricant silencieuse n'est acceptée. Le tableau outils,
la revue DFM, les tolérances et la preuve du procédé restent à approuver ; les exports provisoires sont décrits au §12.7.13.

**Portes de sortie :** fermeture MPN/protections/Ceff/interfaces/RP4TD ;
routage intégral sans connexion restante et ERC/DRC/parité/revue sans
anomalie ouverte ; stack/vias/perçages/stencil/finition approuvés ; exports
et empreintes cohérents ; prototype destiné à des essais et critères
approuvés. Fabrication d'un prototype et qualification pour usage sont
deux états distincts : aucun prototype ne devient **Qualifié** par sa
seule fabrication. Les preuves électriques/thermiques/CEM du §12.7.11
restent nécessaires dans leur périmètre.



### 12.7.13 Routage complet CA01 et dossier fabricant provisoire, 2 octobre 2026

La [carte native routée](../hardware/electronique/cartographe/carte_avionique/CA01_Avionique.kicad_pcb)
a désormais **zéro connexion non routée**. Chaîne CARTE-003/004/005/006/011/012
→ protections/DC/DC, retours, Kelvin, interfaces et couches PCB
→ T-CA01-03/04/05/06/11/12
→ [preuve de routage complet](../hardware/electronique/cartographe/carte_avionique/verification/routage_complet_20261002.json)
et [DRC final](../hardware/electronique/cartographe/carte_avionique/verification/drc_routage_complet_20261002.json).
Le routage est **Implémenté**, résultat **préliminaire**, qualification
électrique/thermique/CEM **À valider**, manufacturing_ready=false.
Les preuves initiales et leurs 218 connexions du §12.7.10 restent
historiques ; elles ne sont pas les comptages du PCB final.

Cible du contrôle : **Windows amd64, KiCad 10.0.6**, PCB dans son projet
et bibliothèques déclarées. Protocole : remplir les zones, exécuter DRC
avec parité, contrôler nets/pads/empreintes/DNP, plans/vias et règle Kelvin,
puis consigner sources/commandes/empreintes dans la preuve finale.
La revue indépendante passe28/28 ; les459 associations pad/net sont conservées.
Le contrôle principal passe15/15 et la comparaison des exports10/10.
Les perçages sont297PTH (251vias+30EP+16contacts) et4NPTH ;
les136positionsSMD et141positions totales concordent avec le PCB et la BOM.
Les coordonnées Excellon sont arrondies à0,001mm (écart maximal0,0005mm
attendu par encodage), sans garantir la tolérance du procédé physique.
ERC0/0 et230invariants schématiques ont été rejoués sur les sources courantes.
Une exécution sur une copie isolée sans contexte projet peut signaler des
bibliothèques manquantes ; le rapport final ci-dessus porte sur le projet
natif. La configuration de DRC et ses exclusions font partie de la preuve.

| Contrôle du routage final | Résultat / limite |
|---|---|
| Structure | 155 empreintes (151 références électriques et quatre fixations), contour nominal 126 × 80 mm ; placement électrique repris pour boucles/routage, montage SA03 réel **À valider** |
| Pistes et vias | **1 255 segments**, **251 vias traversants**, **10 zones de cuivre** et **sept zones de règles Kelvin** ; paramètres et surfaces réellement remplies dans la preuve |
| Continuité des bus de charge | Contrôle CAO indépendant candidat : chemin large de **1,8 mm** sur 12V_COMPUTE, 12V_LIDAR et 5V_AUX vers leurs charges, et **0,6 mm** pour l'alimentation radio via F102 ; branches fines de feedback conservées, sans leur attribuer le courant de charge ; capacité de courant/chute/échauffement **À valider** |
| Empilage | Quatre couches, GND et VIN_PAYLOAD_PROT distincts ; cuivre 70/35/35/70 µm et épaisseur 1,6 mm candidats ; validation fabricant et thermique **À valider** |
| Potentiels thermiques | EP U102/U201/U301→GND, Q101/Q102→drain commun, Q103→VIN_PAYLOAD_PROT, Q104→SW compact ; U101/13 flottant |
| DAP LM76003 | **30 trous Ø0,3 mm**, 15 pour U201 et 15 pour U301 ; procédé via-in-pad/anneau réel/stencil encore **À valider** |
| DRC natif final | **0 violation**, **0 connexion non routée**, **0 différence de parité** dans le rapport ; résultat selon configuration, aucun verdict fabricant |
| Audit des catégories ignorées | Cinq catégories ignorées dans le rapport natif : courtyard manquant, extrémité piste non centrée sur via, tuning géométrique, filtres empreinte/symbole et type de composant/pads ; ces cinq catégories ont ensuite été réactivées dans une copie isolée, sans changement du projet courant : [audit complet](../hardware/electronique/cartographe/carte_avionique/verification/drc_controles_reactives_20261002.json), zéro violation/connexion et aucun contrôle ignoré |
| Assemblage candidat | CSV 151 références / 141 pièces candidates : 136 SMD + 5 THT, huit DNP, deux pastilles test sans pièce ; aucune différence empreinte/DNP/face/exclusions relevée par comparaison avec le PCB routé |
| Qualification | **0 essai matériel** ; les 13 protocoles du §12.7.11 ont critères proposés et mesures attendues, **0 critère approuvé** à ce stade |


La [revue indépendante du routage final](../hardware/electronique/cartographe/carte_avionique/verification/revue_routage_complet_20261002.json)
contrôle la continuité géométrique des bus de charge après reprise des
étranglements 12V_COMPUTE et 5V_AUX vers F102. Des chemins de puissance
dédiés sont présents ; les branches fines vers le feedback restent des
prises de mesure. Ce contrôle CAO candidat utilise 1,8 mm pour les chemins
calcul/LiDAR/auxiliaires vers les charges et 0,6 mm pour la radio.
Il ne qualifie pas le courant disponible : cuivre fini garanti, chutes,
pertes, densité de courant locale et températures attendent DFM et banc.


La fin de connectivité et le DRC ne démontrent ni courant admissible,
chute de tension, stabilité, SOA, température de jonction ni CEM.
Le plan §12.7.11 s'applique à la révision réellement fabriquée/assemblée :
alimentation limitée et charges fictives d'abord, puis charges réelles,
thermique SA03 et préconformité CEM selon les portes du §2.

Le [manifeste des exports provisoires](../hardware/electronique/cartographe/carte_avionique/fabrication/export_manifest.json)
relie les fichiers de
[fabrication provisoire](../hardware/electronique/cartographe/carte_avionique/fabrication/exports_provisoires_20261002/)
au PCB final contrôlé. Ces exports sont un brouillon à vérifier par
le fabricant/assembleur, avec inventaire perçages, stack, contraintes et
BOM candidate du §12.7.12. Ils n'autorisent aucune commande.
Les empreintes du manifeste et du registre de BOM assemblage désignent
l'instantané **final candidat** du PCB et des sources exportées ; les champs
BOM/empreinte/DNP utilisés par ce CSV sont rapprochés du PCB routé.
Cet instantané reste distinct d'une release fabricant approuvée.

**Fabrication toujours non conforme / incomplète :** TVS, fusibles et Icc
batterie/protection W08, SOA/appel, Ceff et fermeture de boucle, interfaces
OEM et absence de réalimentation, métrologie RP4TD, **44 MPN à monter
encore absents**, cohérence MPN/labels, cuivre fini/stack et tolérances,
anneaux outil/métallisation, remplissage/cap des vias sous pads, stencil,
inspection des joints et revue DFM finale restent ouverts.
Les sorties provisoires ne ferment aucune de ces gates par leur seule
existence. Aucun essai électrique/thermique/CEM, fabrication, assemblage,
montage réel, vol ou pulvérisation n'a été réalisé par ce lot.


### 12.7.14 Revue native de montage de la stack, 3 octobre 2026

Périmètre : `MEC-AVI-001 / MEC-INT-001 / CARTE-010`, CAO nominale
Windowsamd64, KiCad10.0.6 et FreeCAD1.1.3. Le dessinHolybro transmis
par l'utilisateur définit126×80, quatreM3, entraxes120×74 et pieds8mm.
Les images sources et le STEPOEM inchangé sont associés à leurs empreintes.
Le générateur crée9natifs distincts, conserve283entrées sources et reprend
CA01courante :308solides composants,50perçages de pads paramétriques,
conversion explicite du substratSTEP1,46 vers enveloppePCB1,6mm.

| Exigence | Test / critère numérique | Preuve |
|---|---|---|
| MEC-ARC-001 / CARTE-010 | T-STACK-REVUE-NATIF : sources inchangées, liens résolus, recalcul sansInvalid, poseZnative−54,3746, arbrePCBconservé | [construction](../hardware/mecanique/cartographe/verification/construction_stack_revue_20261003.json) et [contrôle](../hardware/mecanique/cartographe/verification/controle_stack_revue_20261003.json) |
| MEC-AVI-001 / MEC-INT-001 | T-STACK-REVUE-GEOM : volumes communs des éléments ajoutés et obstacles représentés ; contact filetéOEM déclaré distinctement, coaxialité et chaîne d'appui | [audit](../hardware/mecanique/cartographe/verification/audit_mecanique_stack_20261003.json), contrôle et [revue indépendante](../hardware/mecanique/cartographe/verification/revue_independante_stack_20261003.json) |
| MEC-AVI-001 | Accès : outil axial sous les quatre vis ; ne doit pas être présenté accessible avec bloccapteurs monté | audit : obstacleP16 ; déposeSA05A requise pour montage/maintenance |

La propositionCHC sous la plaque est rejetée pour intersectionP17.
La variante montée utilise4colonnesG1024mm,4appuisG102mm et4visM3×65
sousP17 avec rondelles ; elle partage la fixationP17/plaque/stack.
P56 remplace la plaque basse par une dérivée avec quatre trousØ3,2,
sans fraiser le carbone. Engagement nominal5,726mm, marge géométrique
au fond1,274mm ; cela ne garantit pas la profondeur filetée utile.
Le recalcul teste aussi la pose enregistrée, pour détecter une coordonnée
négative ramenée àzéro par un type de propriété inadapté.

Résultat final du contrôle en processus neuf : réouverture/recalcul sans
objetInvalid, pose native correcte, volume communHolybro/CA01nul,
aucune intersection détectée des cartes avec les obstacles représentés
aux deux poses, ni des16occurrences de fixation avecCA01/châssis/dock/
capteurs/distribution. Le recouvrement du filetageM3 dans les piedsOEM
est une interface intentionnelle, pas une collision interdite.
L'enveloppeCA01courante laisse2,7546mm au-dessus de la plaque àZ−65,
contre13,38mm dans le montage24/2 ; la facePCB est à24mm de la plaque.
Ces mesures géométriques ne couvrent ni tolérances ni fiches accouplées.

Les rendus sont des capturesFreeCADGui/Coin3D, sans sauvegarde des
natifs : [preuve d'export](../hardware/mecanique/cartographe/verification/rendus_stack_revue_20261003.json).
Recettes : `extract_stack_drills_20261003.py` avec PythonKiCad,
exportKiCadSTEP `--user-origin50x50mm --no-dnp`,
`build_stack_revue_20261003.py`, puis `verify_stack_revue_20261003.py`
dans un processus neuf et macro `rendus_stack_revue_20261003.FCMacro`.
Le manifeste référence cette variante inactive ; ancienne maquette et
faisceau restent de périmètres différents.

Conclusion **préliminaire / À valider**, CAO **Implémenté**.
Non exécutés : métrologie de lot, couple/précharge, compression/fluageP17
etG10, résistance/vibrations, masse réelle, isolement tiges/carbone/PCB,
accouplement/traction/rayons des cordons, course avec nouveau faisceau,
thermique, montage réel etvol. La dépose nécessaire des capteurs et la
libérationP17 lors du desserrage font partie des contraintes de conception.

### 12.8 Synchronisation GNSS, Airy, Basler et Pixhawk

`T-AIRY-SYNC-01` couvre `MAP-FUN-001`, `ELEC-TIM-001`, `CARTE-009` et
`SW-TIM-001`. La cible
**Planifié / À valider** conserve le GNSS RTK sur CAN2 du Pixhawk,
alimente l'Airy en temps GNSS physique et confie la décision de capture à
la Jetson/ROS 2 ; PX4 génère l'impulsion Basler à sa demande.
`SYNC_OUT1` Airy reste une variante : son impulsion d'angle est
documentée, mais ses caractéristiques électriques et sa latence ne le
sont pas. Sources : *Airy User Guide* v1.3 (pages PDF 15–17, 22–24
et annexe A.2.3), documentation fabricant du H-RTK, de la baseboard
Holybro et de la Basler `a2A4096-30ucBAS`. Consigner références,
révisions et firmwares réels avant le banc.

0. **Préparation de la commande et de l'autorité de capture.** Inspecter
   les interfaces et vérifier en simulation le chemin
   `mission_manager -> sensor_manager -> adaptateur PX4 -> camera_trigger`,
   son transport local et les commandes supportées par le firmware.
   Préparer les scénarios demande ponctuelle, refus, réponse perdue, demande périmée,
   doublon, reprise et commande concurrente QGroundControl/mission PX4.
   Leur exécution matérielle est réservée à l'étape 3, après les contrôles
   hors tension, électriques et temporels des étapes 1–2 et la validation
   du niveau de simulation précédent ; aucun déclenchement matériel à cette étape.
   Vérifier une seule autorité active et l'absence de répétition aveugle
   lorsque l'issue précédente est indéterminée ; caractériser les ordres
   déjà en transit lors d'un arrêt. Rapprocher session/demande, acceptation,
   impulsion, exposition et image : aucun ACK ne vaut preuve de capture,
   aucun échec ou doublon ne reste silencieux. Vérifier que GNSS/IMU/LiDAR
   restent continus sans commande de nouvelle mesure par photo.

1. **Allocation hors tension.** Vérifier la variante H-RTK F9P Helical
   DroneCAN reçue : UART2 pin 5 PPS sur STM32G4, mais NC sur S32K1
   selon Holybro. Identifier SKU/révision et, si accessible, relever le
   chemin TIMEPULSE jusqu'au connecteur et un éventuel tampon ; contrôler
   la continuité des conducteurs hors tension. Les niveaux, impulsions,
   GPRMC et la coexistence CAN2 se mesurent sous alimentation à l'étape 2.
   Confirmer la sortie AUX Pixhawk dédiée au trigger,
   distincte des sorties de propulsion, et l'entrée AD&IO `FMU_CAP1`
   réservée au retour d'exposition. Relever les broches sur la
   baseboard réelle. Helical et allocation des ports restent
   **À valider**.
2. **Temps GNSS distribué par CA01.**
   Après les contrôles hors tension, alimenter normalement le GNSS avec
   Airy/CA01/Orin déconnectés de sa sortie PPS. Mesurer UART2 pin5 par
   rapport à pin6 GND à l'oscilloscope, sonde haute impédance ×10, sur
   plusieurs périodes : niveaux haut/bas, dépassements, polarité, largeur
   et fronts. Relever alimentation, charge, référence/révision du module,
   configuration TIMEPULSE et validité du temps GNSS. L'hypothèse 3,3 V de
   DOC-ELEC §8.1 reste **À valider** ; le +5 V pin1 n'est pas une preuve
   du niveau PPS et une moyenne au multimètre ne suffit pas.
   Avant raccordement, caractériser la charge de l'entrée CA01 candidate,
   puis répéter les mesures avec cette charge admissible et sur ses
   sorties : la tension nominale seule ne prouve pas la marge électrique
   vers l'Airy. Archiver traces, conditions et comparaison aux seuils.
   Avant d'admettre GPRMC comme source, relever les deux firmwares F9P/nœud
   DroneCAN, la configuration UART2/NMEA/RMC, le préfixe accepté par l'Airy,
   le débit et la persistance après redémarrage et autoconfiguration.
   Mesurer aussi TX UART2 pin3 par rapport à pin6, source sans charge
   externe puis sous charge CA01 admissible : niveaux haut/bas, repos,
   polarité, fronts et débit. L'hypothèse UART logique 3,3 V de DOC-ELEC
   §8.1 n'est pas une mesure ; GPRMC ne définit pas un niveau électrique.
   Choisir l'interface de décodage après cette mesure : USB-UART logique
   3,3 V et USB-RS232 ne sont pas interchangeables. Capturer les octets
   RMC, vérifier `$GPRMC` / talker GP, checksum, date UTC et statut A,
   9600 bauds 8N1, cadence et fenêtre par rapport au PPS. Ne pas supposer
   `$GNRMC` accepté sans preuve. Tester la persistance avec CAN/PX4 et
   RTCM actifs, sans écrasement par la configuration du nœud.
   Avant connexion à l'Airy, identifier son interface réelle et contrôler
   la sortie du convertisseur CA01 candidat : niveaux RS232, repos et
   polarité, puis égalité des octets avant/après conversion et absence
   de perte/framing error. Le tableau3 du guide Airy spécifie RS232 ; la
   mention TTL 3,3 V du dépannage ne qualifie pas une connexion directe.
   Contrôler ensuite `GPRMC Status`, `PPS Status` et `Time Sync Status`
   ainsi que les timestamps décodés. Une réception série seule ne prouve
   pas une association correcte GPRMC/PPS ; ne pas reporter le niveau
   RS232 sur la branche RX logique de l'Orin.
   Appliquer aussi la recette physique du§12.7.2 : relever les rails
   3V3_SYNC/5V_AIRY_IO et la référenceCamera22/GND1 surJ509, confirmer
   qu'elle suit les domainesGPIO/UART de l'Orin, puis mesurer les
   scénarios GNSS, CA01, Airy et Orin successivement éteints/redémarrés.
   Archiver tensions résiduelles et courants de retour ; ne pas assimiler
   Ioff du traducteur à une preuve de non-réalimentation de l'appareil.
   Commencer avec R530–R533 DNP ; n'autoriser leur montage sur banc
   qu'après caractérisation des niveaux, charges et interfaces.
   Pour une alternative Serial Forwarding : vérifier le nœud, le port
   interne et le chemin CAN réellement utilisé (proxy PX4 ou accès direct
   Jetson), puis les octets NMEA effectivement émis, le verrouillage du
   port, les délais/pertes sous charge et la coexistence GNSS/RTCM.
   Un accès GUI/u-center seul ne vaut pas preuve d'un flux nominal ; tester
   la continuité sans GUI et la passerelle vers l'Airy. Un tunnel d'octets
   ne remplace pas le PPS physique. Pour une reconstruction RMC depuis
   `Fix2`, conserver la provenance et valider époque, validité, préfixe,
   checksum et association PPS ; ne pas la présenter comme NMEA extrait.
   Dans la voie directe, mesurer PPS source et sorties
   tamponnées/protégées vers Airy pin 9 et une entrée GPIO/PPS
   compatible de l'Orin. Pour l'Airy : PPS positif de 3–15 V,
   largeur 20–200 ms, période 1 s ± 200 µs. Acheminer GPRMC
   UART2 vers Airy pin 11 par adaptation RS232 et, si le port
   UART debug Orin est libre et approprié, vers lui par une
   voie tamponnée distincte. Vérifier l'interface réelle selon les preuves
   ci-dessus, 9600 8N1, statut A, émission
   après front descendant PPS et fin 300–500 ms avant le front
   montant suivant. Interdire Y passif, retours de courant
   vers le vol et branchement direct non vérifié.
3. **Déclenchement et exposition.** Configurer Pixhawk AUX puis
   adaptation CA01 vers l'entrée optocouplée Basler `Line1`
   M8 pin 2, retour opto pin 3. Mesurer largeur, polarité et
   courant (>5 mA requis pour l'opto). Configurer Basler `Line2`
   en `ExposureActive` ; sortir par M8 pin 4 avec masse GPIO
   pin 6, entrer sur CA01 avec rappel/protection adaptés à sa
   sortie collecteur ouvert, puis rejoindre AD&IO `FMU_CAP1`
   pin 2 et GND pin 8 après contrôle du brochage de la
   baseboard réelle. Mesurer ensemble commande AUX, front
   Line1, début/fin d'exposition et événement `camera_capture`
   PX4. L'ordre de déclenchement ne remplace pas la mesure
   de l'exposition effective.
4. **Association et incertitude.** Acheminer les événements PX4
   vers Jetson par la liaison compagnon interne TELEM2 ; mesurer
   délai et pertes. Associer chaque capture, impulsion
   `ExposureActive` et image USB3 par séquence, `Frame ID`,
   chunks `Timestamp Value` et `Exposure Time`. Relever
   `FrameTriggerMissed`, overflow, doublons et images sans
   événement. Contrôler `Time Sync Lock` Airy et ses temps UTC
   dans les paquets/points décodés. Comparer références
   GNSS/CAN2, PX4, Jetson/PPS et Airy, puis estimer offset,
   dérive, jitter, latence caméra et incertitude de pose
   interpolée au milieu de l'exposition. Une résolution
    d'horodatage ne prouve pas la précision absolue.
   Inclure la demande Jetson dans la table de correspondance ; démontrer
   l'association à la séquence PX4 sans supposer son identifiant transmis
   sur AUX. Mesurer le délai entre demande et exposition et corriger la
   latence du retour ExposureActive. Injecter retard/réordonnancement des
   paquets et vérifier que le temps d'acquisition et les mesures sources
   restent identiques ; refuser les associations ambiguës ou les fenêtres
   sans historique suffisant. Vérifier la convention des temps GNSS et
   l'association GPRMC/PPS, indépendamment du statut RTK fixe.
5. **Défauts et reprise.** Répéter démarrage, reset des
   capteurs/Jetson, perte et retour PPS, GPRMC, RTK, CAN2,
   liaison compagnon et capture. Vérifier Lock/Unlock, rejet
   des données sans temps fiable, alertes, absence de
   déclenchement fantôme ou manqué et réaction PX4.
   Une défaillance CA01 ou de synchronisation ne doit pas
   altérer les boucles critiques du vol ; les défauts de
   puissance ont leurs essais dédiés.

`FMU_CAP1` ne mesure pas simultanément `ExposureActive` et un PPS
distinct. Un PPS vers Pixhawk demande une autre entrée de capture
disponible et un pilote PX4 compatible : cette prise en charge de
la Holybro 6X n'est pas établie dans le build standard. Ne pas déclarer
son horloge disciplinée par PPS. Si la précision UTC commune exigée
dépasse celle mesurée, qualifier une deuxième capture ou revoir la
stratégie de temps. PTP/gPTP Airy et `SYNC_OUT1` seront comparés
ultérieurement après caractérisation du maître, du réseau et du signal.

Approuver avant banc les seuils chiffrés d'erreur temporelle
LiDAR–image–pose, jitter, dérive, taux d'appariement, pertes et durée
de reprise, avec répétitions et critères de refus. Conserver schéma
annoté, configurations, captures d'oscilloscope, journaux PX4/Jetson/Airy,
paquets, images et table `Frame ID → exposition → capture PX4 → UTC Airy`
dans une preuve de banc identifiée. Arrêter sur niveau hors enveloppe,
échauffement, reset du domaine vol ou datation inexpliquée.
**Aucun essai matériel n'a été exécuté ; conclusion : Planifié / À valider.**

## 13. Matrice de traçabilité synthétique

| Exigence | Composant / algorithme | Test | Résultat / preuve | Statut |
|---|---|---|---|---|
| CAB-CARTO-001, MEC-INT-001 | skill electromechanical-integration, planificateur C++17, contrôles BRep, copies isolées et résolution des inconnues | T-SKILL-EMI-01 ; T-SKILL-EMI-02 | §12.1.11 ; [preuve initiale](verification/electromechanical_integration.json), [autonomie](verification/electromechanical_autonomy.json) | **Implémenté**, tests synthétiques ; autonomie générale, faisceau réel et physique **À valider** |
| CAB-CARTO-001, MEC-INT-001 | Moteur de banc, référentiel gelé, extraction FreeCAD, mesures natives des retenues et poses, rétrovalidation et contre-validation historique ciblée | T-EM-ENGINE-01, T-EM-ENGINE-02, T-EM-ENGINE-03 | [§12.1.13](#validation-moteur-electromecanique), [GO 1](verification/electromechanical_engine_go1.json), [GO 2](#qualification-moteur-go2) | Bancs et contrôles ciblés **Implémenté**, intégration du prototype **À valider** |
| CAB-CARTO-001, MEC-INT-001 | Matrice d’interconnexion et contrôles du cartographe sur copies | T-EM-ENGINE-04 | [Action 3](#cartographe-action3) | Contrôles ciblés **Implémenté**. Architecture candidate **À valider**. |
| CAB-CARTO-001, MEC-INT-001, METH-001 | Audit du moteur et des sources, rapprochement des axes, contrat V2 et régressions sur banc | T-EM-ENGINE-L0 | [L0](#moteur-electromecanique-v2-l0), [preuve](electromechanical_v2/TEST_RESULTS.json) | Audit **Implémenté**, `L0_READY` pour engager L1. Intégration et GO 3 **À valider**. |
| CAB-CARTO-001, MEC-INT-001, METH-001 | Recherche documentaire par `issue_id`, vérification des références, calcul conditionnel et cache | T-EM-ENGINE-L1 | [L1](#moteur-electromecanique-v2-l1), [preuve](verification/technical_research_l1.json) | Moteur **Implémenté**, `L1_PASS` sur Windows amd64. Applicabilité matérielle des inconnues **À valider**. |
| CAB-CARTO-001, MEC-INT-001 | Catalogue, graphe de continuité, repères, enveloppes et réconciliation des sources | T-EM-ENGINE-L2 | [L2](#moteur-electromecanique-v2-l2), [preuve](electromechanical_v2/L2_RESULT.md) | `L2_CONDITIONAL`. Banc numérique **Qualifié** pour le cas à quatre contacts. Prototype **À valider**. |
| CAB-CARTO-001, MEC-INT-001, METH-001 | Diagnostic L3, alternatives, fonctions, consolidation et Pareto | T-EM-ENGINE-L3 | [L3](#moteur-electromecanique-v2-l3), [preuve](verification/architecture_decision_l3.json) | **Implémenté**, `L3_PASS` sur bancs synthétiques Windows amd64. Prototype **À valider**. |
| CAB-CARTO-001, MEC-INT-001, METH-001 | Validation indépendante V1 à V6 et contrôle des preuves natives | T-EM-ENGINE-L4 | [L4](#moteur-electromecanique-v2-l4), [preuve](verification/electromechanical_validation_l4.json) | **Implémenté**, `L4_CONDITIONAL`. 100 attentes sur 100 satisfaites. Architecture complète et essais physiques **À valider**. |
| CAB-CARTO-001, MEC-INT-001, METH-001 | Convergence, sélection, rollback et validation indépendante de la fusion | T-EM-ENGINE-L5 | [L5](#moteur-electromecanique-v2-l5), [preuve](verification/electromechanical_convergence_l5.json) | **Implémenté**, `L5_PASS` sur banc statique Windows amd64. Périmètre de reprise dans [GO2bis](#qualification-moteur-go2bis). |
| CAB-CARTO-001, MEC-INT-001, METH-001 | Lots L0–L5 corrigés, gel, couverture, diagnostics historiques, fusion et chaîne de preuve | T-EM-ENGINE-GO2BIS | [Résultat](#qualification-moteur-go2bis), [matrice et preuves](verification/GO2BIS_QUALIFICATION.md) | GO conditionnel sur bancs Windows amd64. Fusion XLink, rattachement électrique au natif et matériel **À valider**. |
| CAB-CARTO-001, MEC-INT-001, METH-001 | Architecture du prototype sans dock et validation des interfaces | T-CARTO-GO3A | [Résultat](#cartographe-go3a), [critères](verification/go3a/GO3A_REQUIREMENTS.yaml) | Dossier **Implémenté**. H-01 **À valider**, GO3B suspendu aux données et contrôles critiques. |
| CAB-CARTO-001, MEC-INT-001, METH-001 · G3A-01 à G3A-08 | Admission du dossier H-01, interconnexion L2, natifs XLink et portée du validateur L4/L5 | T-CARTO-GO3B-ADM | [Résultat](#cartographe-go3b), [preuve](verification/go3b/GO3B_ADMISSION.json) | `NO_GO_MOTIVE` à l’admission. Couverture documentaire vérifiée. Reconstruction et rétrovalidation `NOT_RUN`. |
| CAB-CARTO-001, MEC-ARC-001, MEC-INT-001, METH-001 · G3A-01 à G3A-08 | Construction native des trois familles et consolidation avec contre-validation indépendante | T-CARTO-V21-GO3B | [Résultat](#cartographe-go3b-reconstruction), [preuves](verification/v21_go3b_validation.json) | `GO3B_CAO_NO_GO_MOTIVE`. Six variantes sauvegardées, une consolidée de diagnostic et défauts mesurés. Montage et GO4 **À valider**. |
| CAB-CARTO-001, MEC-INT-001, V3-A1-01 | Confrontation des autorités UART, réouverture XLink sur copies et contrôles d’admission L5 | T-CARTO-V3-A2-EVIDENCE, T-CARTO-V3-A2-NATIVE | [Résultat](#cartographe-v3-a2). `V3_A2_EVIDENCE_CONDITIONAL`, huit issues ouvertes, mutation cartographe suspendue. |
| CAB-CARTO-001, MEC-INT-001, V3-A1-01, V3-B1-01 | Dossier UART, réouverture XLink, contrôles L5 et collecte hors tension | T-CARTO-V3-A3-AUTH | [Résultat](#cartographe-v3-a3). V3_A3_EVIDENCE_CONDITIONAL, douze mutations bloquées et collecte physique À valider. |
| CAB-CARTO-001, MEC-INT-001, V3-A1-01, METH-001 | Collecte opérateur, contrôle des paquets de preuve et refus L5 avant construction | T-CARTO-V3-A4-IMPORT, T-CARTO-V3-A4-REGRESSION | [Résultat](#cartographe-v3-a4), [preuves](verification/v3/a4/acceptance.json) | `V3_A4_EVIDENCE_CONDITIONAL`, domaine et revue habilitée **À valider**. |
| CAB-CARTO-001, MEC-INT-001, V3-A1-01, V3-B1-01, METH-001 | Jonction de la recherche sur banc, de la contre-validation et de l’import des preuves | T-CARTO-V3-INT1 | [Résultat](#cartographe-v3-int1), [verdict calculé](verification/v3/int1/acceptance.json) | `V3_INT1_GO`, jonction **Qualifié** sur banc synthétique Windows amd64. Réception et autorité physique **À valider**. |
| CAB-CARTO-001, MEC-INT-001, V3-B1-01 | Transaction à deux câbles, appui scellé, classification des contacts et mesure après réouverture | T-CARTO-V3-C2 | [Résultat](#cartographe-v3-c2), [revue](verification/v3/c2/independent_review.json) | `V3_C2_MULTIHARNESS_ENGINE_GO` sur banc synthétique. Applicabilité au cartographe **À valider**. |
| CAB-CARTO-001, MEC-INT-001, V3-A1-01, METH-001 | Import A.4, registre et revue authentifiés, préadmission L5 | T-CARTO-V3-A5-AUTHORITY | [Résultat](#cartographe-v3-a5), [refus](verification/v3/a5/adversarial.json) | `V3_A5_AUTHORITY_PIPELINE_GO` en `TEST_ONLY`. Autorité réelle **À valider**. |
| CAB-CARTO-001, MEC-ARC-001, MEC-INT-001, METH-001 · G3A-01 à G3A-08 | Portefeuille GO3A V2.1, sources XLink/L2, recherche L1, comparaison L3 et préflight C | T-CARTO-V21-GO3A-PORTFOLIO | [Résultat](#cartographe-go3a-revise), [contrats et preuves](verification/v21_go3a_candidates.json) | Préflight **Implémenté** sur trois demandes. Construction, mesures des candidats et réception **À valider**. |
| CAB-CARTO-001, MEC-INT-001 · G3A-01 à G3A-08 | Inventaire et catalogue L1, plan cavité/broche L2, rapprochement GO3A/GO3B et observation FreeCAD des occurrences | T-CARTO-V21-CONNECTORS | [Résultat](#preuve-connectique-v21), [preuve](verification/v21_connector_tests.json) | `V21_CONNECTORS_CONDITIONAL` sur Windows `amd64`. Réception réelle **À valider**. |
| CAB-CARTO-001, MEC-ARC-001, MEC-INT-001 · G3A-01 et G3A-08 | Résolution d’occurrences, fermeture isolée, calcul BRep par lots et validation L4 | T-CARTO-V21-XLINK | [Résultat](#preuve-xlink-v21), [preuve](verification/v21_xlink_coverage.json) | `V21_XLINK_CONDITIONAL` sur Windows `amd64`. Réception du montage **À valider**. |
| CAB-CARTO-001, MEC-ARC-001, MEC-INT-001 · G3A-01 et G3A-08 | Validateur L4 scellé, couverture BRep des paires, exclusions AABB et réouverture | T-CARTO-V21-XLINK-B2 | [Résultat](#qualification-xlink-v21-b2), [preuve](verification/v21_b2/coverage.json) | `GO_B` sur Windows `amd64`. Cartographe nominal **non conforme** sur les sept intersections. |
| CAB-CARTO-001, MEC-ARC-001, MEC-INT-001, METH-001 · G3A-01 à G3A-08 | Préflight, connectique L2, validation XLink L4 et convergence L5 | T-CARTO-V21-QUAL · Q1 à Q5 | [Résultat](#qualification-integree-v21), [preuve](verification/v21_qualification_results.json) | `V21_EXPLORATION_NO_GO` pour l’intégration, sur Windows `amd64`. Conditions de reprise et démonstrations locales tracées. |
| CAB-CARTO-001, MEC-ARC-001, MEC-INT-001, METH-001 · G3A-01 à G3A-08 | Admission H-01, L2 et L4 XLink, réimplantation L5, témoins historiques | T-CARTO-V21-FIX-C · C0 et Q1 à Q5 | [Requalification](#requalification-v21-c), [reçu](verification/v21_fix_c_qualification.json) | `GO_CONDITIONNEL_V21_CORRECTIF` sur Windows `amd64`, périmètre numérique borné. |
| CAB-CARTO-001, MEC-INT-001, EM-INT-01/02, EM-GEO-01/02, EM-COL-01/02, EM-GRP-01 | Registre de connectivité et SA07 de la copie de refonte | Export KiCad, fermeture XLink, comparaison BRep nominale, mobilité discrète | [§12.1.12](#validation-refonte-faisceaux), [variantes et couverture](../hardware/mecanique/cartographe/verification/refonte_faisceaux/validation_variantes.json) | Candidat **Implémenté** sur copie, neuf définitions embarquées et intégration physique **À valider** |
| CAB-CARTO-001, MEC-INT-001, EM-INT-01/02, EM-GEO-01/02, EM-COL-01/02, EM-GRP-01 | SA07 modulaire, P60/P64/P68 et supports locaux | Fermeture XLink, recalcul à cache vidé, intersections BRep et inclusion F38 | [§12.1.12](#validation-faisceaux-modulaires) | Architecture **Implémenté** sur copie, maintien, montage et qualification physique **À valider** |
| MEC-ARC-001 | dérivation CAO, collisions, SDF/allocation | T-CARTO-GZ-01 | §§9.3 et 10.2 ; geometry_tests.json, model_checks.json, campaign_20261024.json et station_gazebo_bridge.json via manifeste | **Implémenté**, contrôles numériques, chargement et allocation effective réussis ; fidélité physique **À valider** |
| UI-GZ-001 | service GazeboExportService, backend local et page Modèle 3D ; UI/CLI communs | test_gazebo_export, test_gazebo_model_page, navigation et chargement Gazebo | §10.2 ; [preuve logicielle](verification/station_gazebo_bridge.json) | **Implémenté**, conversion réelle, annulation et publication contrôlées ; Windows amd64 ; import générique **Planifié** |
| MEC-MAS-001 | bilan des inclusions et agrégateur C++17 | T-CARTO-GZ-02 | §9.3 ; mass_ledger.json / test_mass_properties | logiciel testé ; masse/CG/inerties réels **À valider** |
| SAFE-REQ-001/002, ELEC-PWR-002 | airframe et runner borné | T-CARTO-GZ-03 | §9.3 ; campaign_20261024.json, six T0 et revue indépendante | carré, perte Offboard et annulation réussis sur x500/cartographe synthétique ; saturation observée ; qualification physique **À valider** |
| ELEC-PWR-002, SYS-FUN-006 | propulsion proxy, auxiliaires, batterie Thévenin | T-CARTO-GZ-04 | §9.3 ; energy_checks.json et T0 t0_energy | hors ligne **Implémenté**, préliminaire ; couplage/précision **À valider** |
| METH-001 | cadre HLD, AGENTS, INDEX et documents de domaine | T-METH-01 ; §15 | [preuve d'intégration](verification/audit_preceptes.json), 22 principes couverts et 17 fiches | méthode **Implémenté** ; écarts techniques et conformité globale **À valider** |
| `SYS-FUN-001` | pont d'état PX4–ROS 2 | topics, diagnostics, SITL | odométrie observée ~100 Hz | conforme au banc SITL |
| `SYS-FUN-004` | runner Offboard + PX4 | carré 2 m | quatre segments et posé | conforme au banc SITL |
| `SAFE-REQ-001` | frontière PX4/ROS 2 | revue des interfaces et runners | aucun topic actionneur direct | conforme au lot A |
| `SAFE-REQ-002` | failsafe PX4 | coupure réelle des consignes en SITL | `AUTO_LAND` en 1,099 s puis posé | conforme au banc SITL |
| `SYS-FUN-007/008/009`, `SAFE-REQ-010`, `ELEC-LNK-001/002` | PX4, mission, RF commun et QGC | `T-RF-01..06`, §9.1 | présélection documentaire ; aucune exécution RF | **Planifié / À valider** |
| `SW-RTK-001`, `SYS-FUN-009`, `ELEC-LNK-001/002/003` | H-RTK F9P Base retenue, rover patch réévalué au profit du candidat Helical DroneCAN STM32G4, QGC, Backpack, ELRS/RP4TD, PX4 | `T-RF-06`, §9.1 : RTCM + commandes ponctuelles + RC + télémétrie | choix rover temporel et débit, marge, reprise RF non mesurés | **Planifié / À valider** |
| `MAP-FUN-009` | planification et suivi de couverture | `T-MAP-COV-01`, §9.1 | aucun résultat de couverture de parcelle qualifié | **Planifié / À valider** |
| `QUAL-REQ-001` | Docker, contrats et runners | builds, CTest, smokes | PC/`amd64` conforme ; cible **À valider** | partiel |
| `SYS-FUN-006`, `SAFE-REQ-001/002`, `QUAL-REQ-001` | socle PX4/Gazebo et premier monde VB01 | reprise carré/perte Offboard puis VB01 exploratoire ; [§9.2](#demarrage-gazebo), GZ-01..04 | évaluation des sources et preuves historiques ; aucun nouveau rejeu | travaux **Planifiés**, révision courante et critères agricoles **À valider** |
| `LOC-001` | FAST-LIO2 | BotanicGarden complet à `1×` | 5 762 scans, ATE 0,35916 m | baseline PC préliminaire |
| `LOC-002` | LIO-SAM | BotanicGarden complet à `1×` | meilleure orientation/RPE, coût supérieur | candidat précision |
| `DATA-FB-001` | recette FriûlBot | contrôle MD5 bag et images | empreintes conformes | conforme |
| `DATA-FB-002` | allowlist et manifeste | identité prédiction sans références | GNSS/odom exclus | conforme |
| `FUS-FB-001` | association LiDAR–caméra | 638 déclenchements / 638 jeux | structure cohérente | conforme structurellement |
| `MAP-FB-001` | détection locale de rangs | capture réelle +120 s | trois rangs | préliminaire **À valider** |
| `SW-MAP-002` / `MAP-GLOBAL-001` | ICP, triangulation angulaire et fusion voxelisée | tests algorithmes, contrats et parcours surface réel | 23 scans, 61 903 faces ; `.runtime/scan-surface/` | implémenté, précision et collision **À valider** |
| `EVO-001` | cibles CMake et services | contrôles de dépendances et CTest | conforme sous Windows | Linux/ARM **À valider** |
| `UX-002` | navigation et pages Qt | routes, retour et contexte | réussi sous Windows | cible **À valider** |
| `CARTE-001..012` | carte avionique CA01 | `T-CA01-01..12`, §12.2 et §12.7.1–12.7.13 ; E01..E06/TH01..03/CEM01..04 | 230 invariants et 44 contrôles analytiques ; ERC0/0 ; routage complet quatre couches, 1 255 segments / 251 vias, continuité large CAO candidate, DRC0/parité0/connexion0 selon configuration ; 13 protocoles / 0 banc | schéma/routage **Implémentés** ; matériel **À valider**, fabrication non conforme/gates ouvertes |
| CAB-CARTO-001, CARTE-002/004/006/007/010/011, ELEC-PWR-001/002 | baseboard Holybro, Pixhawk 6X, PM08-CAN, PDB Holybro 300 A top-entry candidate, W08/CA01 et Jetson Orin NX 16 Go ; cible V0.5 | T-CARTO-SYS-CAB/GEOM, §12.1.4 ; T-PM-V05-01..06 et T-PDB-V05-01, §12.7 | 33 Wxx recensées, 35 réservations CAO ; passages ouverts ; aucun faisceau physique ni essai électrique V0.5 exécuté | registre et maquette **Implémentés** ; matériel **À valider** |
| MEC-ARC-001, MEC-AVI-001, MEC-MAS-001 | variante système 20 Ah inactive, BOM et faisceau candidats | T-CARTO-SYS-NATIF/GEOM/MAS, §12.1.4 | nouveaux natifs/liens et sources préservés ; fixations, rayons, passages et masse totale non validés | **Implémenté** en maquette ; intégration **À valider** |
| MAP-FUN-001, ELEC-TIM-001, CARTE-009, SW-TIM-001 | Jetson mission_manager/sensor_manager et adaptateur PX4 ; H-RTK Helical DroneCAN candidat, PPS/GPRMC via CA01 vers Airy/Orin, trigger AUX Pixhawk, Basler ExposureActive vers FMU_CAP1 | T-AIRY-SYNC-01, §12.8 ; T-CA01-09, §12.2 | responsabilités clarifiées ; commande, signaux, datation et association non qualifiés ; PPS Pixhawk non acquis | **Planifié / À valider** |
| `HW-BAT-SWAP-01..06` | cassette historique, berceau fixe candidat et option interplateaux | CAO `T-BAT-CAO-01..04`, préétude interplateaux, puis inspection, efforts, cycles et défauts | DOC-MEC §4.1.1–4.1.2 et §12.1.1–12.1.2 ; géométrie préliminaire distincte des essais physiques | qualification physique **À valider** |
| MEC-ARC-001, MEC-BAT-001 | batterie67 mobiles, récepteur72 fixes et principal6 SA+6 pièces | T-CARTO-HIER-BAT-01, §12.1.10 | parentage12, multiensemble149, poses/apparences/sources conservées ; extraction0/50/500 unique ; registres182/115 sans doublon | CAO **Implémentée**, contrôle numérique réussi ; physique **À valider** |
| SAFE-REQ-011, ELEC-BMS-001 | BMS solidaire de cassette et connecteur d'échange candidat | T-CARTO-BMS-01..06, §12.1.9 | CAO JBD/TE et schéma40liaisons implémentés ; charge/thermique/isolation/logiciel/cycles à valider, aucun essai matériel | CAO/schéma **Implémentés**, physique **À valider** |
| MEC-ARC-001, MEC-BAT-001 | étage énergie et raccordement direct candidat AWG8/742F5 M5 au TE | T-CARTO-ETAGE-DIRECT-01, §12.1.8 | liens/rayons/implantation/collisions/extraction du pack nominal contrôlés ; enveloppe d'étude, lot et fixations **À valider** | CAO **Implémenté**, préliminaire |
| MEC-ARC-001, MEC-BAT-001 | dock historique coloré et cordons fixes repliés | T-CARTO-DOCK-COULEURS-01 / COMPACT-01, §12.1.7 |181 liens,629 BRep préservés hors2cordons, course+X séparée17,17mm, hauteur−29,3% ; intersectionP49 ouverte | CAO **Implémenté**, conclusion préliminaire, physique **À valider** |

<a id="recentrage"></a>
## 14. Actions de qualification ouvertes

### ORCH-CAO-MASSE-1 — priorité du 25 octobre 2026

La complétude géométrique et massique du prototype actif précède désormais
les études de vol, de consommation et d'autonomie. Les nouvelles capacités
et campagnes Gazebo/PX4 sont suspendues ; leurs capacités et résultats
historiques restent conservés. Le cadrage utilisateur autorise des grades et
recettes de fabrication candidats sourcés, sans qualification physique.

La passe couvre une seule configuration sans dock et suit : préservation
récupérable de l'état initial, trois investigations indépendantes, intégration
sous propriétaire unique, contrôles sur fichiers finaux et revue indépendante.
La baseline récupérable est dans `.runtime/orch-cao-masse-1/` ; ce cache local
n'est pas une preuve versionnée de qualification. Les preuves légères du lot
sont conservées sous `hardware/mecanique/cartographe/verification/`.

Critères : couverture quantitative bidirectionnelle des composants physiques,
géométries utiles documentées, masses applicables ou inclusions explicites,
inconnues sans valeur zéro, sommes reproductibles sans double comptage,
interfaces/solides/rotors/faisceaux contrôlés, réouverture dans un processus
FreeCAD neuf, registres et exports cohérents puis revue indépendante.
Une définition encore bloquée ne vaut pas clôture : terminer les travaux
indépendants et préciser le plan fabricant ou la mesure nécessaire.
Aucune campagne ni qualification physique ne découle de ces contrôles.

**Résultat exécuté au 26 octobre — lot non clos.** Les recherches et modèles
ont été réalisés, puis intégrés sous propriétaire unique dans les natifs
existants. La [preuve consolidée ORCH](../hardware/mecanique/cartographe/verification/controle_orch_cao_masse_1.json)
référence les entrées, empreintes, commandes, résultats et anomalies ; la
[revue indépendante](../hardware/mecanique/cartographe/verification/revue_orch_cao_masse_1.json)
en vérifie la portée. Les trois preuves d'investigation décrivent les sources
consultées, les pistes infructueuses et l'information fabricant nécessaire.
Les preuves antérieures modifiées sont conservées dans
`verification/historique/orch_cao_masse_1/` avec l'index de conservation des
exports ; elles ne qualifient pas les nouvelles dépendances. Les preuves
du 25 octobre remplacées par la reprise sont conservées sous
`verification/historique/orch_cao_masse_1/avant_reprise/`. La reprise étend les
recherches structure, équipements et fournitures, puis la visserie ; une
contrelecture dédiée maintient les poids commerciaux Waveshare conditionnels.
Chaque poste massique incomplet porte désormais son problème et l'information
nécessaire dans la BOM canonique, sans imposer l'arrêt des travaux indépendants.

| Exigence et contrôle | Résultat observé et limite |
|---|---|
| `MEC-ARC-001` → intégration, extraction BRep et couverture BOM/CAO | 132 références, 368 occurrences enregistrées, 512 occurrences physiques et 328 formes sources ; aucune forme physique invalide. Les 134 postes BOM, dont 95 embarqués, figurent dans la réconciliation inverse. Six postes restent sans détail CAO identifié : fixation d'hélices, piges Airy, freinage, terminaisons, gaines et capots. Cinq propriétaires massiques restent indéterminés : quatre feuilles OEM et le composé porteuse/6X/Orin. Un rattachement ne démontre pas une complétude. |
| `MEC-INT-001` → sauvegarde, fermeture et réouverture dans un nouveau processus FreeCAD 1.1.3 Windows AMD64 | 375 liens et 368 poses contrôlés sans erreur de lien, de recalcul ou de pose ; natifs non modifiés par le contrôle. Sauvegarde FreeCAD App, apparences utiles conservées et nouveaux résultats de découpe/fusion reprenant leur source ; contrôle XML des liens/placements. Contrôle interactif GUI non exécuté après blocage d'initialisation ; les vues de contrôle sont tessellées depuis les BRep sauvegardés. |
| `MEC-INT-001` → remplacements et interfaces | Sept géométries d'équipements reprises dans la première passe. Reprise PM08 appliquée avec rotation, déplacements UART/fusible, passages P64/P73/P75 et six fixations ajoutées. Les trois collisions PM08 et quatre chevauchements QS8 constatés sont supprimés. Têtes M3×16/M3×40 et fraisures P60/P66 corrigées à90°, huit poses ajustées ; contour exact des vis et appui physique encore inconnus. Trois têtes CHC corrigées selon les diamètres documentaires, douze placements conservés ; filetages et détails simplifiés. Le gabarit théorique ne devient pas un modèle fabricant exact. |
| `CAB-CARTO-001` → interfaces et faisceaux | Huit parcours puissance et le départ F20 repris, chevauchement F20 supprimé. Contrôle sauvegardé de 12 977 paires autour des occurrences modifiées : zéro intersection positive ; 18 contrôles de paramètres et contacts des fraisures et 15 contrôles des têtes et placements CHC. Réservations arrêtées hors enveloppes QS8/PM08/fan ; segments terminaux et raccordements restent ouverts. Interface SMA GNSS incohérente, prises Basler et engagement Key M à documenter. Les 53 parcours ne sont pas des coupes libérées ni 53 câbles à additionner. |
| `MEC-INT-001` → quatre rotors | Axes et appuis nominaux conformes ; six paires de disques modélisés séparées, jeu minimal 66,108 mm. Variante 1555, moyeux/perçages, masses, tolérances et hélices réelles restent inconnus ; compatibilité et vol non démontrés. |
| `MEC-MAS-001` → calcul C++17, inclusions et provenance | Sous-total disponible 2 892,664 g = 1 299,808 g documentaires applicables + 1 592,856 g de calculs candidats, dont 387,779 g de pièces carbone et 200,650 g de corps aluminium OEM à densités analogues, et 10,094 g pour le seul segment M8. Dix postes documentés, treize calculés complets sur leur contenu défini et deux inclusions couvertes ; 70 postes restent incomplets, dont onze avec contribution partielle. Quinze recettes documentaires, 86 contributions de géométrie/câble ; moteurs 600 g, ATOF 1,4 g et RP4TD 1,4 g comptés une fois. Le kit complet 2 000 g sans batterie figure en approvisionnement sans être ajouté ; scénarios ESC 23,2 g et hélices 88 g exclus du sous-total. Masse complète, centrage et inerties du drone `null`. Les propriétés de 47 pièces homogènes seulement ne sont pas celles du drone et excluent 24 pièces OEM sans distribution calculée. |
| `MEC-INT-001` → intérieurs des bras OEM | Contrôle BRep avec matrices globales : 216 paires après filtre, 22 intersections positives, deux booléens non conclus. Aucun recoupement détecté entre les douze corps aluminium estimés, ni entre eux et les quatre tubes carbone retenus. Les objets non attribués, bagues et vis concernés restent hors estimation ; caractère voulu des contacts, résolution des erreurs et comptage réel **À valider**. La [preuve](../hardware/mecanique/cartographe/verification/orch_verifier_interferences_oem.json) conserve le résultat incomplet. |
| `MEC-MAS-001` → cas négatifs, reproductibilité et consommateurs | Tests de conversion, maxima, périmètres, quantités inconnues, inclusions, absence de propriétaire, formes de même fichier et caches périmés. Tests ciblés de la passerelle/inventaire existants ; classeur réimporté et recalculé pour quantité 7/0/inconnue, sans erreur de formule. Aucun Excel natif, nouveau Gazebo/PX4 ou essai physique. |

La couverture et le sous-total sont **Implémenté** ; la définition complète
reste **À valider**. Les collisions ciblées sont corrigées ; les raccordements,
interfaces non documentées et l'orientation GNSS restent ouverts. Les masses
commerciales sans tolérance publiée ne sont pas exactes,
les densités typiques et recettes de fabrication sont des hypothèses de calcul,
et aucune borne garantie de masse du drone n'est annoncée.

**Prérequis avant reprise des simulations physiques :** identifier variantes
et révisions réellement retenues, obtenir plans utiles et masses nettes avec
contenu exact des ensembles OEM, batterie/BMS/PM08/avionique ; résoudre les
44 MPN CA01 manquants et sa constitution ; compléter quincaillerie, gaines,
contacts, consommables et coupes de faisceaux ; résoudre les interfaces
restantes et contrôler leurs modifications sur les fichiers
finaux. Les mesures nécessaires portent les composants effectivement montés
avec leurs accessoires et longueurs conservés, sans masse de colis ou de kit.
Après réconciliation, caractériser la distribution des masses avant CG/inerties
du drone, régénérer les exports Gazebo et revalider leur périmètre. La suspension
des nouvelles campagnes demeure ; les essais physiques demandent toujours leur
protocole et autorisation propres.

La passe [GO3A](#cartographe-go3a) complète le rattachement documentaire du
faisceau et confirme que le montage des interfaces critiques reste à
démontrer. Avant de chiffrer les terminaisons et de clore le bilan, instruire
la baie commune CAN1/diagnostic et les cordons critiques avec les trois
familles [GO3A V2.1](#cartographe-go3a-revise) sur le même actif. Le
[contrôle d’admission GO3B](#cartographe-go3b) confirme que ces
données et la preuve d’intégrité électromécanique des natifs liés conditionnent
la réception. La clôture ORCH conserve ses critères de masse et de preuves.
Le [rejeu V2.1 XLink](#preuve-xlink-v21) établit la correspondance des axes
et leurs occurrences sur le prototype actif. Les contacts et les volumes
de service restent à instruire avant clôture des terminaisons.
La [clôture B.2](#qualification-xlink-v21-b2) complète la couverture
nominale des paires et localise les intersections à instruire dans
ORCH-CAO-MASSE-1.
La [requalification C](#requalification-v21-c) démontre le préflight et
la réimplantation sur banc synthétique lié. Les essais GO3A V2.1 sur
copies doivent tracer les sept intersections héritées et produire les
observations d’interface propres au prototype.

La campagne [GO3B exécutée](#cartographe-go3b-reconstruction) conserve une
consolidée de diagnostic sur copie et ferme cette passe en NO_GO motivé.
Elle confirme les sept défauts B.2 et les reprises nécessaires au
raccordement F40/F41. La prochaine expérience d’appui/cheminement doit
précéder la clôture des terminaisons, des masses et la réception. Le
programme GO4 conserve la progression du §2.

[V3-A.1](#cartographe-v3-a1) admet les essais indépendants de construction
sur banc numérique en soutien de cette reprise. [V3 B.1](#cartographe-v3-b1)
vérifie la construction et l’appui sur banc scellé. [V3-A.2](#cartographe-v3-a2)
identifie les exclusions et les autorités à obtenir pour l’appui et le
cheminement. Reprendre la décision de mutation après identification du lot,
relevé signé des interfaces et des ancrages, puis démonstration d’un domaine
compatible avec le service et les protections. Ces contrôles servent la
clôture de géométrie et de nomenclature sous ORCH-CAO-MASSE-1.
[V3-I](#cartographe-v3-i) réunit le constructeur et les preuves A.2.
[V3-A.3](#cartographe-v3-a3) confirme les exclusions d’appui et de service et
rend le relevé opérateur utilisable pour les douze couples occurrence–opération.
La contre-validation sur banc et la collecte par occurrence peuvent avancer.
[V3 B.2](#cartographe-v3-b2) vérifie les effets sauvegardés et ouvre
l’orchestration V3-C dans le périmètre des bancs scellés.
[V3-C](#cartographe-v3-c) éprouve la recherche paramétrique et la
contre-validation sur ces bancs. L’exploration du cartographe dépend des
preuves d’autorité relatives aux opérations envisagées.
[V3-C.1](#cartographe-v3-c1) démontre le couplage de la pose, du port, du
parcours et du support en banc avec un domaine restreint après gel.
[V3-D](#cartographe-v3-d) maintient la lecture seule du cartographe et fixe
la collecte préalable à une décision sur le support et les cheminements.
[V3-A.4](#cartographe-v3-a4) fournit le formulaire et l'import préliminaire
de ces relevés. Le budget de construction du cartographe reste nul tant que
le dossier du couple `CREATE_SUPPORT(iso)` n'est pas admis.
[V3-INT.1](#cartographe-v3-int1) consolide les deux voies et fixe les
conditions de passage pour les travaux synthétiques et la revue habilitée.
[V3-C.2](#cartographe-v3-c2) éprouve la convergence de deux câbles et le
choix d’appui. L’instruction des interfaces réelles conserve ses portes.
[V3-A.5](#cartographe-v3-a5) rend vérifiable la revue de test et maintient
la collecte du lot réel avant une décision d'ancrage sur P64 ou P66.

<a id="preuve-porte-v21"></a>
**T-CARTO-V21-GATE · G3A-01 à G3A-08.** Dans la preuve initiale, le
préflight du gestionnaire de convergence a rejoué `NO_GO_MOTIVE` à 0
variante sur 12, puis a autorisé le
plan d’exploration numérique privé H-01 avec les huit états
`INCONCLUSIVE`. La réception rend `FINAL_NO_GO` en l’absence d’un
candidat intégré et de preuves associées aux critères gelés. Les cas
négatifs couvrent les gardes d’essai, les états de preuve, l’intégrité des
fichiers et la reprise de la file à budget inchangé. La preuve spécifie
les régressions et les limites. Le rejeu intégré sur la livraison courante
s’arrête au contrôle d’empreinte du worker FreeCAD (voir
[T-CARTO-V21-QUAL](#qualification-integree-v21)). H-01 reste **À valider**.
[Preuve reproductible](verification/v21_exploration_gate.json) ·
[Contrat V2.1](electromechanical_v2_1/01_EXPLORATION_POLICY.md).

### 14.1 Ordre de reprise à partir du 8 octobre 2026

Appliquer le [cadrage de DOC-HLD](architecture/HLD.md#methodologie).
Le responsable du projet a choisi le 7 octobre de valider d'abord la
**faisabilité physique du cartographe**. Les axes ci-dessous organisent les
travaux conservés ; ils ne constituent ni un calendrier approuvé ni une
autorisation de banc. Les critères chiffrés et budgets encore inconnus sont
**À valider** avant engagement, jamais ajustés après observation pour conclure
favorablement. Impact et urgence sont distincts : aucun incident matériel
urgent n'est observé ici ; l'urgence des premiers points vient des décisions
de conception qu'ils conditionnent.

| Ordre / rôle | Action minimale et lien aux écarts | Preuve de sortie / décision | Limite et arrêt |
|---|---|---|---|
| 1 — système/mécanique, fort impact avant nouvelle variante | inventorier matériel disponible/révisions ; réconcilier une configuration cartographe, sa BOM, inclusions, masse/centrage, limites du porteur et données propulsion ; AUD-003/008 | bilan unique sourcé, inconnues et postes discriminants ; décision poursuivre, alléger, revoir le porteur ou mesurer | une configuration et une passe sur données existantes ; pas de nouveau modèle ni achat ; arrêter sur bilan exploitable ou donnée bloquante identifiée |
| En soutien immédiat — validation/mécanique | comparer sans sauvegarde le natif divergent et la revue ; AUD-007 | portée du changement connue puis contrôles proportionnés sur le fichier courant | arrêt après diagnostic de portée ; pas de régénération automatique ni réécriture de preuve historique |
| 2 — électrique/système, fort impact avant fabrication | confronter profil mission, puissance/énergie, BMS/connecteur avec maîtrise de l'appel/PM08/CA01 et thermique ; sélectionner le premier test discriminant ; AUD-004 | critère tiré des limites applicables, modèle/hypothèse, protocole et résultat attendu ; décision prévue si échec | budget horaire/financier et répétitions **À valider** ; aucun essai sensible sans prérequis de §2 et arrêt sûr |
| 3 — mécanique/acquisition, fort impact avant intégration avancée | fermer tenue/fixations et définir la chaîne minimale LiDAR–image–pose ; AUD-004/005 | mesures d'effort/tenue et synchronisation liées au besoin, limites et refus explicites | une hypothèse critique à la fois ; suspendre l'ajout de variantes si les données nécessaires manquent |
| Selon dépendance du banc retenu — logiciel/validation | corriger seulement les garanties nécessaires pour exploiter sa preuve ; AUD-010/011/012/014/015 | contrat effectivement contrôlé, test autonome et environnement identifiable | pas de refonte globale de station ou Docker ; arrêter quand le banc retenu produit la preuve attendue |
| Après décision de faisabilité — pilotage | réexaminer les lots logiciels, perception avancée, traitement et abstractions ; AUD-013/016 | justification par besoin observé et capacité minimale démontrée | un nouveau chantier exige son propre signal, budget, arrêt et revue ; toute priorité différente est explicitée |

La méthode, les renvois d'autorité et les contradictions documentaires ciblées
sont corrigés dans cette tâche (AUD-001/002 partiellement, AUD-006/009/017).
Les travaux techniques du tableau sont **Planifiés**. La décision de priorité
est acquise ; les critères de réussite physique, les budgets d'essai et la
preuve de faisabilité restent **À valider**.

État au 9 octobre : la sélection documentaire a été rapprochée dans une
nomenclature unique du prototype sans dock (§14.3). L'inventaire du matériel
possédé, le bilan complet et la preuve de faisabilité restent ouverts ;
la première action n'est donc pas close.

### 14.2 Portefeuille conservé

Les actions ci-dessous restent nécessaires selon leurs portes. Leur numéro
est un repère de liste, **pas l'ordre d'exécution** ; le §14.1 les séquence.

1. Exécuter la suite courante, les rejeux LIO et les scénarios PX4 sur Linux,
   puis sur un hôte `arm64` natif/Jetson.
2. Définir et approuver les seuils multi-scènes de localisation, rangs,
   corridors, latence et ressources.
3. Qualifier les extrinsèques et la synchronisation Airy/Basler et FriûlBot sur
   correspondances indépendantes ; exécuter d'abord T-AIRY-SYNC-01 au banc
   pour caractériser PPS/GPRMC, le trigger Pixhawk et le retour réel
   `ExposureActive` ; garder `SYNC_OUT1` comme variante de banc.
4. Étendre l'assemblage borné à une parcelle, mesurer dérive/couverture,
   intégrer IMU/deskew et fermeture de boucle selon les besoins, puis qualifier
   la surface et les zones inconnues.
5. Implémenter et valider `VB01` à `VB10`, y compris fils, perte RTK et
   géométrie pauvre.
6. Réaliser les vérifications mécaniques et électriques de prototype, puis les
   bancs d'actionneurs.
7. Préparer la revue de risques avant tout vol ; ne passer à l'eau/traceur
   qu'après fermeture des portes précédentes.

8. Exécuter la campagne AUTO/MANU, couverture et RF commun du §9.1 après
   fixation des versions et critères ; qualifier distinctement les deux drones.
9. Mesurer au banc puis en terrain le tri-flux T-RF-06 avec la base H-RTK
   F9P et le rover DroneCAN retenu après l'étude temporelle ; arrêter la
   politique de priorisation et, si la marge
   échoue, dimensionner une liaison de données distincte pour RTCM/MAVLink.

<a id="nomenclature-prototype"></a>
### 14.3 Nomenclatures prototype et produit custom — 11 octobre 2026

**T-CARTO-BOM-PROTO-01**, lié à MEC-ARC-001, MEC-MAS-001,
CAB-CARTO-001 et à l'action prioritaire de §14.1 : rapprocher la sélection
cible avec le prototype X650 sans échange rapide. Le
[registre](../hardware/mecanique/cartographe/nomenclature_prototype.json)
et le [classeur](../hardware/mecanique/cartographe/exports/Nomenclature_Prototype_Cartographe.xlsx)
sont **Implémentés** ; la sélection, la réalisation et la qualification
physique restent **À valider**.

Critères de cette vérification documentaire : tous les postes source et
liaisons repris ou explicitement exclus, identifiants uniques, parentages
résolus, quantités inconnues distinctes de zéro, sources locales accessibles,
empreintes concordantes, aucune masse totale inférée, export fidèle et
formules sans erreur. La
[preuve technique](../hardware/mecanique/cartographe/verification/controle_nomenclature_prototype.json)
porte les entrées, empreintes, comptages, contrôles et limites.

Résultat courant après définition du prototype : **134 lignes** couvrent les **60 postes
source**, dont **95 embarquées et 23 exclues** ; **43 identifiants de liaisons**
couvrent tous les Wxx de la source, y compris ceux explicitement retirés.
JETI, commande magnétique et `ELEC-F39` sont à quantité zéro dans les retraits ;
`W39` et `W-JETI-COMMANDE` aussi. `ELEC-F38`/`W38` portent le raccord direct
connecteur côté drone → PM08-CAN IN. La reprise
CA01 conserve **151 repères / 141 composants montés candidats / 8 DNP /
2 points de test**. La revue indépendante a fait corriger le rattachement des
empreintes CA01 et la nature de la masse Basler (« <85 g »). Les onglets,
formules de comptage et représentations du classeur sont contrôlés.

La décision du 10 octobre conserve BMS, PM08, distribution, isolation UART et
protections ; le connecteur doit assurer la maîtrise de l'appel de courant
pour **branchement = marche, débranchement = arrêt**. Les candidats et leurs
limites sont dans [DOC-ELEC §3](architecture/ARCHITECTURE_ELECTRIQUE_RESEAUX.md#3-chaîne-dénergie-candidate-du-cartographe).
Ce besoin est décidé ; le responsable retient **un jeu QS8-S D-MAX B9310**.
La référence est choisie, la qualification reste **À valider** : aucune tenue
à l'appel capacitif, mesure thermique ou déconnexion sous charge n'est acquise.
Le responsable retient ensuite un SSD Samsung 990 EVO Plus 1 To,
MZ-V9S1T0BW, ligne 21, pour conserver toutes les données brutes LiDAR/caméra
pendant la mission, scénario caméra confirmé à 5 images/s sur 20 minutes.
Les budgets conditionnels sont dans [DOC-ELEC](architecture/ARCHITECTURE_ELECTRIQUE_RESEAUX.md#stockage-prototype) ;
budget combiné et qualification d'acquisition restent ouverts. Le responsable
retient ensuite **un jeu Waveshare Orin-FAN-PWM, SKU 24076**, à la ligne 22 ;
interfaces et thermique **À valider**, dans
[DOC-MEC](architecture/ARCHITECTURE_MECANIQUE.md#refroidissement-prototype).
Le responsable retient ensuite **un Fujinon CF8ZA-1S, 8 mm, monture C**,
pour `SEN-LENS`, ligne 26 ; sa masse fabricant d'environ 180 g est distinguée
d'une masse installée mesurée. Le poste `SOL-PC`, ligne30, désigne depuis la précision du 12 octobre un
terminal au format ouvert (portable/tablette/téléphone), distinct du PC fixe.
Son choix et son chargeur hypothétique60 W sont différés hors CAO, selon
[DOC-ELEC](architecture/ARCHITECTURE_ELECTRIQUE_RESEAUX.md#pc-sol-prototype).

Le contrôle documentaire **`T-CARTO-FAN-CONN-01`**, du 10 octobre, est
**Implémenté** ; le raccordement demeure **À valider**. Sa
[preuve](../hardware/electronique/cartographe/verification/controle_connecteur_ventilateur_jetson.json)
établit le courant nominal Waveshare 0,13 A sous la limite Holybro 0,35 A,
et conserve l'identification DF13 **candidate** issue du STEP et de la photo.
Elle n'établit ni la tension du port FAN, ni les deux brochages, ni la
référence d'accouplement Waveshare, ni la portée réelle du câble.
Conclusion : **raccordement direct non démontré**, sans qualification
électrique ou thermique. Critères de fermeture : confirmer les références
et les contacts sur les variantes utilisées, la tension, les niveaux de
commande éventuels et la portée ; vérifier ensuite démarrage, régulation et
température sous charge. Aucune mesure sur matériel n'a été exécutée.
Le contrôle FAN précède le choix du refroidissement ; sa preuve historique
reste conservée. La sélection ultérieure actualise le registre et son export
sans fermer ces vérifications physiques.

Le calcul **`T-CARTO-OPT-01`** est **Implémenté**, qualification **À valider**.
La [preuve](../hardware/electronique/cartographe/verification/dimensionnement_objectif_prototype.json)
compare les champs idéaux de deux objectifs candidats sur la Basler.
Le responsable souhaite espacer les passages et propose une hauteur de
travail de 10 m au-dessus des vignes, en remplacement de 20–30 m envisagés
initialement. Ce scénario n'est pas une hauteur nominale qualifiée ;
le responsable choisit ensuite le Fujinon CF8ZA-1S pour `SEN-LENS`.
La preuve conserve l'état des candidats au moment du calcul ; la sélection
figure dans la BOM. Les paramètres, masses publiées et limites
sont dans [DOC-ELEC](architecture/ARCHITECTURE_ELECTRIQUE_RESEAUX.md#objectif-prototype).
Critères de fermeture : GSD utile et recouvrements définis, intrusion et
fixation compatibles, calibration/distorsion et netteté mesurées, retours
LiDAR et densité utiles constatés sur les cibles réelles. Aucun essai
d'acquisition, thermique ou vol, ni changement de paramètres PX4 exécuté.

Le choix du terminal `SOL-PC` est différé hors CAO. Avant usage du format
retenu, vérifier les fonctions de terrain réellement nécessaires :
supervision, affichage et manipulation, liaison radio/RTK, veille/énergie,
autonomie et transfert des acquisitions. Le profil Qt desktop antérieur
ne démontre aucune capacité mobile. Les60 W du chargeur sont une hypothèse
utilisateur, sans mesure ni qualification. Aucun de ces essais matériels
n'est exécuté dans cette passe documentaire ; la CAO aéronef reste inchangée.

La revue **`T-CARTO-CHARGE-DOC-01`** est **Implémenté**, qualification
**À valider**. Sa
[preuve](../hardware/electronique/cartographe/verification/controle_recharge_bms_prototype.json)
confronte la notice JBD A01 et les chargeurs candidats. Le port protégé
B+/C− permet le concept deux fils, batterie débranchée du drone ; le chargeur
assure la régulation. **SkyRC S100neo SK-100202** est retenu pour la définition,
quantité **1**, avec réglages et recharge **À valider**. Le courant
OEM du pack et les bornes Capacity/Timer du firmware restent à confirmer.
Sa sortie de charge XT60 impose un cordon **XT60 → QS8-S** ; l'accouplement
direct est impossible. Ce raccordement est explicité dans la BOM et sa preuve ;
**Logic RC O-LGL-CLQS8** est retenu comme cordon complet en quantité 1,
connecteurs intégrés. Cette référence documentaire ne démontre pas
l'accouplement exact avec D-MAX B9310 ; sexes des contacts, polarité et
caractéristiques du lot doivent être contrôlés sur les équipements réels.
Avant recharge : limites de charge et seuils BMS adaptés, polarité et protections
revues ; protocole de banc pour profils CC/CV, cellules/équilibrage, température,
fin sans maintien et ouverture/reconnexion BMS. Les critères chiffrés suivent
les notices réelles, pas les coupures ultimes par défaut. Un arrêt pour
coupure BMS n'est pas assimilé à une charge complète. Aucun faisceau réalisé
ni essai de recharge exécuté ; natifs dock/JETI historiques conservés.

Deux exports distincts comportent chacun onze onglets, dont une Vue système
liée au détail (**24 équipements principaux prototype**, 26 fonctions/équipements
custom). Le
[registre custom](../hardware/mecanique/cartographe/nomenclature_produit_custom.json)
recense 54 postes fonctionnels **Planifiés / À valider**. La revue indépendante
a confirmé la conservation du prototype et fait clarifier le parentage custom
et les fonctions incluses dans sa porteuse. Les **96 contrôles** du vérificateur
réussissent sur les fichiers sauvegardés : couverture, données des cellules,
formules de synthèse, inconnues, inclusions, filtres, volets et empreintes.
La synthèse prototype a été recalculée après les suppressions ; les rendus
avant/après ont été relus et les réserves modifiées rendues entièrement lisibles.
La vérification précédente de propagation des quantités demeure distincte ;
le recalcul dans Excel natif n'a pas été exécuté. La preuve liée ci-dessus
porte les exports sauvegardés et les quatre contrôles ciblés du retrait.
La revue indépendante du retrait ne relève plus d'écart après correction
de la mention F39 dans les terminaisons. La comparaison à l'état avant retrait
confirme la conservation des données, formules, styles et dimensions des sept
onglets non concernés ; les empreintes du registre et de l'export custom sont
identiques. Aucun résultat de cette revue documentaire ne vaut essai matériel.
Pour l'ajout QS8-S et le cadrage SSD qui suivent, la comparaison des onze
onglets à l'état précédent confirme que seuls `ELEC-CONNECTEUR-MANUEL` et
`AVI-SSD` changent ; les données/formules/styles non concernés et les deux
fichiers custom sont préservés. Les budgets caméra sont calculés, sans test
de débit, température ou intégrité sur Jetson ; le format Bayer8 reste une
hypothèse distincte de la cadence/durée confirmées.

La sélection du SSD et le cadrage du refroidissement qui suivent sont
vérifiés à leur tour sur les onze onglets : seules les données des postes
`AVI-SSD` et `MEC-REFROIDISSEMENT-JETSON`, leur synthèse liée et la hauteur
nécessaire à lire les réserves du refroidissement changent. Les autres
données, formules, styles et les deux fichiers custom sont préservés.
Aucun essai thermique ou d'acquisition sur matériel n'a été exécuté.

La définition du prototype comprend désormais **55 postes repris**, dont
les 50 initialement incomplets. Les champs actifs de référence et de quantité
sont renseignés par une référence fabricant, une inclusion OEM ou une
définition projet distinctes ; cela n’établit pas la disponibilité du matériel.
**20 détails matériels demeurent ouverts** : trois contrôles de contenu OEM,
neuf détails de montage ou qualification physiques et huit interfaces à
identifier. Les deux choix de terminal et d’alimentation au sol sont différés
séparément, sans dépendance CAO. Le registre possède le détail courant.
Le 22 octobre, le classeur prototype est réexporté, réimporté et recalculé,
puis ses lignes modifiées sont inspectées. **108 contrôles documentaires**
réussissent sur les fichiers sauvegardés ; les variations 7, 0 et vide
se propagent dans la synthèse sans sauvegarder les valeurs d’essai.
Le classeur custom et son registre sont préservés. Le recalcul dans Excel
natif n’est pas exécuté. Seules des preuves aux empreintes concordantes
décrivent les fichiers courants ; les contrôles CAO correspondants sont au §14.4.

La conclusion de faisabilité reste **données insuffisantes** : les masses,
le centrage, l'endurance, la thermique et l'acquisition ne sont pas démontrés.
AUD-003 reste ouvert. AUD-007 et les preuves de course du dock concernent les
natifs historiques avec JETI ; le nouvel assemblage possède une vérification
distincte au §14.4. Le routage CA01, les essais de propulsion, de câblage et
de banc ne sont pas rejoués par cette passe de définition mécanique.

<a id="assemblage-prototype"></a>
### 14.4 Reconstruction FreeCAD du prototype — 22 octobre 2026

**Périmètre historique du 22 octobre, remplacé pour les fichiers modifiés par ORCH-CAO-MASSE-1 (§14).**

**T-CARTO-CAO-PROTO-01**, lié à MEC-ARC-001, MEC-INT-001 et CAB-CARTO-001,
porte sur
[`Prototype_Cartographe.FCStd`](../hardware/mecanique/cartographe/assemblages/Prototype_Cartographe.FCStd)
et ses sept sous-assemblages liés. La refonte est **Implémenté** :
**118 références, 346 occurrences**, énergie à l’étage supérieur,
caméra conservée avec prises coudées et **53 parcours Cable Workbench 0.3.7**.
Les choix et interfaces sont dans
[DOC-MEC §2.2](architecture/ARCHITECTURE_MECANIQUE.md#assemblage-prototype).
Les preuves du 22 octobre portent les empreintes des fichiers finaux ;
les résultats des constructions antérieures ne sont pas transférés sans identité.

Les contrôles numériques sont conformes à leurs critères déclarés, sans
assouplissement de seuil pour accepter un défaut. Ils ont été exécutés sous
FreeCAD 1.1/Windows sur les natifs sauvegardés, par réouverture ou lecture
des BRep selon le protocole. Les processus de contrôle n’ont pas sauvegardé
de modification des natifs. La construction, les sources et les recettes sont
rapprochées par empreintes avant la synchronisation finale.

| Périmètre et critère | Résultat et preuve du 22 octobre |
|---|---|
| Construction et sources | 118 références et 346 occurrences ; sources OEM préservées, sept sous-assemblages. [Construction](../hardware/mecanique/cartographe/verification/historique/orch_cao_masse_1/construction_prototype.json), [inventaire](../hardware/mecanique/cartographe/verification/inventaire_reconstruction_prototype.json) et [préservation initiale](../hardware/mecanique/cartographe/verification/preservation_sources_prototype.json). |
| Liens, placements et interférences | 346 liens et poses retrouvés ; aucune collision hors interfaces explicitement déclarées. Les volumes engagés SSD/microSD restent localisés et **À valider**. [Contrôle assemblage](../hardware/mecanique/cartographe/verification/historique/orch_cao_masse_1/controle_assemblage_prototype.json). |
| Recalcul et cheminements | 53 parcours natifs recalculés, continuité, rayons et longueurs conformes aux critères de définition. Contrôles exacts contre structure, guides et équipements. [Contrôle faisceaux](../hardware/mecanique/cartographe/verification/historique/orch_cao_masse_1/controle_faisceaux_prototype.json). |
| Pièces et fixations des guides | Solides, métadonnées persistées, ancrages et interférences des références fabriquées contrôlés. [Pièces](../hardware/mecanique/cartographe/verification/historique/orch_cao_masse_1/controle_pieces_prototype.json) et [guides](../hardware/mecanique/cartographe/verification/historique/orch_cao_masse_1/controle_fixations_guides_prototype.json). |
| Départs des bras | Huit départs signal/LED fermés par douze stations : huit sur les commandes MAIN/F04 (deux par bras) et quatre sur les LED. Contrôle contre les câbles et obstacles finaux. [Départs](../hardware/mecanique/cartographe/verification/historique/orch_cao_masse_1/controle_departs_bras_prototype.json). |
| Réserve USB, liaisons et corps | Trois boucles de réserve USB, neuf liaisons entre supports et trois captures de corps QS8/RF0/RF1 : bandes fermées, passages, captures communes, interférences et têtes contrôlés. Deux liaisons P75–P72 réemploient des colliers du contrat ; QS8 réemploie F37_POS_-20 et RF1 sa boucle native. [Colliers](../hardware/mecanique/cartographe/verification/historique/orch_cao_masse_1/controle_colliers_prototype.json). |
| Couverture des retenues | 295 affectations de stations pour les 53 parcours, 269 colliers uniques, portées et exceptions locales documentées conformes. Les colliers communs ont une affectation géométrique cohérente. [Contrat](../hardware/mecanique/cartographe/verification/retenues_faisceaux_prototype.json) et [contrôle](../hardware/mecanique/cartographe/verification/historique/orch_cao_masse_1/controle_retenues_faisceaux_prototype.json). |
| Supports GNSS/USL, RF et MIDI | 24 occurrences ciblées : quatre supports, quatre boucles natives et seize éléments M2. Fusions, cinq appuis, quatre empilages M2 et interférences conformes. [Équipements](../hardware/mecanique/cartographe/verification/historique/orch_cao_masse_1/controle_fixations_equipements_prototype.json). |
| Revue indépendante et inspection visuelle | Revue des pièces, placements et fixations, [contre-vérification des trois corps](../hardware/mecanique/cartographe/verification/historique/orch_cao_masse_1/review_assemblage_prototype.json#contre_verification_corps) ; inspection de l’ensemble et des zones difficiles sur les vues natives finales. [Revue](../hardware/mecanique/cartographe/verification/historique/orch_cao_masse_1/review_assemblage_prototype.json) et [rendu](../hardware/mecanique/cartographe/verification/historique/orch_cao_masse_1/rendu_prototype.json). |
| Registres et nomenclature | BOM et classeur alignés sur les fichiers contrôlés ; 108 contrôles documentaires, relecture/recalcul de l’export, limites de quantité testées à 7, 0 et vide. [Nomenclature](../hardware/mecanique/cartographe/verification/historique/orch_cao_masse_1/controle_nomenclature_prototype.json), [couverture BOM/CAO](../hardware/mecanique/cartographe/verification/historique/orch_cao_masse_1/couverture_bom_cao_prototype.json) et [registres](../hardware/mecanique/cartographe/verification/historique/orch_cao_masse_1/controle_registres_prototype.json). |

L’enveloppe nominale est de **853,513 × 505,793 × 486,320 mm**, avec une garde
verticale de l’objectif de **91,436 mm**. Elle comprend les représentations
de câbles ; elle ne borne ni les débattements ni l’accès de tout outillage.
Les sources OCCT imparfaites et les volumes engagés des connecteurs restent
identifiés par le contrôle plutôt que masqués par une exemption générale.

**Défauts CAO corrigés.** Les corrections portent sur les croisements de
guides et gaines, les huit reprises des bras, les passages et les boucles
communes USB, les ancrages P69/P71 fusionnés vers P66, les reprises P70
vers P75 et la tablette MIDI sur P73. La déduplication des colliers évite
d’ajouter les deux bandes P75–P72, le QS8/F37 et le corps RF1 déjà retenu
par sa boucle native. Le contrôle des retenues
conserve les budgets de portée et refuse les partages entre ancrages incompatibles.
La synchronisation refuse une preuve absente, périmée ou non conforme.

**Limites matérielles — À valider.** La BOM porte **20 détails matériels
ouverts**. Aucun défaut géométrique constaté n’est reclassé en essai physique.
Le décompte est de **281 colliers nominaux dans le périmètre de contrôle** ;
les trois corps QS8/RF0/RF1 ont une pose nominale contrôlée, sans
qualification physique. La quantité réellement posée est inconnue.
Les coordonnées ou plans manquants des interfaces modules, les brochages
USL/FAN, la protection des bornes, les terminaisons, la compatibilité des
prises caméra, les tolérances, le serrage, l’abrasion, les vibrations,
la thermique et les masses installées restent à vérifier sur matériel.
Le QS8 monobloc ne décrit pas sa face de joint ni son volume de manœuvre :
identifier le demi-corps fixe sur plan/lot, vérifier accouplement, extraction
et prise en main hors bande, puis adapter la pose si le joint est recouvert.
Le cordon USB n’a que 3,326 mm de marge sur son budget conservateur ; le
rayon statique de 22 mm ne qualifie pas la flexion continue à 48 mm.
L’engagement M8 de 6 mm reste hypothétique. La définition de CAO ne qualifie
ni la fabrication, ni la mise sous tension, ni le vol. Aucun de ces essais
n’a été exécuté dans cette passe ; terminal et alimentation au sol restent
différés hors CAO.

<a id="audit-preceptes"></a>
## 15. Audit des préceptes et remise en cohérence

### 15.1 Périmètre, méthode et limites — 7–8 octobre 2026

Référentiel : [DOC-HLD §11, P01–P22](architecture/HLD.md#preceptes).
Exigence : `METH-001`. Priorité choisie par le responsable du projet :
**faisabilité physique du cartographe**, avant les extensions de capacité.

L'audit porte sur le workspace à partir de Git
`4463ffeee77653ae92dca59fae4cf6c16c6f2f80`, branche
`codex/sw0-consolidation`, avec **128 entrées de statut Git préexistantes**
(certaines représentent un répertoire), et non sur ce commit seul.
869 fichiers suivis ou non ignorés ont été inventoriés et empreintés au départ,
puis retrouvés identiques à la reprise du 8 octobre avant nos modifications.
Trois investigations indépendantes ont couvert logiciel, matériel et
validation ; leurs constats ont été consolidés avant intégration.

Lecture des documents vivants et points d'entrée ; inspection ciblée des
contrats, services, tests, CI, Docker, nomenclatures, configurations,
instructions agentiques et preuves. Les **22 préceptes sont passés en revue**.
Les faits sont vérifiés sur les fichiers cités ; risques et causes non observés
sont des inférences ou inconnues. Les empreintes, références initiales et
contrôles sont dans la [preuve structurée](verification/audit_preceptes.json).

L'inventaire léger des résultats locaux a trouvé 98 fichiers de manifeste,
108 fichiers de métriques et 11 `result.json` PX4 sous `results/benchmarks`
et `results/simulation` : ce ne sont pas autant de campagnes distinctes.
L'absence de Git de ces fichiers volontairement ignorés n'est pas un manquement.
Il n'y a eu ni nouveau build, ni CI distante, ni rejeu LIO/SITL, ni ouverture
ou sauvegarde de CAO, ni contrôle KiCad/ERC/DRC, ni mesure physique.
Les comportements logiciels décrits sont déduits du code, sauf contrôle
explicitement exécuté. Les gros datasets n'ont pas été relus intégralement.
Les notices, prix et règles externes n'ont pas été réévalués : les valeurs
matérielles citées sont celles du dossier local, encore **À valider**.

Critère d'arrêt : référence intégrée, couverture des 22 principes, constats
étayés avec action et clôture, ordre de reprise, revue indépendante et
contrôles documentaires. Aucun nouveau système d'audit n'est construit.
Conclusion : **non conforme au nouveau cadre sur les écarts identifiés** ;
intégration de la méthode **Implémenté**, conformité globale et faisabilité
physique **À valider**. Cet audit ne garantit pas l'absence d'autres écarts
dans les comportements non exécutés ou le matériel.

### 15.2 Constats, actions minimales et clôture

L'ordre de reprise est au §14. Le rôle indiqué est celui à mobiliser pour la
correction, pas une nomination ni un engagement de budget.

<a id="aud-001"></a>
#### AUD-001 — Référentiel de décision incomplet

- **Fait :** HLD §1 définit l'usage et §8.6 des performances préliminaires,
  mais l'état initial ne comportait ni méthode commune ni définition
  opérationnelle de l'Étoile du Nord et de son décideur. AGENTS organisait
  réalisation/review sans imposer le cadrage préalable.
- **Préceptes :** P01, P02, P12, P17. **Impact : fort ; rôle : pilotage.**
- **Action réalisée :** référence complète, déclencheurs et priorité utilisateur
  intégrés dans HLD/AGENTS/INDEX. Le besoin terrain et la réussite d'usage
  restent **À valider**, sans inventer d'approbation.
- **Clôture restante :** résultat utile, bénéficiaire et critères de réussite
  physique reliés au besoin et approuvés avant engagement correspondant.

<a id="aud-002"></a>
#### AUD-002 — Chantiers sans borne commune ni ordre de décision

- **Fait :** l'ancien §14 listait neuf actions, et DOC-SW §12 onze lots après T0,
  sans plafond d'effort, arrêt méthodologique ni arbitrage entre cartographe,
  cartographie, traitement et infrastructure. L'arrêt sûr d'un banc ne
  remplace pas l'arrêt d'une investigation.
- **Préceptes :** P03, P07, P08, P09, P14, P15. **Impact : fort ; rôle : pilotage.**
- **Action réalisée :** priorité physique et séquence §14 ; extension reportée
  sauf contribution explicite à la contrainte courante. Les budgets du futur
  essai ne sont pas encore approuvés.
- **Clôture restante :** première tâche bornée avec responsable, plafond
  d'effort/coût, signal, événement de revue et décision en cas d'échec.

<a id="aud-003"></a>
#### AUD-003 — Pas de bilan de faisabilité du cartographe complet

- **Fait :** DOC-MEC §6.1 donne un sous-total **historique et incomplet** de
  6,195–6,809 kg ; aucune marge sous les 6,3 kg commerciaux cités n'est
  démontrée. La [configuration cible](../hardware/mecanique/cartographe/configuration_cible_20261003.json)
  déclare elle-même l'absence de configuration complète active. Ce sous-total
  n'est ni la masse du prototype courant ni une preuve de dépassement réel.
- **Préceptes :** P02, P03, P10, P11, P12, P14. **Impact : critique pour la décision ; rôle : système/mécanique.**
- **Inférence :** poursuivre les détails d'implantation risque de consolider
  une configuration incompatible avec son porteur. Le gain de volume local
  mesuré ne ferme pas masse, centrage, poussée ou autonomie.
- **Action et clôture — Planifié :** réconcilier une seule BOM, inclusions et
  retraits, masses mesurées/publiées/provisionnelles/inconnues ; identifier les
  limites applicables puis décider poursuivre, alléger, changer la
  configuration ou obtenir une mesure précise. Aucun inconnu compté à zéro.

<a id="aud-004"></a>
#### AUD-004 — Critères physiques discriminants encore à définir

- **Fait :** DOC-MEC §4.1 et §4.4 laisse efforts, cycles, tolérances,
  précharge et fluage ouverts. La
  [campagne électrique/thermique/CEM](../hardware/electronique/cartographe/carte_avionique/validation_electrique_thermique_cem.json)
  contient encore des critères `null` ; §12.7.11 déclare zéro banc.
- **Préceptes :** P08, P09, P13, P14, P21. **Impact : fort ; rôle : système/mécanique/électrique.**
- **Qualification :** lacune de préparation de décision, pas fausse
  qualification ; les limites sont déjà annoncées honnêtement.
- **Action et clôture — Planifié :** dériver de la configuration et de l'usage
  un premier cas susceptible de réfuter tenue, énergie ou thermique ; fixer
  critère, répétitions, budget et arrêt avant résultat. Revue/calcul d'abord,
  banc après ses prérequis. Aucun seuil inventé par l'audit.

<a id="aud-005"></a>
#### AUD-005 — Succès de l'acquisition minimale non relié au besoin

- **Fait :** DOC-ELEC §8 et DOC-VAL §12.8 décrivent la chaîne candidate et
  demandent encore l'approbation des limites d'erreur temporelle, jitter,
  appariement, pertes et reprise ; aucun essai matériel n'est réalisé.
- **Préceptes :** P01, P11, P12, P21. **Impact : fort ; rôle : acquisition/système.**
- **Action et clôture — Planifié :** partir du niveau de carte utile pour
  définir la précision LiDAR–image–pose requise et une observation minimale
  sur la chaîne disponible ; relier critère approuvé, protocole et mesure.
  La présence d'un circuit de synchronisation ne prouve pas la datation réelle.

<a id="aud-006"></a>
#### AUD-006 — Synthèses électriques actives périmées

- **Fait initial :** DOC-ELEC §5.2 mentionnait EC5/AWG10, §6 un routage
  complet CA01 encore Planifié, et §10 le SBS X-75A. §6.2 et les registres
  courants décrivent AWG8/TE/BMS et un routage candidat présent. HLD §7.1
  présentait CA01 seulement comme Planifiée ; DOC-SW avait une date ancienne.
- **Préceptes :** P19, P22. **Impact : fort ; rôle : documentation de domaine.**
- **Correction Implémentée :** ces synthèses et leurs renvois sont alignés
  sur les choix actuels, avec fabrication/qualification toujours **À valider**.
- **Clôture :** cohérence documentaire ciblée vérifiée ; cela ne clôt pas
  AUD-008 ni ne requalifie les interfaces ou composants.

<a id="aud-007"></a>
#### AUD-007 — Empreinte de l'assemblage différente de la revue

- **Contrôle exécuté :** 147 natifs comparés à
  [revue_hierarchie_batterie.json](../hardware/mecanique/cartographe/verification/revue_hierarchie_batterie.json),
  146 identiques et un différent ; 66 autres fichiers revus tous concordants.
  `Integration_Stack_Revue_20261003.FCStd` vaut au moment de l'audit
  `b03b8588f5b2b64ecfe4114ed1ecd9500e589e623c4898f6d7e17319d26d93e5`,
  contre `a418dad3701a6ca6ece86a26167cf8be73c80c731c11a5005323e6f5f72a32a8`
  dans la revue, le contrôle et le manifeste.
- **Préceptes :** P04, P13, P19. **Impact : fort ; rôle : mécanique/validation.**
- **Inconnue :** géométrie, liens, vues ou métadonnées ; aucune régression
  géométrique n'est déduite d'une différence d'empreinte.
- **Action et clôture — Planifié :** comparer le contenu natif sans sauvegarde,
  identifier la portée puis rejouer les contrôles proportionnés sur le fichier
  courant ; conserver l'ancienne preuve. Ne pas remplacer seulement le hash
  attendu pour faire passer la vérification.

<a id="aud-008"></a>
#### AUD-008 — Contraintes de configuration historiques encore actives

- **Fait :** [configuration_cible_20261003.json](../hardware/mecanique/cartographe/configuration_cible_20261003.json)
  conserve le logement Z33…103 et une course continue/301 poses ; DOC-MEC
  distingue ce logement historique du plateau actuel Z128…130. Les preuves
  courantes portent sur des positions discrètes et excluent une démonstration
  continue (DOC-MEC §4.1.3.3 ; DOC-VAL §12.1.10).
- **Préceptes :** P13, P19. **Impact : fort ; rôle : mécanique/configuration.**
- **Action et clôture — Planifié :** distinguer dans le registre historique,
  requis et vérifié pour la variante courante. Conserver le reliquat de course
  continue ; une exigence non couverte n'est pas supprimée pour rendre la
  preuve conforme. Vérifier les recettes qui lisent ces champs avant modification.

<a id="aud-009"></a>
#### AUD-009 — Autorité ambiguë et empreinte FriûlBot mal recopiée

- **Fait initial :** §7.3 recopiait `14ded790d1771006219fc02980ee3eb8`
  pour les images ; le
  [catalogue canonique](../datasets/manifests/catalogue_datasets.yaml)
  et la [recette](../tools/download_friulbot.cmake) portent
  `14ded790d1771006218fc02980ee3eb8`. L'INDEX donnait une prévalence
  documentaire dont la portée vis-à-vis des manifestes était ambiguë.
- **Préceptes :** P17, P19. **Impact : moyen ; rôle : documentation/datasets.**
- **Correction Implémentée :** renvoi au catalogue au lieu de recopier le MD5,
  autorité précisée par nature de donnée dans l'INDEX.
- **Clôture :** contradiction documentaire retirée ; aucun recalcul du dataset
  ni nouvelle qualification d'intégrité n'est revendiqué.

<a id="aud-010"></a>
#### AUD-010 — Garantie T0 supérieure aux validations effectives

- **Fait par lecture :** [ContractRegistry.cpp](../software/cpp/src/application/ContractRegistry.cpp)
  charge et compte les schémas sans les appliquer intégralement.
  [StationComposition.cpp](../software/cpp/src/composition/StationComposition.cpp)
  recopie certains champs libres de la requête ;
  [ResultAdapter.cpp](../software/cpp/src/adapters/storage/ResultAdapter.cpp)
  effectue des contrôles partiels avant écriture.
  [RunService.cpp](../software/cpp/src/application/RunService.cpp) annonce
  pourtant des contrats « archivés et validés ».
- **Préceptes :** P04, P13, P19. **Impact : fort avant usage qualifiant ; rôle : logiciel.**
- **Correction documentaire Implémentée :** DOC-SW §5 distingue contrat
  déclaré et contrôle effectif. **Correction logicielle Planifiée :** source
  de validation commune à l'entrée et à la finalisation, cohérence des IDs.
- **Clôture :** tests négatifs types/champs requis/inattendus, identifiants
  contradictoires et événements invalides ; aucune finalisation « validée »
  en cas d'échec. Aucun de ces tests n'a été exécuté par l'audit.

<a id="aud-011"></a>
#### AUD-011 — Tests ordinaires dépendants de résultats locaux

- **Fait par lecture :** [TestResultRepository.cpp](../software/cpp/tests/TestResultRepository.cpp)
  exige au moins 59 résultats et trois identifiants historiques ;
  [TestComparisonService.cpp](../software/cpp/tests/TestComparisonService.cpp)
  utilise ces archives et [TestContractRegistry.cpp](../software/cpp/tests/TestContractRegistry.cpp)
  résout un dataset local obligatoire. Le
  [workflow](../.github/workflows/sw0-ci.yml) lance CTest sans fournir ces
  ressources, volontairement absentes de Git.
- **Préceptes :** P05, P11, P13. **Impact : moyen ; rôle : logiciel/validation.**
- **Conséquence déduite :** plusieurs suites n'ont pas leurs prérequis dans
  un checkout neuf ; aucune panne de CI distante n'a été observée ici.
- **Action et clôture — Planifié :** petites fixtures synthétiques pour les
  contrats, intégrations terrain séparées avec prérequis explicites ; suite
  ordinaire réussie sur checkout neuf, intégrations exécutées/absentes distinguées.

<a id="aud-012"></a>
#### AUD-012 — Rejeu LIO sans échéance totale

- **Fait par lecture :** [LioOrchestrator.cpp](../software/cpp/src/adapters/runtime/LioOrchestrator.cpp)
  attend tant que lecteur rosbag et LIO restent vivants. Le délai de vidange
  commence après la fin du lecteur ; l'annulation borne l'arrêt demandé,
  mais aucune échéance totale automatique ne couvre un lecteur bloqué vivant.
- **Préceptes :** P13, P14. **Impact : moyen ; rôle : logiciel/rejeu.**
- **Action et clôture — Planifié :** budget total dérivé de durée/vitesse et
  marge configurée, diagnostic et arrêt ; test d'un lecteur vivant sans
  progression terminé dans le budget. Aucun blocage réel n'est allégué.

<a id="aud-013"></a>
#### AUD-013 — Abstractions compilées sans consommateur actuel trouvé

- **Fait :** [IStationModule.hpp](../software/cpp/include/drone_agricole/station/IStationModule.hpp)
  n'a pas d'implémentation ni d'usage trouvés dans le périmètre inspecté.
  [StationArchitecture.cpp](../software/cpp/src/station/StationArchitecture.cpp)
  décrit dix étapes ; seuls ses tests le consomment.
  [TestStationArchitecture.cpp](../software/cpp/tests/TestStationArchitecture.cpp)
  vérifie des booléens déclarés, pas une frontière de commande effective.
- **Préceptes :** P06, P10, P11, P16, P19. **Impact : faible à moyen ; rôle : logiciel.**
- **Action et clôture — Planifié :** justifier un utilisateur actuel, ou
  différer/supprimer le contrat après vérification de dépendances ; garder la
  cible dans DOC-SW. Ne pas compter ce test déclaratif comme preuve de sûreté.
  Une abstraction inutilisée n'est pas, à elle seule, un défaut de vol.

<a id="aud-014"></a>
#### AUD-014 — Identité du rejeu insuffisamment garantie

- **Fait :** les producteurs FriûlBot
  [FriulBotMap.cpp](../software/cpp/src/adapters/mapping/FriulBotMap.cpp) et
  [FriulBotReconstruction.cpp](../software/cpp/src/adapters/mapping/FriulBotReconstruction.cpp)
  n'inscrivent dans `software` que l'implémentation ; leurs manifestes ne
  suffisent pas à relier commit, image, entrées et calibrations comme demandé
  au §3. Le [Dockerfile](../software/docker/Dockerfile) utilise aussi des bases
  ROS sans digest et APT non figé. Des commits LIO/PX4 et l'image SITL sont,
  eux, épinglés : la reproductibilité est partielle, pas inexistante.
- **Préceptes :** P04, P13, P19. **Impact : moyen ; rôle : logiciel/validation.**
- **Action et clôture — Planifié :** pour le seul banc retenu, lier la preuve
  à l'image exécutée, au logiciel et aux empreintes d'entrées/calibrations,
  puis conserver l'environnement nécessaire. Une preuve doit permettre de
  retrouver sa configuration exacte ; aucune refonte générale Docker requise.

<a id="aud-015"></a>
#### AUD-015 — Résultats historiques insuffisamment reliés à leurs preuves

- **Fait :** les tableaux initiaux §§8–9 et plusieurs lignes §13 donnaient
  des métriques sans résultat exact lié. Les preuves existent localement.
  Le comparatif LIO du 19 août référence les trois runs et retrouve les
  valeurs publiées ; cela n'est pas un nouveau rejeu.
- **Préceptes :** P04, P13, P19, P22. **Impact : moyen ; rôle : validation.**
- **Correction partielle Implémentée :** lien exact ajouté au §8.1.
- **Clôture restante — Planifié :** rattacher les autres affirmations
  utilisées pour une décision à leurs runs et conditions ; ne pas relancer
  une campagne si l'archive existante répond déjà à la question.

<a id="aud-016"></a>
#### AUD-016 — Hypothèse de calibration non bornée par sa réfutation

- **Fait :** le [profil FriûlBot](../configs/datasets/friulbot/test2-2024-07-22.yaml)
  indique une extrinsèque utilisée sans inversion et à valider ; la
  qualification sur correspondances indépendantes n'a pas encore de seuil
  approuvé ni décision explicitée en cas d'échec.
- **Préceptes :** P07, P13, P21. **Impact : moyen ; rôle : perception/validation.**
- **Action et clôture — Planifié, différé :** lors de la reprise du chantier,
  définir prédiction, observation indépendante de soutien/réfutation et effet
  sur la projection. Aucun seuil ni résultat inventé ; ne passe pas devant
  la faisabilité physique du cartographe.

<a id="aud-017"></a>
#### AUD-017 — Consigne locale encourageant des notes dispersées

- **Fait initial :** `research/README.md` demandait études et notes avec
  décisions, contrairement à la consolidation dans cinq documents vivants.
- **Préceptes :** P10, P17, P19, P22. **Impact : faible ; rôle : documentation.**
- **Correction Implémentée :** ressources et preuves techniques, avec
  intégration des décisions dans leur document vivant.
- **Clôture :** instruction locale cohérente ; aucun fichier de recherche
  supprimé et aucun rapport narratif séparé créé.

### 15.3 Couverture des 22 préceptes

Une preuve positive reste limitée au périmètre observé ; elle n'accorde pas
une conformité générale. « Pas d'écart établi » ne signifie pas qualification.

| Précepte | Lecture de l'audit et renvoi |
|---|---|
| P01 First Principles | usage et contraintes physiques à préciser : AUD-001/005 |
| P02 Référentiel validé | priorité choisie, faisabilité et réussite d'usage ouvertes : AUD-001/003 |
| P03 Classification | ordre de reprise introduit ; budgets futurs ouverts : AUD-002/003 |
| P04 Réel observé | preuves existantes réutilisées ; AUD-007/010/014/015 |
| P05 Résoudre à la source | cause des tests dépendants du poste identifiée : AUD-011 ; autres causes non présumées |
| P06 Distinction réelle | couches station justifiées ; contrat inutilisé à revoir : AUD-013 |
| P07 Réversibilité | cadrage Type 1/2 introduit ; feedback et limites à concrétiser : AUD-002/016 |
| P08 Budget d'erreur | portes de sûreté conservées ; prochaine expérience à borner : AUD-004 |
| P09 Test asymétrique | plafonds d'effort/coût et revue manquants : AUD-002/004 |
| P10 Minimum suffisant | fermer configuration et nécessité des ajouts : AUD-003/013/017 |
| P11 Gall's Law | noyau physique/acquisition et banc reproductible à démontrer : AUD-003/005/011/013 |
| P12 Valider avant construire | contraintes physiques à fermer : AUD-001/003/005 ; pas de preuve que toute construction antérieure était injustifiée |
| P13 Boucle fermée | calcul/finalisation distincts déjà présents ; AUD-004/007/008/010/011/012/014/015/016 |
| P14 Arrêt | arrêt sûr existant, arrêt d'investissement incomplet et délai LIO absent : AUD-002/004/012 |
| P15 Avantage cumulatif | contrats, rejeu et documents réutilisables ; arbitrage par friction réelle ajouté via AUD-002 |
| P16 Infrastructure justifiée | adaptateurs LIO comparés sur mesures, pas d'écart par simple multiplicité ; AUD-013 |
| P17 Instructions LLM | entrée méthodologique et autorité clarifiées : AUD-001/009/017 ; aucune technique dépendante d'un modèle introduite |
| P18 Jugement/mécanique IA | pas de LLM en runtime trouvé dans le périmètre ; agents bornés par invariants et contrôles, aucun contournement critique observé, autorité PX4 conservée |
| P19 Source unique | divergences concrètes AUD-006/007/008/009/010/013/014/015/017 |
| P20 Mesurer avant optimiser | compacité avant/après et baseline LIO présentes ; pas de manquement général établi. Gain local ≠ faisabilité globale (AUD-003) |
| P21 Hypothèse réfutable | saturation CPU LIO éprouvée (§8.2) ; réfutations ouvertes AUD-004/005/016 |
| P22 Capitaliser | documents vivants et preuves réutilisables ; résumés/liens/notes corrigés ou ouverts : AUD-006/015/017 |

### 15.4 Vérifications de cette intégration

`T-METH-01` relie `METH-001` à l'intégration documentaire : fidélité du texte
fourni hors adaptation de titres/métadonnées, présence unique P01–P22,
liens locaux ajoutés, concordance des identifiants d'audit, dates/journaux,
et préservation des fichiers hors périmètre. Résultats, revue indépendante
et empreintes dans la [preuve structurée](verification/audit_preceptes.json).

La revue et les contrôles documentaires ne ferment pas les corrections
logicielles, les écarts de registre ou l'empreinte CAO. Builds, tests
fonctionnels, rejeux, recalculs natifs et bancs ne sont pas exécutés : aucun
code exécutable ni modèle physique n'est modifié par cette intégration.


## 16. Journal de modifications

- **25 novembre 2026** — V3-C.2 qualifie la convergence de deux faisceaux sur banc, avec perturbation externe après gel. [Résultat](#cartographe-v3-c2)
- **25 novembre 2026** — V3-A.5 qualifie la préadmission signée de test et précise les relevés qui conditionnent une décision réelle. [Résultat](#cartographe-v3-a5)
- **25 novembre 2026** — Fusion V3-INT.1 et vérification commune sur banc des protections du cartographe. [Résultat](#cartographe-v3-int1)
- **24 novembre 2026** — Qualification logicielle V3-C.1 sur deux bancs, couplage et contre-validation après restriction préenregistrée. [Résultat](#cartographe-v3-c1)
- **24 novembre 2026** — V3-A.4 structure la collecte et la validation de provenance des preuves physiques par occurrence–opération. [Résultat](#cartographe-v3-a4)
- **19 novembre 2026** — Jonction V3-D et contrôle de la non-admission cartographe, avec reprise des observations en lecture seule. [Résultat](#cartographe-v3-d)
- **19 novembre 2026** — Qualification V3-C sur Workholding et C4, avec resserrement après gel et alternative mesurée. [Résultat](#cartographe-v3-c)
- **19 novembre 2026** — Contre-validation croisée V3 B.2 des plans XLink, garde des reçus et variantes de rayon sur banc. [Résultat](#cartographe-v3-b2)
- **19 novembre 2026** — V3-A.3 instruit les autorités UART par occurrence, rejoue les contrôles numériques et prépare les relevés hors tension. [Résultat](#cartographe-v3-a3)
- **19 novembre 2026** — Rejeux d’intégration V3-I sur banc scellé et vérification de la portée A.2 en lecture seule. [Résultat](#cartographe-v3-i)
- **19 novembre 2026** — V3 B.1 exécute les mutations XLink sur deux bancs et vérifie les candidats sauvegardés. [Résultat](#cartographe-v3-b1)
- **18 novembre 2026** — V3-A.1 rejoue l’admission L5 sur banc XLink scellé et vérifie les refus sur le cartographe. [Résultat](#cartographe-v3-a1)
- **18 novembre 2026** — V3-A.2 documente les exclusions et les preuves requises pour les huit issues UART. [Résultat](#cartographe-v3-a2)
- **18 novembre 2026** — V3-A sur le cartographe sans dock. Fermeture, graphe et impact vérifiés sur copies et banc. Admission conditionnelle au périmètre numérique décrit au §12.1.13.

- **17 novembre 2026** — Contrôles locaux avant sauvegarde et intégration Git : compilations réussies, échecs et tests incomplets conservés, périmètre de publication explicité (§6.3).
- **17 novembre 2026** — GO3B exécuté sur copies natives, consolidation et contre-validation. [Verdict NO_GO et couverture](#cartographe-go3b-reconstruction).
- **17 novembre 2026** — Rejeu du gel cartographe et préflight GO3A V2.1 des trois familles. [Résultat et porte finale](#cartographe-go3a-revise).
- **17 novembre 2026** — Requalification indépendante V2.1 après A, B.2 et correction C4 sur banc lié. [Résultats et portée](#requalification-v21-c).
- **17 novembre 2026** — Couverture nominale V2.1 B.2 complète, validation indépendante et résultats distincts du moteur et du prototype. [Clôture XLink](#qualification-xlink-v21-b2).
- **15 novembre 2026** — Qualification indépendante V2.1 sur copies, écart de gel H-01 et contre-épreuves de connectique et de reprise XLink. [Verdict et conditions de reprise](#qualification-integree-v21).
- **15 novembre 2026** — Validation V2.1 multi-documents sur copie du prototype actif, banc L4 XLink et reprise par lots. [Couverture et limites](#preuve-xlink-v21).
- **15 novembre 2026** — Vérification V2.1 de la connectique sur documents, bancs et copie XLink. [Résultat conditionnel](#preuve-connectique-v21).

- **15 novembre 2026** — Préflight V2.1 vérifié sur le dossier H-01.
  Exploration numérique conditionnelle autorisée, réception fermée.
  [Résultats et limites](#preuve-porte-v21).
- **14 novembre 2026** — GO3B clos à l’admission en `NO_GO_MOTIVE`. Gel,
  sources et couverture rejoués, verrous critiques et contrôles candidat non
  exécutés tracés (§12.1.13 et §14).
- **14 novembre 2026** — GO3A conditionnel, preuve de réconciliation exhaustive et critères de reprise H-01 (§12.1.13 et §14).

- **14 novembre 2026** — Qualification GO2bis sur Windows amd64. Corrections
  L2/L4/L5, réouvertures historiques et GO conditionnel borné aux capacités
  démontrées (§12.1.13).
- **14 novembre 2026** — Résultats finaux de réception L5 et limites de
  validation consignés (§12.1.13).
- **13 novembre 2026** — L5, consolidation native unique, reprise de campagne,
  13 contrôles indépendants et critères de passage proposés (§12.1.13).
- **13 novembre 2026** — L4, validation indépendante sur bancs et historiques,
  réouverture en processus neufs et chaîne de preuves L0/T0 (§12.1.13).
- **13 novembre 2026** — L3, décision d’architecture sur bancs synthétiques,
  consolidation, preuve T0 et revue indépendante (§12.1.13).
- **12 novembre 2026** — L2, continuité et raccordement sur banc natif,
  convertisseur 71 lignes / 53 axes et inconnues fournisseur (§12.1.13).
- **12 novembre 2026** — Recherche technique L1 C++17 validée hors FreeCAD,
  avec rejeu F16, rapport HTTPS Basler et inconnues matérielles tracées (§12.1.13).
- **12 novembre 2026** — Audit L0, contrats V2 et conditions de reprise L1.
  Régressions sur banc et empreintes vérifiées. GO 3 ouvert (§12.1.13).
- **11 novembre 2026** — Action 2 du moteur électromécanique. Trois défauts
  corrigés avec régressions. GO conditionnel sur bancs et contre-validation
  historique ciblée (§12.1.13).
- **11 novembre 2026** — Clôture GO 1 sur les bancs, mesure native des
  retenues et des poses discrètes, inventaire complet du prototype avec
  défauts CAO fournisseur (§12.1.13).
- **10 novembre 2026** — Banc du moteur électromécanique, réouverture
  indépendante, rétrovalidation et périmètre des résultats (§12.1.13).
- **9 novembre 2026** — Contrôles de la copie modulaire sur les natifs
  sauvegardés, essais de variantes, contrôle des retenues et revue
  indépendante (§12.1.12).
- **9 novembre 2026** — Contrôles de la refonte du câblage sur copie isolée,
  rapprochement électrique et comparaison des enveloppes de protection.

| Date | Évolution |
|---|---|
| 12 novembre 2026 | Action 3 : F12/F16/F25/P85/F35 consolidés sur copie, réouverture et criblage ciblé exécutés, geste CAN1 simulé. |
| 11 novembre 2026 | Action 3 : gabarit CAN1 coté et sonde candidate testés ; nouveau trajet F35 sauvegardé et assemblage rouvert sur copie. |
| 11 novembre 2026 | Reprise action 3 : X650 corrigé sur copie, sauvegarde et réouverture du prototype complet démontrées ; F12 vers TELEM1 sur copie A1 et accès CAN1 préfiltré. |
| 11 novembre 2026 | Action 3 : référentiel et identité du moteur vérifiés, interconnexions réconciliées, historiques rejoués et trois architectures conditionnelles documentées ; GO 3 ouvert. |
| 28 octobre 2026 | T-SKILL-EMI-02 : autonomie de conception, huit évaluations comportementales indépendantes réussies, régressions et revue de cohérence ; preuves et limites synthétiques sans qualification matérielle (§12.1.11). |
| 28 octobre 2026 | Essais de reconstruction sur copie, recalculs frais, équivalence volumique, F16 et contrôles globaux bornés ; inconnues, reprises et absence de qualification globale explicites (§12.1.12). |
| 27 octobre 2026 | T-SKILL-EMI-01 : skill d'intégration des faisceaux, tests C++/BRep/natifs/isolation, validation officielle et revue indépendante ; aucun faisceau drone reconstruit ni qualification physique (§12.1.11). |
| 26 octobre 2026 | Reprise X650 : kit 2 000 g hors bilan, 24 estimations OEM par densités analogues, scénarios ESC/hélices distincts et intersections internes des bras à résoudre ; lot non clos (§14). |
| 26 octobre 2026 | Reprise ORCH : collisions ciblées supprimées, fraisures, têtes CHC et placements contrôlés, réouverture et 12 977 paires examinées ; bilan enrichi, poids Waveshare conditionnels et 70 problèmes massiques explicites dans la BOM. Clôture complète et reprise des simulations encore conditionnées (§14). |
| 25 octobre 2026 | ORCH-CAO-MASSE-1 : recherches, reconstructions, intégration et bilan partiel exécutés ; couverture quantitative, réouverture, défauts PM08/QS8 et inconnues conservés, lot non clos et reprise des simulations conditionnée (§14). |
| 24 octobre 2026 | Passerelle CAO → Gazebo intégrée à Simulations : service UI/CLI commun, export isolé et contrôlé, aperçu navigable, annulation et tests ; chargement Gazebo réel, physique À valider (DOC-VAL §10.2). |
| 24 octobre 2026 | ORCH-GZ-1 : banc Docker/ROS reconstruit, airframe 40000 et capteurs synthétiques corrigés ; six essais SITL courants carré/perte Offboard/annulation finalisés, T0 et revue indépendante ; batterie forfaitaire observée, fidélité physique et autonomie couplée À valider (DOC-VAL §9.3). |
| 23 octobre 2026 | ORCH-GZ-1 : dérivation, SDF/airframe d'aperçu, modules C++17, 54 cas énergie et T0 effectif ; tests natifs, blocage Docker, couplage batterie absent et mesures physiques explicités, relais ORCH-GZ-2 et T-CARTO-GZ-01..04 (§9.3–9.4). |
| 23 octobre 2026 | Trois domaines Gazebo explicitement demandés et séquencés entre orchestrateurs (§9.4) ; relais par manifeste technique Planifié, propriétaires de fichiers et régressions communes, données physiques manquantes distinguées des travaux indépendants. |
| 23 octobre 2026 | Priorité utilisateur Gazebo : portance avec charge, consommation et autonomie depuis la CAO active ; lots CGZ-01..05 et tests Planifiés, modèles physiques et énergie distingués du visuel et de la batterie SITL ; inventaire CAO/BOM et données manquantes consignés (§9.3). |
| 23 octobre 2026 | Évaluation du démarrage Gazebo (§9.2) : accès Docker non établi, socle historique distingué des mondes agricoles absents, reprise et premier VB01 séquencés et estimés ; preuves historiques et limites de finalisation explicitées, aucun scénario exécuté. |
| 23 octobre 2026 | UI-V3-001/002/003 : maquettes MagicPath transposées, services locaux et BOM reliés aux tests ; compilation Windows, suite CTest et captures, limites matérielles et environnements non exécutés explicités (§10.1). |
| 22 octobre 2026 | T-CARTO-CAO-PROTO-01 : construction finale 118 références/346 occurrences, contrôles frais des liens, recalculs, collisions, 53 parcours, pièces, guides, départs, colliers et retenues conformes dans leurs périmètres ; revue et inspection visuelle. BOM/classeur rapprochés, 108 contrôles documentaires ; 20 réserves matérielles et aucune qualification physique (§14.3–14.4). |
| 21 octobre 2026 | Contrôle cumulé des quatre guides étendus : deux intersections intersupports identifiées puis corrigées, sans collision câble/support dans cette passe. Contrat exhaustif des 53 parcours et preuve de retenue des spires USB en consolidation ; contrôles finaux liés aux empreintes encore requis (§14.4). |
| 16 octobre 2026 | Construction intégrée 110 références/313 occurrences ; 53 géométries Cable Workbench recalculées sans erreur géométrique mais erreurs d'affichage de couleurs observées. Neuf collisions de guides/fixations/Type A identifiées, corrections et nouvelle reconstruction en cours. Contrôles locaux de retenues réussis, couverture globale et contrôles finaux encore ouverts (§14.4). |
| 19 octobre 2026 | Construction complète 111 références/314 occurrences. Recalcul des 53 câbles réussi ; correction du format d'apparence vérifiée par réouverture sans MemoryError. Retenues locales intégrées ; vérification globale des collisions et de la couverture en cours (§14.4). |
| 13 octobre 2026 | Refonte énergie supérieure/faisceau53 parcours Cable Workbench en cours de contrôle ; garde nominale 18 mm, P72/P73 implantés, P75 en étude. Les contrôles et104 vérifications documentaires du12 ne couvrent pas les fichiers modifiés ; réouverture, interférences, retenues, synchronisation et réexport requis. Aucune qualification physique (§14.3–14.4). |
| 12 octobre 2026 | Précision utilisateur : terminal au sol portable/tablette/téléphone, choix selon ergonomie ; chargeur60 W hypothétiques. Deux sélections différées hors CAO,18 compléments embarqués ; aucun natif ni logiciel modifié. |
| 12 octobre 2026 | T-CARTO-BOM-PROTO-01 :104 contrôles réussis. T-CARTO-CAO-PROTO-01 :245 liens/poses,20 équipements et32 fixations contrôlés après corrections, empreintes conservées ; limites SSD/microSD, garde énergie et20 compléments ouverts, aucune qualification physique (§14.3–14.4). |
| 10 octobre 2026 | SkyRC S100neo SK-100202 inscrit comme choix de définition en quantité 1 ; T-CARTO-CHARGE-DOC-01 actualisée, qualification des réglages, du raccordement et de la recharge toujours À valider (§14.3). |
| 10 octobre 2026 | Référence Logic RC O-LGL-CLQS8 inscrite pour le cordon de recharge, quantité 1 et connecteurs intégrés ; catalogue fabricant rapproché, accouplement avec D-MAX B9310 et recharge À valider, aucun essai matériel (§14.3). |
| 10 octobre 2026 | T-CARTO-CHARGE-DOC-01 : correction de connectique documentaire, sortie de charge S100neo XT60 et cordon XT60 → QS8-S précisés dans la BOM ; chargeur candidat, accouplement/polarité et essais matériels toujours À valider (§14.3). |
| 10 octobre 2026 | T-CARTO-CHARGE-DOC-01 : recharge via port BMS protégé documentée, S100neo/D200neo candidats et maintien NPB-120/240 écarté ; courant OEM, réglages et essais de recharge ouverts. Minimum PC accepté pour la définition ; export contrôlé, qualification physique À valider (§14.3). |
| 10 octobre 2026 | Prise FAN : contrôle documentaire T-CARTO-FAN-CONN-01 consigné avec sources et empreintes ; courant nominal sous limite publiée et DF13 candidat, tension/brochages/accouplement/portée ouverts ; raccordement direct non démontré, qualification À valider, BOM inchangée (§14.3). |
| 10 octobre 2026 | Deux BOM hiérarchiques puis retrait JETI/commande/F39 du prototype, W38 direct PM08 ; QS8-S D-MAX B9310, SSD Samsung MZ-V9S1T0BW 1 To, Waveshare Orin-FAN-PWM SKU 24076 et Fujinon CF8ZA-1S 8 mm choisis ; 24 principaux, 97 embarqués, 21 exclus, 42 références embarquées vides ; 96 contrôles des exports réussis. Comparaison à 10 m conservée dans T-CARTO-OPT-01 ; PC ligne 30 : portable de récupération distinct du poste fixe, minimum proposé, matériel et essais ouverts ; qualification physique À valider (§14.3). |
| 9 octobre 2026 | T-CARTO-BOM-PROTO-01 : couverture de la sélection prototype, inclusions/retraits et export contrôlés, revue indépendante ; faisabilité physique toujours À valider (§14.3). |
| 8 octobre 2026 | Audit transversal des 22 préceptes : 17 écarts/lacunes sourcés, ordre de reprise centré sur la faisabilité physique, empreinte CAO divergente signalée, autorité FriûlBot et lien LIO corrigés ; intégration documentaire contrôlée, sans nouvelle qualification matérielle ou logicielle. |
| 5 octobre 2026 | Protocole T-CARTO-HIER-BAT-01 : séparation67/72, principal6+6, identité des références/poses/couleurs et extraction unique ; réouverture après sauvegarde et registres réussis, sources conservées et anciens booléens transférés par identité ; physique À valider (§12.1.10). |
| 5 octobre 2026 | Compactage pack/BMS/TE :147 sources relues, cinq routes BOP, axes/entrées et huit poses d’extraction contrôlés ; comparaison depuis1ccbad81 sur bornes recalculées ; contrôle complet et persistance SA08 réussis, aucun essai matériel (§12.1.9). |
| 5 octobre 2026 | Première implantation supérieure historique Git1ccbad81 : comparaison géométrique BMS recalculée par périmètre, anciens contrôles arrière historiques ; contrôles BMS/extraction,37 routes SA08 enregistrées et registres réussis, aucun essai matériel nouveau (§12.1.9). |
| 5 octobre 2026 | ContrôlesCAOBMS/UART/TE etschéma40liaisons, revueindépendante etempreintescourantes ; limitesphysiquesnonqualifiées (§12.1.9) |
| 5 octobre 2026 | Préparationinitiale Plan de validation BMS embarqué/blind-mate : portée séparée de la CAO TE sans BMS, critères de charge/coupure/communication/implantation/cycles à fermer ; lecture seule et sources fabricant, aucun nouvel essai matériel (§12.1.9) |
| 4 octobre 2026 | CAO étage énergie et liaison directe candidate AWG8/742F5 M5 au TE : retrait XT90-S/AWG10/P42, supports repris ; contrôle du seul pack nominal et rendu ; enveloppe d'étude/lot/physique **À valider**, adaptateur de charge protégé **Planifié** (§12.1.8) |
| 4 octobre 2026 | Dock coloré et repli natif de deux cordons ; réouverture et collisions vérifiées,629 BRep préservés, hauteur−29,3%, intersectionP49 toujours ouverte ; état initial dans Git et nouvelles empreintes distinctes des preuves historiques (§12.1.7) |
| 4 octobre 2026 | Tri des sous-assemblages : miroir autonome et 321 empreintes préservées, réouvertures FreeCAD courant/archive séparées sans erreur, reprise de source châssis contrôlée ; géométrie et essais physiques inchangés (§12.1.6) |
| 4 octobre 2026 | Calcul conditionnel GNSS/radio sur plateaux : volumes et empreintes contrôlés, matériaux hypothétiques, aucun crédit en double des supports absents de la cible ; gain net et qualification physique ouverts (§12.1.5) |
| 3 octobre 2026 | Revue stack sur plan Holybro : neuf natifs, CA01 courante et perçages, fixation communeP17 parM3×65 et appuis24/2 ; contraintes de montage, précharge et isolement ouvertes (§12.7.14) |
| 3 octobre 2026 | Configuration cible 60 postes et faisceau système : 35 routes natives, couverture 33 Wxx, préservation des sources et bilan cuivre ; fixations, rayons, interférences et masse cible ouverts (§12.1.4) |
| 3 octobre 2026 | Cassette 20 Ah et rehausse 20 mm : références natives, visserie, contrôles de course, enveloppes de pales et BOM ; anomalies des STEP TE et essais de verrouillage/électricité/masse explicitement ouverts (§12.1.3) |
| 2 octobre 2026 | Préétude batterie interplateaux : logement 50 mm, occupants avionique et rehausses dimensionnelles +20/+30 mm ; accès latéral et hélices hypothétiques distingués de l'absence de collision OEM ; aucune modification ni qualification de structure (§12.1.2) |
| 2 octobre 2026 | Reprise batterie 6S : défauts historiques identifiés ; neuf natifs/deux assemblages/quinze liens candidats vérifiés, 23 poses de capot et sorties verticales sans collision sur le périmètre déclaré ; encoche P23/P15 corrigée, empreintes actives conservées ; verrou et essais physiques À valider (§12.1.1) |
| 2 octobre 2026 | CA01 : routage complet, 1 255 segments / 251 vias / 10 zones et sept zones de règles Kelvin ; continuité large candidate des bus calcul/LiDAR/AUX et radio contrôlée ; DRC natif 0 violation / 0 connexion / 0 parité selon configuration ; 13 protocoles proposés et dossier fabricant provisoire,44 MPN/process/protections et banc ouverts, aucune qualification physique (§12.7.13) |
| 2 octobre 2026 | CA01 : protocole électrique E01–E06, thermique TH01–TH03 et préconformité CEM01–CEM04 planifié, critères/gates ouverts ; dossier fabricant candidat stack/vias/perçages/process sans commande ni qualification physique (§12.7.11–12) |
| 2 octobre 2026 | Finalisation CA01 : 14 contrôles de revue indépendante, reconstruction isolée équivalente et gardes de protection conformes ; ERC/variante/calculs/shunt/DRC rejoués, 218 connexions restantes ; aucune qualification matérielle (§12.7.10) |
| 1 octobre 2026 | CA01 : démarrage routage4couches, plans GND/batterie protégée, vias par potentiel, variante DAP Ø0,3 et exclusion Kelvin ; contrôles DRC0/parité0 avec218 connexions restantes, conservation schéma/mécanique et revue indépendante ; thermique/CEM/fabrication non exécutées (§12.7.10) |
| 1 octobre 2026 | CA01 :10familles/16occurrences de modèles3D remplacées, sources locales,308solides/141composants ;réouverture et interférences contrôlées,RP4TD détaillé introuvable (§12.7.9) |
| 1 octobre 2026 | RP4TD : symbole dédié et quatre pads THT candidats ;230contrôles/ERC0,parité0,courtyards sans chevauchement,155empreintes sans routage ; cotes photographiques non qualifiées (§12.7.8) |
| 1 octobre 2026 | R116 remplacé par CSM3637 standard après acceptation ±0,1 %, calculs et contrôles de schéma/placement/stack actualisés ; plans/vias Planifiés et tenue matérielle/impulsionnelle À valider (§12.7.6) |
| 1 octobre 2026 | 23 empreintes attribuées et cuivre Q5A/shunt corrigé ; préplacement151composants+4fixations sans routage, parité et chevauchements0,30perçages thermiques ouverts ; trois revues indépendantes, stack native et PDF6pages vérifiés ; qualification physique À valider |
| 1 octobre 2026 | Reprise LM74800 page 2 : équivalence des 111 réseaux et conservation des composants, ERC vierge et PDF inspecté ; aucun essai matériel pour cette retouche graphique |
| 1 octobre 2026 | Export PDF CA01 vérifié : six pages, provenance par empreintes, inspection des pages 2/3 et copie de vérification identique ; aucune modification électrique |
| 1 octobre 2026 | Reprise graphique page 2 et symboles alimentation/GND ; conservation électrique, ERC et revue des rendus ; aucun essai matériel |
| 30 septembre 2026 | Page 3 radio inspectée après reprise graphique ; trois contrôles de conservation sur 151 composants et 111 réseaux, 221 invariants et ERC 0/0 ; aucune modification électrique ni essai matériel |
| 30 septembre 2026 | Recette§12.7.2 pour tempsGNSS physique candidat : Schmitt/TVS, translations, RS232/railAiry et référenceOrinCSI ; 44 contrôles arithmétiques, sortiesDNP, niveaux et séquencements à valider ; aucun essai matériel |
| 30 septembre 2026 | T-AIRY-SYNC-01 précise configuration/persistance RMC UART2 et alternatives tunnel/reconstruction ; support nœud/proxy, continuité sans GUI, coexistence GNSS/RTCM et lien PPS à vérifier ; aucun essai matériel |
| 30 septembre 2026 | T-AIRY-SYNC-01 complété : décision Jetson/ROS 2, autorité unique, demandes/ACK/fronts/images, réponses perdues, doublons, ordres périmés et association aux flux continus ; protocole Planifié / À valider, aucun essai matériel |
| 30 septembre 2026 | T-AIRY-SYNC-01 précise la mesure PPS UART2 pin5/6 à haute impédance puis sous charge connue ; hypothèse 3,3 V distincte de l'alimentation 5 V, contrôles hors tension séparés des mesures actives ; aucun essai exécuté |
| 30 septembre 2026 | T-AIRY-SYNC-01 complète TX UART2/GPRMC : mesure électrique, décodage RMC/GP, conversion RS232 candidate vers Airy, branche Orin logique et persistance CAN/PX4 ; aucun essai matériel exécuté |
| 30 septembre 2026 | Dimensionnement candidat CA01 et sources archivées ; 112 invariants, ERC 0/0, 27 contrôles analytiques ; corrections bootstrap/shunt/OV et revue indépendante ; PCB/banc non exécutés, non fabricable |
| 29 septembre 2026 | Reprise compacte de CA01 et contrôle de topologie adapté : 22 invariants ; diviseurs et petits passifs LM76003 candidats documentés ; aucun essai matériel ni qualification de fabrication |
| 25 septembre 2026 | Schéma CA01 V0.5-pre repris : 20 invariants netlist conformes, 53 composants/51 réseaux, 4 erreurs ERC ouvertes, BIAS LM76003 corrigés et blocs de temps/caméra abstraits ; aucun banc ni PCB |
| 25 septembre 2026 | T-AIRY-SYNC-01 révisé : Helical DroneCAN candidat, PPS/GPRMC Airy/Orin, trigger Pixhawk, retour ExposureActive/CAP1 et limites du PPS Pixhawk ; Base conservée et rover patch réévalué sans changer le trajet RF/RTCM ; aucun essai matériel |
| 25 septembre 2026 | PDB Holybro 300 A top-entry candidate et départ W08/XT30 ajoutés au protocole de banc ; synchronisation Airy GNSS ou PTP/gPTP et SYNC_OUT1 cadrés d'après le guide v1.3 ; aucun essai matériel exécuté |
| 24 septembre 2026 | H-RTK F9P Base/Rover sélectionnés ; protocole tri-flux RTCM, RC, commandes ponctuelles et télémétrie sur ELRS ajouté, Offboard local et seuils à valider ; aucun essai RF exécuté |
| 24 septembre 2026 | protocole V0.5 planifié : baseboard Holybro/6X/Orin NX 16 Go, deux entrées POWER, CAN1 séparé, 5 V CA01 et XT30 12 V candidat ; V0.4 et ses preuves conservées comme historiques, aucun essai V0.5 exécuté |
| 22 septembre 2026 | câblage cible V0.4 PM08-CAN, 31 liaisons ; puissance/CAN séparés, BEC1/BEC2 affectés ; KiCad interne V0.3 non migré |
| 22 septembre 2026 | PM02D en tête V0.3, faisceau adapté, mesure globale via W06 ; T-PM-01..04 planifiés ; thermique non qualifiée |
| 22 septembre 2026 | audit 85 A : recalcul conforme, besoin continu et choix PM non qualifiés |
| 21 septembre 2026 | PM externe et CA01 V0.2 ; W01..W30 ; 14 invariants conformes et 3 erreurs ERC ouvertes ; preuves V0.1 archivées |
| 20 septembre 2026 | contrôle statique CA01 : structure, netlist, ERC, revue des interfaces et recette T-CA01 ; aucune qualification matérielle |
| 16 septembre 2026 | ajout des essais planifiés AUTO/MANU, couverture sur relief et RF commun RC/MAVLink ; aucune nouvelle exécution matérielle |
| 16 septembre 2026 | contrôles capteurs et avionique, revue indépendante de traçabilité, limites et essai du pont KiCad |
| 13 septembre 2026 | consolidation des décisions actives de qualification et d'environnement ; retrait du registre ADR |
| 10 septembre 2026 | création par consolidation du plan de validation, des inspections, campagnes LIO/PX4, jalons T0/SW0, essais EscaYard/FriûlBot et état de qualification matériel |
| 10 septembre 2026 | preuve d'assemblage de scans, surface PLY, diagnostics ICP et tests de rejeu ; limites de qualification maintenues |
