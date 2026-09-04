# Étude LaMole/Grospoli et chaîne rangs–carte–trajectoires

| Champ | Valeur |
|---|---|
| Référence | DOC-30 |
| Version | V0.1 |
| Date | 3 septembre 2026 |
| Statut | Étude candidate — accès aux données et paramètres **À valider** |
| Références projet | DOC-00, DOC-01, DOC-19, DOC-28, ADR-0001, ADR-0004, ADR-0007, ADR-0010 |

## 1. Conclusion

L'intuition de remplacer BotanicGarden pour le développement de la carte métier est correcte, mais le remplacement ne doit pas être global :

- BotanicGarden reste utile pour rejouer des flux LiDAR–IMU, mesurer les LIO et valider la chaîne ROS 1 vers ROS 2 ;
- LaMole/Grospoli est beaucoup plus représentatif des terrasses, des fortes pentes, des murs et des rangs irréguliers visés par le projet ;
- les produits LaMole/Grospoli publiés sont des cartes déjà reconstruites, et non un rosbag LiDAR–IMU avec trajectoire de référence ; ils servent donc à B3/B4 — carte métier et mission — mais pas au classement LIO de B2 ;
- le paquet exact employé par les publications n'est pas disponible par téléchargement public direct. Les auteurs indiquent un accès sur demande, soumis à l'autorisation des organismes fournisseurs ;
- un développement mesurable ne doit pas attendre cet accord. EscaYard fournit publiquement orthomosaïques, nuages 3D et positions RTK de ceps ; VineLiDAR fournit dix nuages UAV-LiDAR RGB multi-date. Ils constituent respectivement la baseline quantitative et la baseline géométrique immédiates.

La stratégie proposée est donc un portefeuille par fonction, et non un dataset unique.

## 2. Ce que contient réellement LaMole/Grospoli

« LaMole/Grospoli » désigne plusieurs campagnes et plusieurs échelles de données.

| Produit | Emprise et date | Contenu annoncé | Utilité projet | Limite principale |
|---|---|---|---|---|
| Lamole, échelle territoriale | vallée, 341 ha, 6 août 2020 | nuage LiDAR aéroporté classifié, DTM, DSM, orthophoto RGB | terrain, terrasses, murs, contexte global | résolution LiDAR annoncée de 50 cm, insuffisante seule pour des rangs précis |
| Grospoli I | environ 1,8 ha, 7 septembre 2017 | nuage photogrammétrique non classifié et orthophoto à environ 2 cm | rangs courbes, géométrie fine, murs et terrassements | accès public direct et licence non établis |
| Grospoli II | environ 1,1 ha, 5 septembre 2020 | cinq acquisitions RGB et TIR par DJI Mavic 2 Enterprise Dual ; nuages photogrammétriques | variation temporelle dans la journée, rangs et végétation | données traitées, pas de LiDAR–IMU brut ni de vérité terrain de trajectoire |
| Castello | environ 2,15 ha en parties terrassée et non terrassée | acquisitions UAV RGB/TIR et contexte LiDAR | transition entre morphologies | contenu exact du paquet **À valider** |
| Tracés manuels de recherche | douze vignobles de la vallée | murs et rangs tracés manuellement dans QGIS pour les analyses publiées | vérité terrain potentielle pour la topologie | disponibilité comme fichiers vectoriels **À valider** |

Les publications ne décrivent ni rosbag, ni paquets LiDAR bruts horodatés par point, ni IMU, ni calibration LiDAR–IMU, ni trajectoire 6 DoF utilisable pour ATE/RPE. Convertir ces produits statiques en topics ROS artificiels ferait perdre leur sémantique sans créer les informations manquantes.

Sources principales :

