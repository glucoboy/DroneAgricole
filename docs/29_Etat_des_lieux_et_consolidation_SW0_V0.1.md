# État des lieux et consolidation SW0

| Champ | Valeur |
|---|---|
| Référence | DOC-29 |
| Version | V0.1 |
| Date | 2–5 septembre 2026 |
| Statut | Fermé — baseline locale Windows/Linux amd64 ; réserves de qualification tracées par ADR-0011 |
| Références | DOC-00, DOC-20, DOC-26, DOC-27, DOC-28, ADR-0003, ADR-0006, ADR-0007, ADR-0011 |

## 1. Objet

SW0 consolide le socle logiciel avant le démarrage du lot B1. Il ne modifie ni
la répartition de sûreté entre PX4 et ROS 2, ni les choix algorithmiques. Il
établit une baseline reproductible, explicite les preuves disponibles et
sépare les validations locales des qualifications encore **À valider**.

La sortie de SW0 est une condition d'entrée de B1, pas une qualification au vol.

## 2. État des lieux au démarrage

### 2.1 Éléments opérationnels préliminaires

- application desktop C++17 / Qt 6 configurable par CMake ;
- contrats T0, catalogue de runners, historique, rechargement et comparaison ;
- carte 3D interactive, accumulation LiDAR bornée et pont de télémétrie C++ ;
- adaptateur BotanicGarden et outils C++ d'analyse ATE/RPE ;
- images Docker des trois moteurs LIO et du pont PX4–ROS 2 ;
- séparation de sûreté conservée : PX4 assure le vol critique, ROS 2 fournit
  uniquement les consignes et fonctions avancées.

### 2.2 Preuves locales relevées le 2 septembre 2026

| Vérification | Résultat |
|---|---|
| Configuration CMake `desktop-debug` | Réussie |
| Construction C++17 / Qt 6 Debug | Réussie |
| Suite CTest desktop | 12 tests sur 12 réussis |
| Test fumée de l'application Qt | Réussi hors écran |
| Image Docker Qt/ROS 2 `linux/amd64` | Construite, cible `ros-humble-qt-dashboard` |
| Santé du pont de télémétrie | `status=ok`, schéma `drone_agricole.telemetry_snapshot.v1`, domaine ROS 42 |
| Audit du code actif | 80 fichiers C/C++, 15 fichiers de test C/C++ et un fichier `.ui` |

Ces tests Windows couvrent le noyau, l'interface et les adaptateurs locaux. Ils
ne remplacent pas les tests ROS 2 réels en conteneur, car les variantes sans
ROS 2 natif utilisent des adaptateurs de remplacement.

### 2.3 Maturité fonctionnelle

| Domaine | Maturité observée | Limite principale |
|---|---|---|
| Architecture système et station | Approuvée | fonctions métier B1 et suivantes majoritairement planifiées |
| Socle T0 de simulation | Opérationnel préliminaire | qualification multi-plateforme incomplète |
| LIO sur BotanicGarden | Opérationnel préliminaire | répétitions longues et Jetson **À valider** |
| PX4 SITL | Opérationnel préliminaire | carré et perte Offboard rejoués avec succès en SW0 ; répétabilité et transposition hors SITL **À valider** |
| Simulation viticole | Préliminaire | scénarios `VINEYARD_BENCH_V01` documentés mais non implémentés |
| Station métier B1 | Architecture / prototype | schémas et import reproductible à implémenter |
| Matériel | Conception préliminaire | nomenclature, budgets et bancs absents |

## 3. Risques de baseline

Les constats ci-dessous décrivent les risques relevés au lancement. Leur
traitement est suivi dans la matrice SW0 et les résultats d'exécution ; le
découpage Git réalisé figure en §3.1.

### SW0-RISK-001 — état Git non consolidé

La migration C++17 / Qt 6 est présente dans le répertoire de travail mais n'est
pas encore organisée en commits de consolidation. Le dépôt local ne possède
qu'un commit initial et aucun dépôt distant n'est configuré. Une validation
technique ne doit donc pas être confondue avec une baseline récupérable.

Le découpage des commits doit préserver les changements locaux existants. Un
commit global automatique est interdit tant que les groupes migration,
documentation, infrastructure et preuves n'ont pas été revus séparément.

### SW0-RISK-002 — couverture de plateforme incomplète

