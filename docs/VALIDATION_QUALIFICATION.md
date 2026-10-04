# Validation et qualification

| Champ | Valeur |
|---|---|
| Référence | `DOC-VAL` |
| Nature | document vivant transversal |
| Dernière mise à jour | 4 octobre 2026 |
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
| Images `0029SET.zip` | 5 518 848 615 octets ; MD5 `14ded790d1771006219fc02980ee3eb8` |
| Durée / messages | 1 283,858 s / 977 318 |
| Capteurs utiles | 12 728 scans, 256 812 IMU, 638 déclenchements, 638 jeux × 5 TIFF, 3 855 GNSS |

Le bag est un conteneur mixte. L'allowlist sépare perception
(LiDAR, IMU, déclenchements, TIFF, calibrations) et évaluation (GNSS, odométrie
roues et poses SLAM publiées). Les bags d'indices NDVI/GNDVI/NDRE des auteurs
sont exclus de la prédiction. FriûlBot qualifie une chaîne logicielle de
perception en vigne, pas le montage Airy/Basler ni la dynamique du drone.

## 8. Résultats de localisation

### 8.1 Comparaison de référence BotanicGarden à `1×`

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
approbation/signature de carte, mission et transfert ne sont pas qualifiées.

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
| `SYS-FUN-001` | pont d'état PX4–ROS 2 | topics, diagnostics, SITL | odométrie observée ~100 Hz | conforme au banc SITL |
| `SYS-FUN-004` | runner Offboard + PX4 | carré 2 m | quatre segments et posé | conforme au banc SITL |
| `SAFE-REQ-001` | frontière PX4/ROS 2 | revue des interfaces et runners | aucun topic actionneur direct | conforme au lot A |
| `SAFE-REQ-002` | failsafe PX4 | coupure réelle des consignes en SITL | `AUTO_LAND` en 1,099 s puis posé | conforme au banc SITL |
| `SYS-FUN-007/008/009`, `SAFE-REQ-010`, `ELEC-LNK-001/002` | PX4, mission, RF commun et QGC | `T-RF-01..06`, §9.1 | présélection documentaire ; aucune exécution RF | **Planifié / À valider** |
| `SW-RTK-001`, `SYS-FUN-009`, `ELEC-LNK-001/002/003` | H-RTK F9P Base retenue, rover patch réévalué au profit du candidat Helical DroneCAN STM32G4, QGC, Backpack, ELRS/RP4TD, PX4 | `T-RF-06`, §9.1 : RTCM + commandes ponctuelles + RC + télémétrie | choix rover temporel et débit, marge, reprise RF non mesurés | **Planifié / À valider** |
| `MAP-FUN-009` | planification et suivi de couverture | `T-MAP-COV-01`, §9.1 | aucun résultat de couverture de parcelle qualifié | **Planifié / À valider** |
| `QUAL-REQ-001` | Docker, contrats et runners | builds, CTest, smokes | PC/`amd64` conforme ; cible **À valider** | partiel |
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

## 14. Actions de qualification ouvertes

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

## 15. Journal de modifications

| Date | Évolution |
|---|---|
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
