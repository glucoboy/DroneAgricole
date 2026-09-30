# Validation et qualification

| Champ | Valeur |
|---|---|
| Référence | `DOC-VAL` |
| Nature | document vivant transversal |
| Dernière mise à jour | 1 octobre 2026 |
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
| Images `0029SET.zip` | 5 518 848 615 octets ; MD5 `14ded790d1771006218fc02980ee3eb8` |
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

| Test / exigence | Protocole et critère | État au 20 septembre |
|---|---|---|
| `T-CA01-01 / CARTE-001` | revue schéma/netlist puis inspection du faisceau : aucun chemin propulsion ; mesure globale identifiée | netlist partielle vérifiée ; faisceau et mesure globale **À valider** |
| `T-CA01-02 / CARTE-002` | défauts limités sur chaque départ charge utile : aucun reset Pixhawk ; si le 5 V radio CA01 est perdu, perte RC détectée et repli PX4 sûr | non exécuté ; critère cible V0.5 |
| `T-CA01-03 / CARTE-003` | rampes 6S, inversion contrôlée, appel et transitoires selon enveloppe approuvée : protections et seuils respectés | protections et protocole détaillé **À valider** |
| `T-CA01-04 / CARTE-004` | charges statiques/dynamiques 12 V calcul vers XT30 Holybro, puis Orin NX/USB/SSD : stabilité, polarité, limite porteuse et thermique respectées | non exécuté ; LM5146 réel candidat depuis30/09, boucle/Ceff/charges à valider |
| `T-CA01-05 / CARTE-005` | source 12 V capable d'au moins 2 A, démarrages et acquisition Airy à chaud : aucun reset | non exécuté |
| `T-CA01-06 / CARTE-006` | 5 V local CA01, charges radio/auxiliaires, défauts et séquences : budgets fermés, plages respectées, aucun retour vers POWER1/2 | V0.5-pre : F102 entre 5V_AUX et 5V_RADIO vérifié en netlist ; budgets et banc **À valider** |
| `T-CA01-07 / CARTE-007` | révisions PM/porteuse et faisceau identifiés ; BEC1→POWER1, BEC2→POWER2, CAN1 distinct ; budgets ≤3 A chacun, bascule et calibration PX4 conformes | schéma V0.3 historique ; matériel V0.5 non exécuté |
| `T-CA01-08 / CARTE-008` | mesurer UART et état hors tension avant de monter R401/R402 ; essais RC/QGC avec Jetson arrêté, puis `T-RF-01..06` | DNP vérifié ; banc et RF non exécutés |
| `T-CA01-09 / CARTE-009`, `ELEC-TIM-001` | qualifier CA01 : W36 GNSS→CA01 sans retour +5 V, W23/W24 PPS/GPRMC tamponnés vers Airy/Orin, référenceIO J509, adaptation AUX Pixhawk vers opto Basler Line1, retour réel ExposureActive Line2 vers FMU_CAP1, niveaux et isolement ; suivre `T-AIRY-SYNC-01` (§12.8) | schéma physique temps/trigger/capture candidat Implémenté ; sortiesR530–R533DNP, niveauxOEM/référenceIO et banc À valider ; recette§12.7.2 |
| `T-CA01-10 / CARTE-010` | CAO avec porteuse Holybro/Orin NX/PM08/CA01 et vrais connecteurs puis montage SA03/SA04 : accès, fixations, isolation et thermique conformes | non exécuté ; ancienne CAO conservée |
| `T-CA01-11 / CARTE-011` | charges simultanées, thermique, bruit et CEM puis progression moteurs autorisée : marges et capteurs conformes | non exécuté |
| `T-CA01-12 / CARTE-012` | sources, BOM, empreintes, netlist, ERC puis DRC : aucune valeur ouverte et revue complète avant fabrication | V0.5-pre depuis30/09 : 221 invariants selon preuve régénérée ; GNSS en composants physiques candidats, interfacesOEM/empreintes/BOM/PCB incomplets ; **non conforme pour fabrication** |

Aucun essai de charge, thermique, RF, synchronisation sur capteurs, simulation
électrique, DRC de carte routée ou vol réalisé : composants et protections
incomplets, PCB non conçu et matériel non assemblé. Ces absences ne sont pas
compensées par les contrôles statiques.


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
| `CARTE-001..012` | carte avionique CA01 | `T-CA01-01..12`, §12.2 et §12.7.1–12.7.2 | 221 invariants et 44 contrôles analytiques ; ERC selon preuve régénérée ; banc non exécuté | **Implémenté** en schéma préliminaire ; matériel **À valider**, fabrication non conforme |
| CAB-CARTO-001, CARTE-002/004/006/007/010/011, ELEC-PWR-001/002 | baseboard Holybro, Pixhawk 6X, PM08-CAN, PDB Holybro 300 A top-entry candidate, W08/CA01 et Jetson Orin NX 16 Go ; cible V0.5 | T-PM-V05-01..06 et T-PDB-V05-01, §12.7 | protocole planifié ; aucun faisceau ni essai V0.5 exécuté | **Planifié / À valider** |
| MAP-FUN-001, ELEC-TIM-001, CARTE-009, SW-TIM-001 | Jetson mission_manager/sensor_manager et adaptateur PX4 ; H-RTK Helical DroneCAN candidat, PPS/GPRMC via CA01 vers Airy/Orin, trigger AUX Pixhawk, Basler ExposureActive vers FMU_CAP1 | T-AIRY-SYNC-01, §12.8 ; T-CA01-09, §12.2 | responsabilités clarifiées ; commande, signaux, datation et association non qualifiés ; PPS Pixhawk non acquis | **Planifié / À valider** |
| `HW-BAT-SWAP-01..06` | cassette batterie | inspection, efforts, cycles et défauts | protocole défini dans DOC-MEC | non exécuté |

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