La construction native Windows et les images Linux `amd64` à l'état source
courant sont démontrées. La CI n'était pas versionnée au démarrage de SW0 et sa
première exécution distante reste **À valider**. Le noyau propriétaire C++/ROS 2
a compilé pour `linux/arm64`, mais l'image Qt/LIO complète n'a pas été produite :
la compilation LIO-SAM sous QEMU a saturé le moteur Docker. JetPack, l'image
complète et les performances Jetson restent **À valider** sur un hôte ARM natif.

### SW0-RISK-003 — preuves d'intégration encore partielles

Les smokes LIO, l'interface temps réel et les deux scénarios PX4 complets sont
démontrés avec le port C++. Trois rejeux courts post-migration de FAST-LIO2 et
trois de LIO-SAM sont disponibles. Ils révèlent toutefois une variabilité
d'initialisation et de comptage sur un extrait de cinq secondes. Les longues
campagnes LIO et leurs seuils de répétabilité restent donc **À valider** avant de
figer une baseline candidate.

### SW0-RISK-004 — documentation active hétérogène

Certains guides conservaient des références à l'ancienne interface Web ou à des
services supprimés. SW0 doit distinguer les protocoles historiques des commandes
actuelles afin d'éviter une procédure inexécutable.

### SW0-RISK-005 — environnement Docker Desktop récupéré, cause à surveiller