- [LamoLab — campagnes des vignobles en terrasses](https://lamolab.net/lamole-research/) ;
- [Tyc et al., intégration des données dans un modèle voxel composite](https://doi.org/10.3390/rs13173483) ;
- [Tyc et al., processus paramétrique appliqué à Grospoli I](https://gispoint.de/fileadmin/user_upload/paper_gis_open/DLA_2022/537724049.pdf) ;
- [Tucci et al., campagne UAV multisenseur sur Grospoli](https://doi.org/10.3390/ijgi8020087).

## 3. Accès et téléchargement

### 3.1 Paquet scientifique exact

Le `Data Availability Statement` de l'article de 2021 indique que des restrictions s'appliquent et que les données sont accessibles auprès des auteurs avec la permission des organismes concernés. Il n'existe donc pas, à la date de cette étude, de commande de téléchargement public et reproductible pour le paquet exact.

La voie réaliste est une demande conjointe aux auteurs et au GeCo Lab de l'Université de Florence. Le premier contact institutionnel vérifié est la page d'[Erica Isabella Parisi, DICEA/GeCo](https://cercachi.unifi.it/p-doc2-0-0-A-3f2b3a323b292f.html). La demande doit citer le DOI `10.3390/rs13173483` et demander explicitement :

1. le nuage et l'orthophoto Grospoli I 2017 ;
2. les produits RGB/TIR Grospoli II 2020 ;
3. le DTM, le DSM et, si autorisé, le nuage classifié Lamole 2020 ;
4. les polygones de parcelle et tracés manuels de rangs/murs s'ils peuvent être partagés ;
5. le CRS horizontal, le datum vertical, les GCP/RTK et les transformations entre campagnes ;
6. la liste des fichiers, leurs tailles et leurs empreintes ;
7. les conditions d'usage, de publication des métriques, de modification, d'usage commercial futur et de redistribution des dérivés.

La réponse écrite et la licence devront être archivées hors Git si elles contiennent des informations personnelles ou confidentielles. Seul un résumé de provenance et des droits sera versionné.

### 3.2 Données ouvertes de la Région Toscane

La Région Toscane publie via Cartoteca/GEOscopio des DTM, DSM et certains relevés LiDAR RAW à pas de 1 ou 2 m sous licences Creative Commons. Cette voie permet de récupérer un contexte terrain autour de Lamole :

- [catalogue régional des relevés LiDAR](https://dati.toscana.it/dataset/lidar?action=read) ;
- [page Open Geodata et accès Cartoteca](https://geoblog.regione.toscana.it/-/open-geodata).

Ces données ne doivent pas être présentées comme le paquet Lamole 2020 de la publication. La couverture exacte de Grospoli, la date, la composante RAW et la licence de chaque tuile restent **À valider**. Leur résolution est utile pour le relief et le géoréférencement, mais pas suffisante pour produire seule une trajectoire inter-rang sûre.

### 3.3 Démarrage public immédiat

Deux jeux ouverts permettent de développer l'importateur et de mesurer l'algorithme avant l'accord LaMole :

| Dataset | Téléchargement | Licence | Premier sous-ensemble recommandé |
|---|---|---|---|
| EscaYard | [Zenodo 10362567](https://zenodo.org/records/10362567) | CC BY 4.0 | `trunk_locations_VineyardB7.zip`, un nuage LAS B7 et une fenêtre de l'orthomosaïque B7 |
| VineLiDAR | [Zenodo 8113105](https://zenodo.org/records/8113105) | CC BY 4.0 | un nuage B7 à 30 m ; pour un aperçu léger, miroir FiftyOne/Hugging Face voxelisé |

EscaYard apporte deux orthomosaïques multispectrales, dix nuages SfM et des positions RTK de ceps. VineLiDAR apporte dix nuages LAZ RGB issus d'un DJI M300/Zenmuse L1, sur deux parcelles et plusieurs dates. Les deux jeux fournissent des produits cartographiques statiques, pas des flux LIO bruts.

Sources :

- [EscaYard — description, fichiers et RTK](https://pmc.ncbi.nlm.nih.gov/articles/PMC11106823/) ;
- [VineLiDAR — description scientifique](https://pmc.ncbi.nlm.nih.gov/articles/PMC10616138/) ;
- [VineLiDAR — fiche de téléchargement et licence](https://huggingface.co/datasets/Voxel51/VineLiDAR).

### 3.4 Règles de stockage

Les données restent hors versionnement :

```text
datasets/public/
├── lamole_grospoli/
│   └── <release_autorisee>/raw/
├── escayard/
│   └── zenodo_10362567/raw/
└── vinelidar/
    └── zenodo_8113105/raw/
```

Avant toute préparation, le manifeste doit enregistrer l'URL ou l'identifiant de remise, la date, la licence, la taille et SHA-256 de chaque fichier. Une archive reçue ne doit jamais être modifiée ; les tuiles, extraits et annotations dérivés sont placés dans `datasets/derived/`.

## 4. Architecture des adaptateurs

### 4.1 Séparer les deux familles d'entrée

L'adaptateur actuel est spécialisé BotanicGarden et convertit des messages ROS 1 vers ROS 2. La nouvelle chaîne doit conserver deux ports indépendants :

```text
RosBagSurveyImporter
  -> flux LiDAR / IMU / GNSS / caméra horodatés
  -> benchmark LIO et SurveyRunPackage brut

GeospatialSurveyImporter
  -> LAS/LAZ/COPC + GeoTIFF + GeoPackage/Shapefile
  -> SurveyRunPackage de type external_geospatial_products
```

La seconde famille ne synthétise pas d'IMU, de trajectoire ou de timestamp absent. Les champs manquants sont déclarés `not_available` et les algorithmes incompatibles échouent explicitement.

### 4.2 Noyau générique et profils minces

Le noyau C++17 proposé s'appuie sur GDAL/PROJ pour les rasters et repères, et PDAL pour LAS/LAZ/COPC. Ces dépendances doivent être figées dans une image Docker reproductible `amd64` et `arm64`.

Responsabilités du noyau :

- inventaire, taille et SHA-256 ;
- lecture des en-têtes sans charger un nuage complet en mémoire ;
- contrôle du CRS horizontal et du datum vertical ;
- transformation vers un repère local métrique tout en conservant `earth -> map` ;
- contrôle des emprises et recouvrements entre nuage, orthophoto, DTM, DSM et labels ;
- tuilage, index spatial et génération d'extraits de test ;
- rapport `PASS/WARN/FAIL` sans correction silencieuse ;
- provenance de chaque produit dérivé.

Les profils `LamoleGrospoli`, `EscaYard` et `VineLiDAR` ne contiennent que les règles de nommage, les rôles de fichiers, les CRS attendus lorsqu'ils sont publiés et les contrôles propres au jeu. Le traitement de la géométrie reste commun.

### 4.3 Formats canoniques proposés

| Information | Format de travail | Justification |
|---|---|---|
| Nuage maître | COPC/LAZ tuilé | accès partiel, coordonnées et attributs conservés |
| DTM, DSM, CHM, confiance | Cloud Optimized GeoTIFF | pyramides, fenêtres et géoréférencement |
| Rangs, corridors, murs, obstacles | GeoPackage | géométries vectorielles, attributs et transactions |
| Graphe de mission embarqué | paquet binaire versionné **À valider** | lecture bornée sur le compagnon |
| Manifestes et preuves | JSON/YAML + SHA-256 | inspection humaine et traçabilité |

Le format embarqué ne doit pas contenir le nuage complet. Il porte des tuiles utiles à la relocalisation, les corridors, l'ESDF ou l'occupation dérivée, la topologie et les incertitudes.

## 5. Évaluation de l'effort des adaptateurs

Les chiffres ci-dessous sont des estimations de développement pour une personne connaissant C++/CMake, sans temps d'attente des ayants droit. Ils restent **À valider** après réception d'un inventaire de fichiers.

| Lot | Contenu | Charge candidate **À valider** |
|---|---|---:|
| Contrats B1 | `SurveyMissionPackage`, `SurveyRunPackage`, provenance et états d'absence | 3 à 5 j.h |
| Socle géospatial | GDAL/PROJ/PDAL, images Docker, `amd64` et compilation `arm64` | 2 à 4 j.h |
| Import générique | inventaire, CRS, tuilage, index, contrôles d'emprise et rapport qualité | 5 à 8 j.h |
| Profil LaMole/Grospoli | nommage, bandes, multi-date, contrôles et manifeste | 2 à 4 j.h |
| Tests | mini-tuiles synthétiques, fichiers corrompus, CRS incompatibles, golden reports | 3 à 5 j.h |
| Total import exploitable | hors reconstruction photogrammétrique | 15 à 26 j.h |

Si seuls les clichés bruts sont fournis, l'intégration d'une reconstruction reproductible avec un outil tiers tel qu'OpenDroneMap ajoute environ 5 à 10 j.h **À valider**, plus le temps de calcul. Le moteur tiers peut utiliser ses propres langages ; l'orchestration, les validations et la logique métier du projet restent en C++17.

Le risque dominant n'est pas le code LAS/GeoTIFF : ce sont les droits d'accès, le datum vertical et l'absence éventuelle des tracés de rangs utilisés par les chercheurs.

## 6. Algorithme recommandé pour reconnaître les rangs

### 6.1 Pourquoi une baseline géométrique hybride

Une transformée de Hough globale est adaptée aux rangs droits, mais elle casse les rangs courbes, les changements d'orientation et les terrasses séparées. Un réseau neuronal entraîné immédiatement serait peu mesurable, faute d'annotations LaMole et avec un risque de surapprentissage à une saison.

La première baseline doit donc combiner hauteur, couleur et structure locale, puis tracer des courbes sur la surface. Elle est déterministe, explicable et fournit automatiquement des pré-annotations pour une IA future.

La littérature confirme deux points utiles :

- les méthodes historiques combinant segmentation et Hough sont efficaces sur des alignements plutôt droits, mais leurs hypothèses de parallélisme restent limitantes ;
- une méthode récente dédiée aux vignobles pentus et irréguliers combine indices visibles et différence DSM–DTM, puis reconstruit les lignes centrales courbes.

Références : [Comba et al., 2015](https://doi.org/10.1016/j.compag.2015.03.011) et [Pádua et al., 2024](https://doi.org/10.1016/j.compag.2024.109372).

### 6.2 Pipeline hors ligne

```text
validation des entrées et du géoréférencement
  -> DTM + ruptures de terrain + partition en terrasses
  -> hauteur normalisée au-dessus du sol
  -> probabilité de végétation et d'éléments structurants
  -> champ d'orientation locale et cohérence linéaire
  -> graines de rangs par terrasse
  -> suivi de crêtes par chemin de coût minimal
  -> splines 3D avec coupures explicites
  -> contrôle topologique et confiance
  -> revue/correction opérateur
```

#### Étape A — terrain et terrasses

1. Utiliser la classe sol du LiDAR si elle est fiable, sinon extraire le sol par filtrage morphologique/progressif.
2. Construire un DTM avec incertitude par cellule.
3. Détecter murs, talus et ruptures par pente, variation de normale et discontinuité d'altitude.
4. Segmenter la parcelle en surfaces de terrasse. Un rang ne peut franchir automatiquement une rupture non navigable.

#### Étape B — masque de vigne

Pour chaque cellule, calculer :

- hauteur au-dessus du DTM ;
- densité et distribution verticale des points ;
- indice visible normalisé ou NDVI si NIR disponible ;
- rugosité, verticalité et cohérence locale ;
- distance aux murs, arbres et zones inconnues.

La probabilité de vigne combine ces indices. Les poids et seuils restent **À valider** sur EscaYard puis LaMole. Une végétation inter-rang basse ne doit pas être confondue avec la canopée simplement parce qu'elle est verte.

#### Étape C — orientation et traçage courbe

Un tenseur de structure multi-échelle estime localement l'orientation et sa cohérence. Hough ou FFT peuvent fournir des orientations initiales à l'échelle d'une terrasse, mais pas la géométrie finale.

Chaque centre de rang est ensuite recherché comme une courbe `gamma` minimisant un coût composé de :

- faible probabilité de rang ;
- désaccord avec l'orientation locale ;
- courbure excessive ;
- franchissement d'une rupture, d'un obstacle ou d'une zone inconnue ;
- saut au-dessus d'une lacune trop longue.

La courbe discrète est ajustée par B-spline cubique robuste. Les lacunes conservées portent un état `observed_gap`, `occluded` ou `unknown` ; elles ne sont jamais comblées silencieusement.

#### Étape D — identité et topologie

Les rangs sont associés entre tuiles par position, tangente, altitude, espacement et continuité de terrasse. Chaque `VineRow` reçoit un identifiant stable, des segments observés, une enveloppe de canopée, un côté, une confiance et une date.

Une revue opérateur valide les fusions, séparations et extrémités. Les corrections sont enregistrées comme une couche distincte afin de comparer l'algorithme à la vérité terrain.

## 7. De la géométrie des rangs à la carte navigable

La carte doit distinguer clairement la plante et l'espace de vol :

| Entité | Rôle |
|---|---|
| `VineRow` | axe et enveloppe du mur végétal |
| `InterRowCorridor` | tube 3D libre entre deux rangs, borné en largeur et hauteur |
| `RowEnd` | entrée/sortie et sens possibles |
| `TransitionZone` | volume vérifié pour demi-tour, montée, rétraction ou réentrée |
| `TerraceSurface` | terrain continu et plage d'altitude |
| `Wall`, `Talus`, `WireZone`, `Obstacle` | volumes interdits ou conservateurs |
| `ConfidenceLayer` | couverture, incertitude géométrique et zones inconnues |

Pour chaque abscisse curviligne, le corridor est dérivé des enveloppes des deux rangs voisins et de l'espace libre observé. Sa marge dépend de l'enveloppe balayée du drone et du bras, de l'incertitude de carte, de localisation, du vent et de la dynamique. Les dimensions et coefficients restent **À valider** avec la plateforme physique.

Une zone est marquée non navigable si le calcul ne peut pas démontrer une largeur et une hauteur libres suffisantes. L'absence de point n'est pas une preuve d'espace libre.

## 8. Génération des trajectoires de traitement

### 8.1 Centre nominal du passage

Le centre nominal n'est pas la simple moyenne globale de deux lignes. Il est construit section par section sur la surface de la terrasse, à distance contrôlée des deux enveloppes. Un décalage latéral peut être appliqué si un seul côté est traité ; sa valeur dépend du bras, de la buse et du modèle de dépôt et reste **À valider** sur banc eau/traceur.

Le profil vertical est calculé avec le volume balayé complet : corps, bras rétracté/déployé et buses. Il doit simultanément :

- maintenir le corps au-dessus ou dans le volume autorisé selon le concept mécanique **À valider** ;
- positionner les étages de traitement face aux cibles ;
- éviter sol, canopée, poteaux, fils, murs et ruptures ;
- respecter vitesse, accélération, jerk et vitesse verticale **À valider**.

### 8.2 Graphe et ordre des rangs

Les segments traitables sont des arêtes dirigées ; les entrées, sorties et zones de transition sont des nœuds. Le coût d'une arête combine temps, énergie, virage, risque, déploiement du bras et priorité agronomique. Un optimiseur ordonne les segments sélectionnés sans modifier leur géométrie mesurée.

[Fields2Cover](https://fields2cover.github.io/) fournit une référence C++ BSD-3 pour la décomposition, l'ordre des passages et les chemins de couverture. Il peut servir de baseline et d'outil de comparaison, mais ses swaths 2D générés ne remplacent pas les rangs courbes 3D extraits ni les contraintes du bras.

### 8.3 Trajectoire dynamique

À partir de l'ordre choisi :

1. générer une spline 3D nominale à l'intérieur du corridor ;
2. optimiser temps et régularité sous contraintes de corridor, vitesse, accélération et jerk ;
3. aligner le yaw sur la tangente ou la face à traiter selon le montage **À valider** ;
4. rétracter le bras avant chaque transition non certifiée ;
5. simuler la mission complète avec l'enveloppe balayée et PX4 SITL ;
6. exiger l'approbation opérateur avant production du `TreatmentMissionPackage`.

Si aucun demi-tour sûr n'existe en bout de rang, la trajectoire doit prévoir une sortie, une montée ou une réentrée validée, pas inventer un virage dans une zone inconnue.

En vol, ROS 2 localise le drone, met à jour un corridor local et fournit des consignes haut niveau. PX4 conserve le contrôle critique, les limites, la géofence et les failsafes. Le drone peut ralentir, arrêter le traitement, rétracter le bras, replanifier localement dans le corridor ou abandonner ; il ne modifie pas silencieusement la carte approuvée.

Référence utile pour la séparation carte globale, trajectoire optimisée et replanning local : [Guidance, Navigation and Control for Autonomous Quadrotor Flight in Vineyards](https://doi.org/10.3390/s22228865).

## 9. Validation et métriques

### 9.1 Annotation

La vérité terrain doit être dessinée sur des zones indépendantes de l'ajustement des paramètres. La séparation entraînement/validation se fait par parcelle et par date, jamais par tuiles voisines du même orthomosaïque.

EscaYard permet de comparer les axes de rang aux positions RTK des ceps. Pour LaMole, les tracés manuels des publications sont à demander ; à défaut, une annotation indépendante en double lecture sera nécessaire.

### 9.2 Détection et carte

| Mesure | But |
|---|---|
| rappel/précision de longueur de rang | détecter les omissions et faux segments |
| erreur latérale médiane et P95 | précision géométrique |
| Hausdorff P95 | défaut local maximal robuste |
| exactitude des extrémités et lacunes | entrées, sorties et discontinuités |
| erreurs de fusion/séparation | validité topologique |
| erreur d'espacement inter-rang | qualité des corridors |
| rappel des murs/ruptures/obstacles | prévention des faux espaces libres |
| calibration de confiance | faire correspondre confiance annoncée et erreur réelle |
| taux de corridor déclaré sûr à tort | métrique de sûreté prioritaire, seuil **À valider** |

### 9.3 Trajectoire

- couverture des segments prescrits ;
- longueur, durée et énergie estimée ;
- distance minimale au sol, aux rangs, murs, poteaux et fils ;
- violations de corridor, géofence et dynamique ;
- nombre de rétractions, transitions et zones inconnues franchies ;
- erreur de suivi latérale/verticale dans SITL ;
- volume traité hors zone autorisée ;
- reproductibilité à configuration et données identiques.

## 10. Plan d'implémentation proposé

| Incrément | Sortie | Charge candidate **À valider** |
|---|---|---:|
| M0 — accès | demande LaMole envoyée, droits et inventaire reçus | 0,5 à 1 j.h + délai externe |
| M1 — import | importeur géospatial, EscaYard/VineLiDAR, rapport qualité | 15 à 26 j.h |
| M2 — annotations | outil ou format de correction, vérité terrain partielle | 4 à 7 j.h |
| M3 — rangs | DTM/CHM, masque vigne, orientation, splines et confiance | 13 à 20 j.h |
| M4 — carte | terrasses, entités, corridors, graphe et paquet candidat | 8 à 14 j.h |
| M5 — mission | ordre des rangs, transitions et spline 3D dynamique | 8 à 13 j.h |
| M6 — validation | métriques, tests de régression et scénarios SITL | 7 à 12 j.h |

Un prototype hors ligne cohérent représente donc environ 55 à 93 j.h, soit 11 à 19 semaines pour une personne, avec recouvrements possibles entre lots. Une démonstration réduite « un nuage → rangs → un corridor → une trajectoire » peut viser 25 à 40 j.h **À valider**. La robustesse multi-saison, l'intégration embarquée et la qualification de sûreté nécessiteront des incréments supplémentaires.

Le chemin critique recommandé est : EscaYard réduit → import → vérité terrain RTK → rangs → corridor unique → trajectoire SITL. LaMole est injecté dès réception sans modifier le contrat générique.

## 11. Traçabilité initiale

| Exigence | Composant/algorithme | Test prévu | Résultat actuel |
|---|---|---|---|
| `MAP-FUN-003` — nuage 3D géoréférencé | `GeospatialSurveyImporter` | CRS, emprise, précision et provenance | conception candidate |
| `MAP-FUN-004` — terrain/végétation/obstacles | terrain + classifieur hybride | IoU/rappel par classe et zones inconnues | **À valider** |
| `MAP-FUN-005` — rangs/terrasses/murs | champ d'orientation + traçage courbe | erreur latérale, topologie et rappel | **À valider** |
| `MAP-FUN-006` — ID/géométrie/confiance/date | modèle d'entités versionné | test de contrat et calibration de confiance | **À valider** |
| `MAP-FUN-007` — graphe réel | constructeur de topologie | cohérence des voisins, bouts et transitions | **À valider** |
| `MAP-FUN-008` — zones insuffisantes | `ConfidenceLayer` | défauts injectés et faux corridors sûrs | **À valider** |
| `TRT-FUN-003` — corridor continu | enveloppe 3D drone + bras | collision swept-volume en SITL | **À valider** |
| `TRT-FUN-005` — suivi du relief | profil 3D + contraintes dynamiques | pente, terrasse et rupture simulées | **À valider** |
| `SAFE-REQ-001` — autorité PX4 | interface ROS 2 haut niveau/PX4 | perte Offboard et dépassement de limite | séparation existante conservée |
| `SAFE-REQ-004` — fils multimodaux | `WireZone` conservatrice | fils absents/faiblement observés | **À valider** |

## 12. Décisions à prendre après le premier incrément

Restent **À valider** par benchmark ou données physiques :

- disponibilité et droits exacts de LaMole/Grospoli ;
- datum vertical et précision absolue des campagnes ;
- format vectoriel canonique et format embarqué ;
- seuils hauteur/couleur/cohérence et longueur maximale de lacune ;
- méthode de sol la plus robuste sur murs et terrasses ;
- optimisation de courbe : graphe discret, fast marching ou autre ;
- définition mécanique du volume balayé corps–bras ;
- marges, vitesses, accélérations et stratégie de transition ;
- besoin et architecture d'un modèle IA après mesure de la baseline géométrique.