Chaque saturation QEMU a laissé des sockets Windows AF_UNIX orphelins dans
`AppData/Local/Docker/run` et `AppData/Local/docker-secrets-engine`. Le symptôme
correspond aux incidents Docker Desktop Windows
[#536](https://github.com/docker/desktop-feedback/issues/536) et
[#554](https://github.com/docker/desktop-feedback/issues/554). Après redémarrage
du poste, les répertoires de sockets ont été renommés de façon réversible et
`EnableDockerAI` a été désactivé dans `settings-store.json`, avec sauvegarde du
fichier. Docker Desktop a ensuite redémarré normalement, sans réinitialisation
usine ni suppression d'image, volume ou dataset.

Les sauvegardes locales portent le suffixe `recovery-sw0-20260904` ou
`recovery-sw0-20260905-ai-disabled`. Elles restent hors dépôt. La stabilité des
prochains redémarrages reste **À valider** et les builds LIO arm64 sous QEMU
restent suspendus sur cet hôte.

### 3.1 Consolidation Git réalisée

La branche `codex/sw0-consolidation` conserve les groupes suivants :

| Commit | Périmètre |
|---|---|
| `8ecf352` | migration propriétaire C++17/Qt 6, contrats et tests |
| `8361698` | Docker, Compose, patches et workflow CI SW0 |
| `77bb878` | architecture, ADR, contexte et guides C++17/Qt 6 |
| `c841ceb` | étude viticole candidate DOC-30, isolée de SW0 |
| `ad4b102` | correction de l'alignement ATE et régression des trajectoires planes |
| `32b90ef` | parallélisme borné du noyau et de Qt dans Docker |
| `0f3b25b` | précision des petits angles, validée sous Windows et Linux |

Les changements préexistants sont conservés ; les résultats, rosbags, datasets
lourds et caches restent exclus de Git. Aucun dépôt distant n'est configuré.
Le tag local `sw0-v0.1` identifie le commit documentaire de clôture. Les travaux
indépendants apparus pendant la consolidation restent hors de ce commit.

## 4. Travaux SW0

| ID | Travail | Critère de sortie | État initial |
|---|---|---|---|
| `SW0-CFG-001` | inventorier et séparer les changements Git | groupes de commits proposés et aucun changement local perdu | Conforme — commits séparés et baseline locale `sw0-v0.1` |
| `SW0-CI-001` | automatiser CMake/CTest sous Windows et Linux `amd64` | workflow versionné et commandes locales équivalentes | Conforme localement — exécution sur forge **À valider** |
| `SW0-ARM-001` | construire le runtime Qt/LIO pour `linux/arm64` | image construite et architecture enregistrée | Partiel — noyau ARM64 construit et exécuté ; LIO complet bloqué sous QEMU, image finale **À valider** |
| `SW0-PX4-001` | rejouer le carré avec le port C++ | mission terminée, posé, artefacts T0 présents | Conforme en SITL SW0 |
| `SW0-PX4-002` | rejouer la perte Offboard avec le port C++ | failsafe PX4 observé, posé, artefacts T0 présents | Conforme en SITL SW0 |
| `SW0-LIO-001` | répéter FAST-LIO2 et LIO-SAM après migration | au moins trois répétitions comparables par candidat, seuils **À valider** | Conforme — trois passages complets par candidat à 1×, métriques corrigées et aucun scan manquant ; seuils de qualification **À valider** |
| `SW0-DOC-001` | aligner les guides actifs et l'index | aucune commande active ne cible le dashboard Web supprimé | Conforme pour les guides actifs ; revue historique conservée |

## 5. Résultats d'exécution SW0

### 5.1 Construction et tests

Ce premier relevé précède les corrections numériques de clôture. Les empreintes
finales qui le remplacent pour la baseline active sont enregistrées en §5.8.

| Preuve | Résultat des 2–5 septembre 2026 |
|---|---|
| Preset `ci-windows` | configuration et construction réussies sous MSYS2 UCRT64 |
| CTest `ci-windows` | 12/12 réussis en 2,94 s le 2 septembre ; recontrôles conformes, dont 12/12 en 5,05 s après redémarrage le 5 septembre |
| Docker `linux/amd64` courant | cibles FAST-LIO2, Point-LIO, LIO-SAM et Qt/ROS 2 construites séquentiellement avec les correctifs courants |
| Empreinte FAST-LIO2 | `sha256:56e0c5b62d00a4a9c8f335293ba43d9c94766bb944d9108bcd2247ce2bca1489` |
| Empreinte Point-LIO | `sha256:e1f846d6bd03239ad332c941066c33226c1f0c7c13ed04c55c44a79f048e8b85` |
| Empreinte LIO-SAM | `sha256:58b681bb1293dc9d842a78b87c7896af61a81ba824f13173e92178d3c168181c` |
| Empreinte Qt/ROS 2 | `sha256:dad4835b6a68cca9769eef9dcb9edeabacebbc5cf480da8490130ed73a918903` |
| Tags Compose | les tags `1.0.0` FAST-LIO2, Point-LIO, LIO-SAM et Qt pointent vers ces quatre empreintes courantes |
| Smokes des images | exécutables ROS 2 des trois moteurs détectés ; CLI projet exécutée ; application Qt terminée avec succès hors écran |
| Limite du smoke Qt en conteneur | création du contexte OpenGL impossible sans serveur graphique/GPU ; rendu réel **À valider** séparément |
| Résolution Compose | `docker compose config --quiet` réussi avant incident ; service résolu et relancé après récupération |
| Santé du pont de télémétrie | service recréé avec l'image courante ; `status=ok`, schéma `drone_agricole.telemetry_snapshot.v1`, domaine ROS 42 sur `127.0.0.1:8092` |
| Workflow de CI | versionné ; première exécution distante **À valider**, aucun dépôt distant n'étant configuré |
| Noyau C++/ROS 2 `linux/arm64` | image construite, inspectée `linux/arm64` et binaire `drone-agricole-tools help` exécuté avec succès |
| Empreinte du noyau `linux/arm64` | `sha256:1901e9e1095eae4290e596b1f63a7af9b9769366763f8d42c4a32e54dbfc769a` |
| Runtime Qt/LIO `linux/arm64` | non produit ; reprise **À valider** après rétablissement de Docker ou sur hôte arm64 natif |

### 5.2 Rejeux PX4 SITL avec le client C++

| Scénario | Résultat | Mesures observées | Archive locale non versionnée |
|---|---|---|---|
| Carré | `square_completed`, posé, aucun failsafe | altitude maximale 2,018 m ; erreurs maximales par segment comprises entre 0,299 m et 0,344 m | `results/simulation/px4_lot_a/sw0_cpp_square_20260902_1` |
| Perte Offboard | `offboard_loss_land_observed`, posé, failsafe PX4 observé | perte des consignes à 18,850 s ; action PX4 à 19,900 s ; latence observée 1,050 s ; altitude maximale 2,004 m | `results/simulation/px4_lot_a/sw0_cpp_failsafe_20260902_1` |

Chaque archive contient le `run_request.json`, les quatre autres contrats T0
natifs et le `result.json` du runner. Le manifeste natif reprend désormais le
`request_id` et les paramètres exacts de la requête, dont le délai d'étape. Ce
point est couvert par un test de régression C++.

Ces résultats prouvent le comportement du banc SITL local. Ils ne qualifient ni
le matériel, ni un vol réel, ni une valeur limite de latence ; ces éléments
restent **À valider** par des protocoles dédiés.

### 5.3 Diagnostic `linux/arm64`

La première construction complète a franchi la compilation du noyau C++/ROS 2
arm64, puis LIO-SAM a échoué pendant la configuration : après
`find_package(ament_cmake)`, `rosidl_default_generators` ne retrouvait plus la
bibliothèque ROS 2 `rcutils`, pourtant présente dans l'image.

Un cas minimal dans l'étape de dépendances a reproduit exactement ce défaut.
La déclaration directe `find_package(rcutils REQUIRED)` avant `rosidl` le
corrige. Le patch LIO-SAM versionné ajoute cette déclaration et la dépendance
`rcutils` au manifeste. La reconstruction corrigée a franchi la configuration,
mais sa compilation prolongée sous QEMU a saturé Docker ; le moteur a ensuite
répondu `500 Internal Server Error` et nécessite un redémarrage explicite.

Après récupération de Docker, le noyau C++/ROS 2 a été reconstruit seul en 197 s,
chargé comme image `linux/arm64`, inspecté et exécuté avec succès. LIO-SAM a
ensuite été lancé seul avec `CMAKE_BUILD_PARALLEL_LEVEL=1`. Le patch s'applique,
la configuration franchit l'ancien défaut `rcutils`, mais la compilation porte
WSL à environ 7,2 Go puis coupe de nouveau le moteur Docker par `EOF`.

La CI manuelle limite désormais BuildKit à une étape parallèle, le parallélisme
CMake des trois moteurs LIO à un travail pour ARM64, et la durée à 120 minutes.
Cette précaution ne suffit pas sur le poste actuel. La suite retenue est donc de
construire LIO-SAM, FAST-LIO2, Point-LIO puis l'image Qt sur un hôte arm64 natif
ou un Jetson. L'émulation QEMU ne qualifie de toute manière pas JetPack.

Le 3 septembre, le premier socket orphelin a été supprimé après arrêt administrateur
de `WSLService`, ce qui a rétabli Docker. Le second essai LIO sous QEMU a recréé le
même incident. Après redémarrage du poste, la suppression directe restait refusée.
Les deux répertoires parents ont donc été renommés, puis Docker AI a été désactivé
dans la configuration sauvegardée. Après un dernier renommage du répertoire `run`,
Docker a recréé ses sockets et retrouvé un état sain. Les constructions `amd64`,
les smokes LIO/Qt et le pont de télémétrie ont ensuite tous réussi. Aucun reset
usine, volume, image ou dataset n'a été supprimé.

### 5.4 Rejeux LIO courts post-migration

Le 5 septembre 2026, trois rejeux FAST-LIO2 et trois rejeux LIO-SAM ont été
exécutés à `1×` dans les images `linux/amd64` courantes sur des extraits de cinq
secondes. Les dossiers sont locaux, sous `results/benchmarks/`, et restent exclus
du versionnement.

| Algorithme | Répétition | Scans reçus / synchronisés / odométrie | Poses | ATE translation RMSE | RPE translation RMSE | CPU moyen | RSS crête |
|---|---:|---:|---:|---:|---:|---:|---:|
| FAST-LIO2 | 1 | 49 / 49 / 45 | 45 | 0,01020 m | 0,01389 m | 0,251 cœur | 155,4 Mio |
| FAST-LIO2 | 2 | 49 / 49 / 46 | 46 | 0,00887 m | 0,01266 m | 0,254 cœur | 155,0 Mio |
| FAST-LIO2 | 3 | 49 / 49 / 46 | 46 | 0,00887 m | 0,01266 m | 0,241 cœur | 155,2 Mio |
| LIO-SAM | 1 | 50 / 46 / 46 | 46 | 0,00465 m | 0,00542 m | 0,559 cœur | 205,8 Mio |
| LIO-SAM | 2 | 50 / 46 / 46 | 46 | 0,00465 m | 0,00542 m | 0,580 cœur | 200,9 Mio |
| LIO-SAM | 3 | 45 / 42 / 42 | 42 | 0,00447 m | 0,00585 m | 0,226 cœur | 197,1 Mio |

Les métriques d'orientation ne sont pas retenues comme preuve de répétabilité sur
ce smoke quasi statique : FAST-LIO2 varie notamment de 168,23° à 88,15° et
LIO-SAM de 145,16° à 160,44°. Les deux moteurs terminent néanmoins les trois
rejeux et produisent des résultats analysables. Une séquence plus longue,
représentative du mouvement, ainsi que les seuils d'acceptation restent
**À valider**.

### 5.5 Reprise et correction du calcul ATE le 5 septembre

Les trois rejeux FAST-LIO2 complets `sw0_full_repeat_01_20260905` à
`sw0_full_repeat_03_20260905` sont terminés : chacun reçoit et synchronise
5 762 scans et publie 5 758 odométries. Les métriques initiales indiquaient une
ATE translation de 1,59382 / 1,61025 / 1,57076 m. Ces ATE sont invalidées par le
défaut d'alignement décrit ci-dessous ; les trajectoires enregistrées sont intactes.

L'audit a identifié une itération de puissance non décalée dans
`TrajectoryAnalysis::alignPositions`. Sur une trajectoire plane, les valeurs
propres extrêmes de la matrice de Horn peuvent avoir le même module et des
signes opposés : les 80 itérations ne garantissent pas le bon quaternion. Le
nouveau test `alignsPlanarPositions` reproduit l'échec sur une transformation
rigide connue. La diagonalisation symétrique de Jacobi remplace cette itération
et choisit la plus grande valeur propre algébrique. Le test couvre des rotations
de 2°, 90° et 180° ; les 12 suites CTest Windows passent après correction en
3,29 s. Le recalcul des trois archives ROS 2 avec le commit `ad4b102` donne une
ATE translation de 0,36442 / 0,37651 / 0,32524 m. Il explique l'écart apparent
avec la référence historique de 0,3592 m. La RPE, indépendante de cet
alignement global, reste inchangée. Les anciens calculs sont conservés dans
`metrics_before_alignment_fix.json` ; `metrics_corrected.json` et le fichier
canonique `metrics.json` portent les résultats recalculés. Le rapport C++ est
`results/benchmarks/sw0_fastlio2_comparison_20260905.json`.

Le même outil corrigé a réanalysé l'enregistrement historique `2a31bc7f` sans
modifier cette archive : ATE translation 0,3591550052 m, contre 0,3591553586 m
dans la référence, soit un écart absolu de 0,0000003535 m. Cette régression sur
des données réelles confirme la cohérence du port C++. Le résultat indépendant
est `results/benchmarks/sw0_historical_alignment_check_20260905.json`.

Le contrôle Linux sous Qt 6.2.4 a ensuite révélé un défaut de précision dans
`rotationErrorDegrees` : `acos` appliqué au produit scalaire en simple précision
pouvait produire un angle non nul entre deux rotations numériquement identiques.
Le calcul utilise désormais `atan2` sur les composantes du quaternion relatif,
calculées en double précision. `resolvesSmallQuaternionAngles` vérifie l'identité,
l'équivalence des signes et un angle de 0,001°. Les métriques d'orientation des
six passages sont actualisées avec ce calcul final ; leurs trajectoires et
leurs mesures de ressources restent inchangées.

L'hypothèse initiale d'une différence de calibration entre la référence et les
essais SW0 n'est pas établie : la comparaison YAML montre principalement une
différence de présentation et de publication du nuage. Aucune calibration n'a
été modifiée pour améliorer les scores.

Au redémarrage, les sockets `sailor-ingest.sock` puis `engine.sock` ont reproduit
le défaut Windows déjà documenté. Les dossiers concernés ont été sauvegardés
par renommage réversible avec les suffixes `recovery-sw0-20260905-1035` et
`recovery-sw0-20260905-1037`, puis `run.recovery-sw0-20260905-final` pour le
socket recréé par une tentative intermédiaire. Le moteur Docker 29.7.2 a été
rétabli et les constructions ainsi que les essais ont repris.

### 5.6 Campagne complète FAST-LIO2 à 1×

Entrée commune : BotanicGarden `1006-03`, 581,120665 s, 243 739 messages,
5 762 scans. Les trois configurations portent l'empreinte
`4ddd7329c4e923bff33ff4e45ad4c406d317439b07a6b90bb1bd3db557475b10`.
Chaque archive contient le manifeste, la configuration, le profil de ressources,
la vidange du pipeline et le rosbag d'estimation. Les chiffres ci-dessous
proviennent du recalcul corrigé, avec association à 0,06 s et RPE à 1 s.

| Répétition | ATE m / ° | RPE m / ° | CPU moyen (cœur) | RSS crête (Mio) | Vitesse effective |
|---|---|---|---:|---:|---:|
| 1 | 0,36442 / 1,65781 | 0,049136 / 0,590860 | 0,37374 | 309,45 | 0,99924× |
| 2 | 0,37651 / 1,67828 | 0,049095 / 0,590993 | 0,37855 | 308,78 | 0,99804× |
| 3 | 0,32524 / 1,67197 | 0,048425 / 0,588135 | 0,37663 | 296,33 | 0,99817× |

Les trois vidanges terminent avec `status=complete`, zéro scan manquant,
5 762 scans synchronisés et 5 758 poses associées. Les sorties manquantes sont
comptabilisées par les étapes d'initialisation et d'undistortion. La plage
d'ATE translation observée est de 0,32524 à 0,37651 m ; les seuils formels de
répétabilité et leur généralisation à d'autres scènes restent **À valider**.

### 5.7 Campagne complète LIO-SAM à 1×

Les trois répétitions utilisent le même bag complet que FAST-LIO2, le profil
`configs/lio/lio_sam/botanicgarden_velodyne_xsens.yaml` et le domaine ROS 143.
Les archives sont sous `results/benchmarks/lio_sam/botanicgarden_1006-03/`,
avec les noms `sw0_full_repeat_01_20260905` à `sw0_full_repeat_03_20260905`.
L'empreinte de configuration, identique sur les trois passages, est
`d667a5f4f068aaf9f64f9923d3d1d789746f42529f83ec5199944dd8f5bf3eb4`.
L'image intègre directement le correctif d'alignement `ad4b102`.

| Répétition | ATE m / ° | RPE m / ° | CPU moyen (cœur) | RSS crête (Mio) | Vitesse effective |
|---|---|---|---:|---:|---:|
| 1 | 0,39505 / 1,15519 | 0,041696 / 0,570634 | 1,56692 | 590,48 | 0,99912× |
| 2 | 0,36649 / 1,06590 | 0,041541 / 0,571346 | 1,50901 | 582,50 | 0,99814× |
| 3 | 0,36768 / 1,03849 | 0,041687 / 0,570580 | 1,54032 | 583,10 | 0,99811× |

Les trois passages terminent avec `status=complete`, 5 762 scans reçus et
5 758 scans synchronisés/odométries ; les quatre scans restants sont déclarés
par `scans_input_buffered`. Aucun scan reçu ne manque au transport. Les six
archives FAST-LIO2/LIO-SAM possèdent leurs manifestes, configurations, profils,
métriques et vidanges complètes. Le rapport de comparaison C++ est
`results/benchmarks/sw0_full_comparison_20260905.json`.

Les ATE translation LIO-SAM s'étendent de 0,36649 à 0,39505 m, leurs RPE de
0,041541 à 0,041696 m. FAST-LIO2 conserve un coût de calcul inférieur ; LIO-SAM
présente ici une meilleure orientation et une meilleure RPE. Ces observations
permettent la fermeture de la répétition post-migration ; les critères de
qualification de navigation restent **À valider**. Elles ne figent pas un choix
de moteur pour toutes les scènes.

La campagne LIO-SAM a utilisé l'image corrigée
`sha256:0aaa46344d24568e3b72840d675fa04a3ec863005bf6599b0724e1c6f225be2e`
(manifeste OCI). Les essais FAST-LIO2 ont utilisé l'image antérieure indiquée en
§5.1 puis le noyau ROS 2 corrigé pour l'analyse. Les reconstructions finales
bornent également le parallélisme CMake du noyau et de Qt à deux travaux ;
elles ne changent ni les sources ni les paramètres des moteurs LIO.

### 5.8 Images et contrôles finaux

Les tags `1.0.0` et `sw0-amd64-current` désignent les images finales suivantes,
toutes inspectées `linux/amd64`, après les commits `ad4b102`, `32b90ef` et
`0f3b25b`. Les cibles ont été construites séquentiellement avec
`CMAKE_BUILD_PARALLEL_LEVEL=2`.

| Image | Empreinte Docker inspectée |
|---|---|
| `ros-humble` | `sha256:f1283201ccfd7bbd0e5d976309c42734de3bab35e5b2b823cbcd51cdc9e8a97f` |
| `fast-lio2` | `sha256:17a50d74b87a25e5cd968b83809c49b4097f4ba911c4df2ee6a7ed6879218404` |
| `point-lio` | `sha256:749c622cd0b8c3b95ead1afa41361b99ea1859d21d12e6dea948f064cee395f5` |
| `lio-sam` | `sha256:d69010a45381d09f38991190e7a4880a9701797c077f7847b4f96098495ab2c1` |
| `qt-dashboard` | `sha256:1179a9b0637c09ef46b0a5e2f4cd9dea6e393175963dbe891ced557065fcf908` |

Les six bilans ont été recalculés avec le noyau final et sauvegarde préalable
`metrics_before_angle_fix.json`. Le rapport comparatif final est régénéré.
La configuration Compose est valide ; le pont recréé avec l'image finale répond
`status=ok`, schéma `drone_agricole.telemetry_snapshot.v1`, domaine 42 sur
`127.0.0.1:8092`. Le smoke Qt final termine avec le code 0 ; le contexte OpenGL
reste indisponible hors écran, donc le rendu graphique conteneurisé reste
**À valider**. Les suites Windows et Linux réussissent respectivement en 2,46 s
et 35,54 s (12/12 chacune).

Lors de la dernière reprise du 5 septembre, Docker était arrêté. Les deux
dossiers de sockets ont été conservés simultanément avec le suffixe
`recovery-sw0-close`, puis le moteur et la télémétrie ont redémarré. Cette
récurrence maintient l'action `SW0-FOLLOW-DOCKER` ouverte.

## 6. Automatisation mise en place

Le workflow `.github/workflows/sw0-ci.yml` :

1. vérifier les écarts de format Git ;
2. construire et tester C++17 / Qt 6 sous Linux `amd64` ;
3. construire et tester C++17 / Qt 6 sous Windows UCRT64 ;
4. valider la résolution de `compose.yaml` ;
5. proposer manuellement une construction Docker `linux/arm64` du runtime Qt/LIO,
   avec une seule étape BuildKit et un seul travail CMake par moteur LIO.

Le job ARM64 est volontairement manuel tant que sa durée, sa consommation et
la compatibilité des dépendances amont ne sont pas mesurées. Cette mesure ne
constitue pas encore une qualification Jetson ou JetPack.

## 7. Porte de sortie SW0

SW0 est fermé au niveau baseline de développement locale, selon ADR-0011.

| Critère | Preuve de sortie |
|---|---|
| Migration récupérable | commits séparés sur `codex/sw0-consolidation`, tag `sw0-v0.1` |
| Windows | 12/12 suites CTest après les deux corrections numériques, 2,46 s |
| Linux amd64 | 12/12 suites CTest, Qt 6.2.4/Ubuntu 22.04, 35,54 s ; cinq images reconstruites |
| ARM64 | noyau construit/exécuté ; blocage QEMU caractérisé et qualification native retenue par ADR-0011 |
| PX4 C++ | carré et perte Offboard réussis en SITL, artefacts rechargeables (§5.2) |
| LIO C++ | trois passages complets à 1× par moteur, 5 762 scans reçus chacun, métriques finales (§5.6–5.7) |
| Documentation | guides actifs, contexte, index, décision et réserves actualisés |

Le contrôle Linux utilise les options du preset CI avec les commandes CMake
explicites, la version CMake du conteneur Ubuntu 22.04 étant antérieure au format
de presets employé par la CI distante. Les tests locaux Windows et Linux
désactivent ROS 2 ; les campagnes en images ROS 2 complètent cette couverture.
L'exécution du workflow sur une forge reste **À valider**.

## 8. Traçabilité SW0

| Exigence | Composant / algorithme | Test | Résultat |
|---|---|---|---|
| `ARCH-CPP17-001` | CMake, `software/cpp`, paquet PX4 C++ | configuration, compilation, audit d'extensions | Conforme localement |
| `UI-QT6-001` | `drone-agricole-dashboard`, `main_window.ui` | `test_dashboard_smoke` | Conforme sous Windows Debug |
| `QUAL-REQ-001` | CMakePresets, CI, Docker | builds Windows/Linux/ARM64 | Windows et images Linux `amd64` courantes conformes localement ; noyau arm64 construit et exécuté ; image Qt/LIO arm64 complète, CI distante et JetPack **À valider** |
| `OBS-TELEM-001` | `TelemetryBridge`, service Compose | `/api/health` | Conforme localement |
| `SAFE-REQ-001` | PX4, pont ROS 2, runner Offboard | revue des interfaces et scénarios SITL | séparation conforme ; deux rejeux SW0 conformes en SITL |
| `T0-TRACE-001` | `ContractRegistry`, `ResultAdapter`, `ProjectTools` | validation RunRequest et liaison requête–manifeste | Conforme, tests C++ réussis |
| `PERF-009` | runners, manifestes et résultats | trois rejeux complets par moteur à 1× | Conforme pour la campagne post-migration : six résultats comparables, aucun scan manquant ; seuils formels et qualification multi-scènes **À valider** |
| `SW0-METRIC-001` | `TrajectoryAnalysis::alignPositions` | régression plane 2°/90°/180°, réanalyse de l'archive historique | défaut reproduit avant correction ; tests réussis après correction ; écart ATE historique inférieur à 0,000001 m |

### 8.1 Réserves de qualification après clôture

L'ADR-0011 autorise l'entrée de B1 sur la baseline locale, sous les conditions
suivantes. Elles restent **À valider** jusqu'à production de leurs preuves.

| ID | Action | Échéance bloquante | Preuve attendue |
|---|---|---|---|
| `SW0-FOLLOW-ARM` | construire Qt et les trois LIO sur ARM64 natif | avant baseline embarquée candidate | images inspectées ARM64, exécutables et smokes réussis |
| `SW0-FOLLOW-JETSON` | qualifier JetPack, vitesse 1× et thermique | avant sélection matérielle définitive | campagne native CPU/RAM/température/stabilité, seuils **À valider** |
| `SW0-FOLLOW-CI` | raccorder une forge et exécuter le workflow | avant livraison collaborative | URL de pipeline et résultats Windows/Linux |
| `SW0-FOLLOW-GL` | contrôler le rendu Qt conteneurisé avec GPU | avant qualification de ce mode d'affichage | contrôle visuel de la carte 3D et absence d'échec de contexte |
| `SW0-FOLLOW-PERF` | définir les seuils et étendre les scènes LIO | avant qualification de navigation | protocole, seuils approuvés et répétitions multi-scènes |
| `SW0-FOLLOW-DOCKER` | vérifier la stabilité des prochains démarrages | avant campagne autonome prolongée sur ce poste | redémarrages sains et absence de sockets orphelins |

La fermeture de SW0 ne supprime pas ces actions. Les preuves SITL et de rejeu
ne qualifient ni le vol réel, ni la pulvérisation.

## 9. Entrée dans B1

B1 peut démarrer sur la baseline locale `sw0-v0.1`. Le premier périmètre
reste `survey-reception` puis `survey-compilation`, avec conservation des données
brutes, validation des timestamps et calibrations, checksums et rapport explicite
`PASS/WARN/FAIL`.

## 10. Enchaînement logiciel et matériel

| Volet | Prochaine phase | Entrées nécessaires | Sortie attendue |
|---|---|---|---|
| Logiciel | B1 — contrats et réception cartographe | porte SW0, contrats T0, dataset BotanicGarden | `SurveyMissionPackage` et `SurveyRunPackage` versionnés, import reproductible et rapport qualité |
| Logiciel embarqué | qualification de la cible compagnon | image `linux/arm64`, profil de mesure et matériel Jetson | build JetPack, tests à 1×, CPU/RAM/température et stabilité ; seuils **À valider** |
| Matériel | définition d'une baseline candidate | interfaces SW/HW, architecture de sûreté et enveloppes de mission | nomenclature candidate, budgets masse/puissance/thermique et matrice d'interfaces, tous **À valider** |
| Intégration | premier banc sec | baseline matérielle candidate et profils PX4 distincts du SITL | alimentation protégée, communications, horloges, arrêt sûr et journalisation démontrés sans liquide |

Le matériel est actuellement moins mature que le logiciel : le dossier ne
contient pas encore de nomenclature, schéma, budget ou protocole de banc. Les
achats structurants ne doivent donc pas être figés à partir des seuls résultats
SITL. La progression conserve l'ordre simulation, banc sec, eau/traceur, puis
seulement produits autorisés avec protocole validé.
