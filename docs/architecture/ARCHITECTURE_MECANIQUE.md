# Architecture mécanique

| Champ | Valeur |
|---|---|
| Référence | `DOC-MEC` |
| Nature | document vivant |
| Dernière mise à jour | 24 septembre 2026 |
| Statut | architecture et CAO du cartographe implémentées partiellement ; qualification physique **À valider** |

## 1. Objet

Ce document décrit les choix mécaniques du système, les pièces fabriquées et du
commerce, les sous-assemblages, leur fonctionnement, la nomenclature mécanique
et les vérifications. Le fonctionnement système est défini dans
[DOC-HLD](HLD.md) et les interfaces électriques dans
[DOC-ELEC](ARCHITECTURE_ELECTRIQUE_RESEAUX.md).

Le drone cartographe possède une première architecture CAO durable. La mécanique
du drone de traitement, du bras et du circuit de pulvérisation reste planifiée et
**À valider**.

## 2. Principes de conception CAO

Les conceptions durables résident dans `hardware/mecanique/` et suivent les
règles suivantes :

- un fichier FreeCAD par référence de pièce fabriquée ou équipement acheté ;
- arbre de construction natif conservé pour chaque pièce conçue ;
- sous-assemblages séparés et assemblage final par liens externes `App::Link` ;
- réutilisation d'une même référence pour les occurrences répétées ;
- sources fabricant conservées inchangées ;
- exports dérivés régénérables et fichiers CAO lourds exclus de Git ;
- placements, références et occurrences décrits dans `manifest.json`.

Le manifeste est l'autorité pour les noms de fichiers et matrices de placement.
Ce document explique l'intention et la nomenclature, sans recopier toutes les
coordonnées.

## 3. Architecture mécanique du système

```text
 Systeme_Cartographie
 ├── Drone_Cartographe
 │   ├── SA01_Chassis
 │   ├── SA02_Energie_EchangeRapide
 │   │   └── SA02A_Connecteur_SBSX75A
 │   ├── SA03_Avionique
 │   ├── SA04_Calcul
 │   ├── SA05_Capteurs_Isoles
 │   │   ├── SA05A_Bloc_capteurs
 │   │   └── 4 × SA05B_Appui_Sorbothane
 │   └── SA06_RTK
 └── SA07_Station_sol
```

Assemblages de référence :

- `hardware/mecanique/cartographe/assemblages/Drone_Cartographe.FCStd` ;
- `hardware/mecanique/cartographe/assemblages/Systeme_Cartographie.FCStd`.

`SA02_Energie` et `SA05_Capteurs` sont conservés comme variantes historiques.
Les configurations actives sont respectivement `SA02_Energie_EchangeRapide` et
`SA05_Capteurs_Isoles`.

L'orientation nadir Airy–Basler reste une hypothèse d'intégration **À valider**.
Les supports imprimés servent d'abord aux contrôles d'encombrement et de
rigidité ; une platine métallique reste une solution de repli après essais.
Les fixations critiques utilisent de la visserie métallique traversante. Les
éléments issus de la CAO fabricant qui ne font pas partie de la configuration
active restent masqués et explicitement exclus par le manifeste.

## 4. Sous-assemblages et fonctionnement

| Sous-assemblage | Fonction | Choix actuel | État |
|---|---|---|---|
| `SA01_Chassis` | structure, bras, train et propulsion | enveloppe fabricant Holybro X650 V2 | candidat ; résistance et vibrations **À valider** |
| `SA02_Energie_EchangeRapide` | maintenir et échanger la batterie sans outil | berceau fixe, cassette, guidage, sangle et réservation de loquet | CAO implémentée ; loquet et essais **À valider** |
| `SA02A_Connecteur_SBSX75A` | accouplement électrique pendant l'insertion | SBS X-75A et support P15 | implantation simplifiée ; tolérances et cycles **À valider** |
| `SA03_Avionique` | fixer Pixhawk, conversion et radios | maquette historique à deux niveaux sur plateaux carbone OEM, P06/P20, cales et sangles | ancienne CAO **Implémenté** ; migration vers porteuse commune **Planifié** |
| `SA04_Calcul` | fixer Jetson, SSD et refroidissement | maquette historique avec adaptateur P03 et quatre entretoises P04 | ancienne CAO **Implémenté** ; deux contacts connus, migration **Planifié** |
| `SA05A_Bloc_capteurs` | maintenir rigidement Airy, Basler et objectif entre eux | platine capteurs isolée | extrinsèques et champ de vue **À valider** |
| `SA05B_Appui_Sorbothane` | isoler le bloc capteurs tout en limitant son débattement | quatre appuis Sorbothane captifs | contacts locaux corrigés ; tenue **À valider** |
| `SA05_Capteurs_Isoles` | intégrer le bloc capteurs suspendu au drone | quatre appuis et retenues de câbles | huit poses contrôlées sans interférence ; **À valider** physiquement |
| `SA06_RTK` | éloigner et orienter antenne/récepteur RTK | support, entretoises et interface antenne | enveloppes provisoires **À valider** |
| `SA07_Station_sol` | porter base RTK, tablette, radio et accessoires | boîtier et éléments du commerce | architecture candidate **À valider** |

### 4.1 Batterie interchangeable

La batterie 6S 10 Ah candidate est installée dans une cassette guidée par P13 et
P14. Un verrouillage mécanique positif doit empêcher la sortie dans toutes les
orientations de vol. La connexion ne doit pas servir de retenue mécanique. Le
loquet représenté est une réservation et non un composant qualifié.

Le mécanisme doit être vérifié pour insertion incorrecte, absence de verrouillage,
traction câble, vibrations, chocs, usure, remplacement avec gants et impossibilité
de court-circuit. Tous les critères et tolérances restent **À valider**.

| ID | Exigence de cassette | Résultat actuel |
|---|---|---|
| `HW-BAT-SWAP-01` | échange sans outil, vis déposée ni sangle refaite | architecture définie ; essai non exécuté |
| `HW-BAT-SWAP-02` | prise détrompée accessible, manipulation par le corps | SBS X-75A intégré en CAO simplifiée |
| `HW-BAT-SWAP-03` | retenue positive et sécurité contre ouverture accidentelle | loquet à sélectionner |
| `HW-BAT-SWAP-04` | capture verticale/transversale et butée longitudinale | principe CAO contrôlé |
| `HW-BAT-SWAP-05` | échange mécanique et connexion en moins de 30 s | exigence acceptée ; essai **À valider** |
| `HW-BAT-SWAP-06` | pas de détérioration après cycles avec poussière et gants | critères et essai **À valider** |

L'extraction est longitudinale vers `+X`. Le connecteur est débranché
manuellement vers `-Y` avant extraction ; il ne constitue ni une butée ni un
verrou de batterie.

Le réceptacle SBS possède une bride représentée à 76,2 × 45,7 mm ; P15 reprend
une découpe 58,4 × 27,4 mm et quatre perçages Ø4,06 mm sur entraxes
42,93 × 35,56 mm. Dans le repère actuel, l'axe de connexion est parallèle à Y,
centré en X = 60 mm et Z = 125 mm, avec face de montage Y = -120 mm. Les modèles
sont reconstruits à partir des plans publics et restent à confronter aux STEP
fabricant ou aux pièces reçues.

### 4.2 Isolation du bloc capteurs

La caméra et le LiDAR restent solidaires sur `SA05A_Bloc_capteurs` afin de
préserver leur calibration extrinsèque. Quatre appuis Sorbothane isolent ce bloc
du châssis et des moteurs. Des pièces métalliques captives limitent le débattement
en cas de choc ou rupture. Les câbles doivent former une boucle souple et ne pas
court-circuiter l'isolation.

La correction sauvegardée les 15–16 septembre 2026 déplace l'Airy de +4 mm
suivant X (centre de montage X = -35 mm) et ses trois perçages sur P16. La
retenue de câble côté Airy est décalée de -3 mm suivant Y. Les arbres natifs
sont conservés. Huit poses discrètes ne présentent plus de volume commun
supérieur à 10⁻⁶ mm³ avec les appuis métalliques ; le contrôle du châssis
utilise les placements globaux des feuilles du modèle fabricant.

Preuves : `verification/correction_capteurs_20260915.json` et complément
du 16 septembre. Ce contrôle ne valide ni un mouvement continu, ni les jeux
avec tolérances, ni la déformation des élastomères. Les extrinsèques Airy/Basler
doivent être recalibrées ; le passage des câbles réels reste **À valider**.

La configuration de travail emploie quatre bagues Sorbothane
`0510030-30-10` 30 Shore 00 comme appuis porteurs et quatre tampons
`0510010-30-10` au rebond. La masse mobile estimée est 558–668 g, soit des
réactions calculées de 131–194 g par appui à 1 g, dans la plage catalogue
113–272 g. Ces valeurs reposent sur des masses et positions estimées. Spectre
moteur, raideur dynamique, fréquence propre, cisaillement, température, fluage
et tenue aux chocs restent **À valider**. Le bilan actualisé est conservé dans
`verification/dimensionnement_isolateurs_20260915.json` ; le fichier sans date
reste la preuve historique avant déplacement de l'Airy.

Le montage est représenté libre, sans précompression artificielle : la bague
inférieure porte la masse et le tampon supérieur peut se décoller légèrement au
repos. La vis et le manchon capturent l'ensemble sans serrer rigidement la
platine. Précompression, cisaillement, rebond et tolérances doivent être vérifiés
sur le montage physique.

### 4.3 Calculateur et thermique

La maquette CAO actuelle monte le kit développeur Orin Nano sur P03/P04.
Deux contacts aux entretoises arrière y ont été détectés ; cette géométrie
ne peut pas valider la nouvelle cible. Celle-ci associe la **Holybro Pixhawk
Jetson Baseboard**, le **Pixhawk 6X module seul** et un **Jetson Orin NX 16 Go**
sur une même porteuse. Son implantation, sa fixation, le refroidissement, la
circulation d'air, la protection contre les projections et l'accès au SSD,
à l'XT30 et aux autres connecteurs sont **À valider** après acquisition des
révisions et géométries exactes. P03/P04 et la platine Pixhawk P20 seront
réévalués ; aucune pièce existante n'est réputée compatible par simple analogie.


### 4.4 Porteuse cible du 24 septembre et CAO historique du 16 septembre

La nouvelle cible mécanique regroupe sur la **Holybro Pixhawk Jetson Baseboard**
le **Pixhawk 6X module seul** et le **Jetson Orin NX 16 Go**. Elle remplace
l'implantation séparée Pixhawk/base v2A dans SA03 et kit Orin Nano dans SA04.
Le support, l'isolation, la dissipation, les accès aux ports et les faisceaux
doivent être redéfinis sans présumer des perçages ou jeux de l'ancienne CAO.
Ce regroupement est **Planifié** ; les assemblages et le manifeste FreeCAD
restent ceux de la configuration du 16 septembre.

La carte commune **CA01** regroupe dans la cible la radio RP4TD, ses conversions
locales 5 V et les adaptations de synchronisation, hors porteuse. Le
**PM08-CAN** reste fixé au châssis près de la distribution, sur un support
séparé de CA01 et de la cassette batterie. Il reste sur le drone pendant
l'échange de pack. Le chemin de puissance cible est batterie → PM08-CAN →
toutes les branches. Le BEC1 dessert POWER1 et le BEC2 POWER2 du Pixhawk ;
la mesure DroneCAN rejoint CAN1 par un faisceau distinct. Les deux BEC ne
sont pas mis en parallèle. Le 5 V local protégé de CA01 est issu d'un départ
batterie aval du PM08-CAN et alimente notamment la radio, indépendamment du
Jetson. Un rail 12 V candidat dessert l'entrée XT30 de la porteuse ; le rail
LiDAR et les adaptations de synchronisation restent à définir. Brochages,
protections, budgets et essais sont décrits dans
[DOC-ELEC §4.2](ARCHITECTURE_ELECTRIQUE_RESEAUX.md#42-cahier-des-charges-de-la-carte-avionique-commune-ca01)
et [§4.3](ARCHITECTURE_ELECTRIQUE_RESEAUX.md#43-câblage-global-du-cartographe).

Le support fixe du PM08-CAN est **Planifié** : prévoir un appui isolant
vis-à-vis du carbone, un maintien positif accessible, une décharge des efforts
sur les câbles et l'accès aux connecteurs. Réserver l'enveloppe fabricant
45 × 41 × 26 mm hors câbles et tenir compte des 185 g annoncés câbles inclus ;
ce ne sont ni l'encombrement installé ni une masse mesurée dans notre montage.
[Source Holybro PM08-CAN](https://holybro.com/collections/power-modules-pdbs/products/dronecan-pm08-power-module-14s-200a).
Les rayons de courbure, terminaisons de puissance, dégagements de maintenance,
fixations, isolation des vis, vibrations et dissipation restent **À valider**.
Les fixations ne doivent pas contraindre le boîtier, les composants ou les
soudures ; aucun effort de cassette ne doit transiter par les câbles du PM.

Le raccordement batterie, le détrompage, la coupure et la séquence d'échange
restent à définir. POWER1, POWER2, DroneCAN et les départs d'alimentation
restent sur le châssis pendant l'échange du pack. Le connecteur SBS de puissance ne transporte pas
implicitement de signaux ; aucun échange sous charge n'est prévu.

Les fichiers CAO SA03/SA04, P03/P04/P06/P20 et les enveloppes ci-dessous
restent ceux de l'empilage du 16 septembre. Ils ne représentent ni la porteuse
Pixhawk Jetson, ni le module Orin NX 16 Go, ni le rail XT30 et ses câbles,
ni la nouvelle implantation CA01 ou le support fixe PM08-CAN. L'enveloppe
PM02D demeure historique. Les anciennes enveloppes RC et télémétrie séparées
ne représentent pas deux modules à ajouter au RP4TD. Aucune réserve de hauteur
ni absence de collision antérieure ne qualifie la nouvelle implantation.

La cible nécessite une reprise des sous-assemblages, du manifeste et du bilan
de masse après choix des révisions matérielles et des modèles fabricants. Le
contour de CA01, ses fixations, les dégagements antennes, l'isolation du carbone,
les connecteurs XT30, POWER1/POWER2 et CAN, le refroidissement et les rayons
de courbure restent **À valider**. Les circuits internes KiCad V0.3 conservent
leur ancienne définition ; le 5 V local protégé et les nouvelles interfaces
ne sont pas démontrés par la CAO ou le schéma actuels. Les nouvelles masses
alimenteront le modèle de simulation ; la CAO et Gazebo ne démontrent pas la
tenue thermique du module, de la porteuse ou des faisceaux.

Les paragraphes et cotes suivants décrivent uniquement la CAO historique
**Implémenté** le 16 septembre ; ils ne sont pas la géométrie de la cible.

La pile utilise les deux plateaux carbone existants du X650. Le modèle fabricant
et ses perçages restent inchangés. Les hauteurs sont exprimées dans le repère
global du drone, Z vers le haut.

| Niveau | Implantation CAO | Fixation |
|---|---|---|
| plateau carbone inférieur | Z = 0 à 2 mm | géométrie OEM |
| support auxiliaire P06 | Z = 3,2 à 6,2 mm, après quatre cales P22 de 1,2 mm | quatre passages existants M3 à X/Y = ±15,25 mm ; vis M3×10 fraisées affleurantes, écrous métalliques sous le carbone |
| modules auxiliaires | PM02D et DC/DC au-dessus de P06 ; RC et synchronisation décalés de +5 mm en Y ; télémétrie tournée de 90° et centrée en (0, -45) mm | cinq sangles réglables de 8 mm traversant P06 ; mousses/enveloppes existantes conservées |
| plateau carbone supérieur | Z = 31 à 33 mm | géométrie OEM |
| platine P20 | 128 × 98 × 2 mm, Z = 34 à 36 mm | quatre cales P21 de 1 mm ; trous OEM Ø2,2 mm à (X, Y) = (±29, ±43) mm, vis M2×8, rondelles et écrous |
| Pixhawk 6X | base Z = 37 mm, sommet proche de 80,903 mm | intercalaire électrique de 1 mm ; sangle réglable traversant P20, enveloppe haute Z = 81,6 mm |

L'intercalaire n'est pas une qualification d'isolation électrique ou vibratoire.
Les sangles sont des enveloppes de boucles réglables ; référence, fermeture,
précharge, résistance et compatibilité avec le boîtier restent **À valider**.
Le modèle présente la chaîne de retenue et la visserie, sans inventer de
taraudages dans les équipements candidats. Les capteurs de vol internes et
l'autorité PX4 restent ceux du Pixhawk.

La réserve verticale au-dessus du DC/DC est **2,8 mm sous le carbone**, ou
**2,2 mm avec la sangle représentée**. C'est un encombrement nominal, pas un
passage de connecteur qualifié. Les sorties des câbles doivent être latérales ;
les connecteurs réels devront être modélisés avant gel. La sangle Pixhawk
laisse 3,4 mm sous l'enveloppe inférieure du berceau batterie à Z = 85 mm.
Les accès carte SD, USB, boutons, antennes et outils de montage sont à vérifier
avec les révisions matérielles exactes.

Les écrous portent directement sous les plateaux carbone : répartition
d'appui, rondelles éventuelles, couples et protection locale restent **À valider**.
Les cales ne démontrent pas l'isolation des vis traversantes.

Les pièces nouvelles conservent des arbres CSG natifs. Une seule référence est
réutilisée pour chaque type de cale et de visserie. Les fichiers actifs, matrices
de placement et quantités sont dans le manifeste ; les STEP/STL de P06 et
P20–P22 sont sous `exports/iteration_20260916/`. Leur présence autorise la
revue de conception, pas la fabrication fonctionnelle ou le vol.

### 4.5 Points restant à fermer pour le drone cartographe

| Point | Traitement réalisé / décision de travail | Donnée ou validation nécessaire pour clôturer |
|---|---|---|
| contacts capteurs | géométrie corrigée, huit poses contrôlées et bilan statique mis à jour | tolérances, câbles, rotations, ancrages M3, essai vibratoire et calibration |
| fixation avionique | ancienne CAO P06, P20–P22 et retenues créées sur trous OEM | nouveau support de porteuse, matériau/procédé, tolérances, freinage, accès et essais de retenue |
| Jetson / P04 | deux collisions de l'ancienne maquette Orin Nano restent ouvertes | modèle exact porteuse/Orin NX, nouvelle fixation et contrôle d'interférence avant fabrication |
| loquet batterie | conserver verrouillage mécanique positif indépendant du SBS ; famille Southco 97 avec verrou secondaire candidate | référence complète loquet/gâche, efforts, montage, essais avec gants et cycles |
| batterie et cassette | enveloppe 6S 10 Ah candidate conservée | pack exact, tolérances, gonflement, mousse, sangles et masse réelle |
| SBS / faisceau | implantation existante maintenue | contacts et câbles réels, rayon de courbure, traction, précharge et échauffement (DOC-ELEC) |
| RTK / antenne | supports P07–P09 et enveloppes conservés | récepteur/antenne exacts, ancrage, connecteurs, dégagement radio et repères |
| caméra / optique | Basler conservée ; translation Airy traçable | objectif réel, champ de vue, masques, longueur des vis et extrinsèques |
| distribution / convertisseurs / radios | cible CA01 avec RP4TD et 5 V local ; PM08-CAN fixé au châssis ; ancienne CAO conservée | contour/fixations CA01, support PM08-CAN, porteuse commune et XT30, décharge câbles, encombrement, vibrations et thermique ; actualiser SA03/SA04 après définition (DOC-ELEC §4.2) |
| masse et centrage | quantités CAO actives corrigées ; bilan isolateurs actualisé | masse de chaque pièce fabriquée et équipement, centre de gravité complet, poussée/endurance |
| sources et exports | sources fabricant conservées, corrections natives et exports locaux | réouverture/recalcul, revue de montage puis essais matériels selon DOC-VAL |

L'approbation d'une référence candidate ou d'un procédé ne remplace pas les
essais. Les moyens de fabrication et les équipements effectivement achetés
n'ont pas encore été confirmés ; les pièces sont donc **Implémenté** en CAO
avec fabrication et usage physique **À valider**.

## 5. BOM mécanique du cartographe

### 5.1 Pièces fabriquées

Les quantités ci-dessous décrivent la configuration active du manifeste FreeCAD
historique, encore non migrée vers la porteuse commune ; elles ne constituent
pas la nomenclature de la nouvelle cible. Elles seront reprises à la revue de
conception puis confirmées à la revue de fabrication.

| Réf. | Qté | Fonction | Procédé/matière | État |
|---|---:|---|---|---|
| `P01_Platine_capteurs` | 1 | ancienne platine rigide | prototype imprimé **À valider** | variante historique |
| `P02_Entretoise_capteurs` | 4 | ancienne liaison capteurs | prototype imprimé **À valider** | variante historique |
| `P03_Adaptateur_Jetson` | 1 | interface calculateur/châssis | prototype imprimé **À valider** | CAO disponible |
| `P04_Entretoise_Jetson` | 4 | fixation Jetson | prototype imprimé **À valider** | contacts à corriger |
| `P05_Bac_batterie` | 1 | ancien maintien batterie | prototype imprimé **À valider** | remplacé dans la configuration active |
| `P06_Platine_auxiliaire` | 1 | support avionique/énergie | prototype imprimé **À valider** | CAO disponible |
| `P07_Support_RTK` | 1 | support récepteur RTK | prototype imprimé **À valider** | CAO disponible |
| `P08_Entretoise_RTK` | 4 | fixation RTK | prototype imprimé **À valider** | CAO disponible |
| `P09_Interface_antenne` | 1 | interface antenne RTK | prototype imprimé **À valider** | CAO disponible |
| `P10_Retenue_cable` | 4 | reprise des câbles | prototype imprimé **À valider** | position locale corrigée ; ancrage physique **À valider** |
| `P11_Boitier_base_sol` | 1 | protection électronique de base | prototype imprimé **À valider** | CAO disponible |
| `P12_Couvercle_base_sol` | 1 | fermeture du boîtier sol | prototype imprimé **À valider** | CAO disponible |
| `P13_Berceau_rapide` | 1 | guidage de cassette | prototype imprimé **À valider** | CAO disponible |
| `P14_Cassette_batterie` | 1 | porte-batterie amovible | prototype imprimé **À valider** | CAO disponible |
| `P15_Support_SBSX75A` | 1 | maintien du réceptacle | prototype imprimé **À valider** | CAO disponible |
| `P16_Platine_capteurs_isolee` | 1 | bloc rigide Airy/Basler | prototype imprimé **À valider** | CAO disponible |
| `P17_Support_deporte_isolation` | 4 | interface appuis/châssis | prototype imprimé **À valider** | CAO disponible |
| `P18_Manchon_limiteur_metal` | 4 | butée de débattement | métal, procédé **À valider** | quantité active issue du manifeste ; tenue **À valider** |
| `P19_Rondelle_capture_metal` | 4 | capture de l'appui | métal, procédé **À valider** | quantité active issue du manifeste ; tenue **À valider** |
| `P20_Platine_avionique_superieure` | 1 | support Pixhawk 128 × 98 × 2 mm | plaque isolante ou matériau à qualifier | **Implémenté** en CAO |
| `P21_Cale_avionique_1mm` | 4 | liaison au plateau supérieur OEM | isolant rigide **À valider** | **Implémenté** en CAO |
| `P22_Cale_avionique_12` | 4 | dégagement sangles sous P06, 1,2 mm | isolant rigide **À valider** | **Implémenté** en CAO |

### 5.2 Équipements et fournitures à impact mécanique

| Réf./famille | Qté | Rôle | État |
|---|---:|---|---|
| châssis X650 V2 et propulsion associée | 1 | structure et portance | candidat **À valider** |
| batterie LiPo 6S 10 Ah Tattu candidate | 1 en vol | énergie et masse principale amovible | sélection **À valider** |
| connecteur Anderson SBS X-75A | 1 paire | connexion rapide de puissance | présélection d'étude |
| loquet rapide | 1 | verrouillage positif de cassette | référence **À valider** |
| mousse et sangles de cassette | 1 jeu | calage et retenue secondaire | dimensions/matière **À valider** |
| Sorbothane 30 duro | 4 appuis | isolation du bloc capteurs | géométrie finale **À valider** |
| vis M2, écrous frein et capture métallique | 4 jeux visés | limitation sûre du débattement | dimensionnement **À valider** |
| Airy, Basler et objectif | 1 chacun | bloc optique/LiDAR calibré | équipements candidats/présélectionnés |
| porteuse Holybro Pixhawk Jetson, Pixhawk 6X module seul et Orin NX 16 Go | 1 chacun | ensemble calcul/vol de la nouvelle cible | **Planifié** ; encombrement, fixation et thermique **À valider** |
| GNSS et antenne | 1 chacun | navigation et interface de fixation | enveloppes partielles **À valider** |
| PM08-CAN et support fixe châssis | 1 par drone | distribution mesurée et deux BEC, près de la distribution | **Planifié** ; enveloppe fabricant 45 × 41 × 26 mm hors câbles, 185 g avec câbles ; intégration **À valider** |
| base RTK, mât, pieds, boîtier et tablette | 1 jeu sol | station de référence et opérateur | architecture candidate |

Les références électriques détaillées sont tenues dans `DOC-ELEC`. Les
références et occurrences CAO exactes restent dans
`hardware/mecanique/cartographe/manifest.json`.

## 6. Budgets mécaniques

Le bilan actuel estime le cartographe avec batterie candidate entre 4,7 et
5,3 kg. Cette plage provient de volumes CAO et provisions, pas d'une pesée ; elle
reste **À valider**. La cassette rapide ajoute de la matière et doit être
réintégrée au bilan après définition du loquet et du faisceau. Ce bilan historique
n'intègre ni le remplacement par PM08-CAN ni la porteuse commune avec Orin NX.
Réconcilier le contenu du kit, retirer les anciens modules et supports devenus
inutiles, puis compter le PM08-CAN, la porteuse, l'Orin NX, leurs supports,
refroidissement et faisceaux réels sans double comptage des câbles inclus.
Les 185 g fabricant ne s'ajoutent donc pas directement au total historique.

### 6.1 Bilan de masse de travail

| Poste embarqué | Masse de travail |
|---|---:|
| kit X650 complet sans batterie | 2 000 g annoncés, configuration exacte **À valider** |
| Airy | 230 g nominaux |
| Basler hors objectif | 85 g nominaux |
| objectif | 80–150 g provisionnels |
| ancien kit Jetson, refroidissement et SSD | 180–350 g provisionnels, hors nouvelle cible |
| rover RTK et antenne | 70–160 g provisionnels |
| conversions, synchronisation et RC | 60–140 g provisionnels |
| anciennes pièces imprimées P01–P10, pleines | environ 350 g calculés |
| câbles, visserie, mousses et sangles additionnels | 100–200 g provisionnels |
| réserve d'intégration | 200–300 g |
| **total historique hors batterie** | **3 355–3 965 g — À valider** |

Le volume plein actualisé P13 + P14 + P15 est environ 247,55 cm³, soit
309,4 g à la densité hypothétique de 1,25 g/cm³. Il remplace l'ancien bac P05
d'environ 63 g et ajoute donc environ 246 g avant connecteurs, loquet, visserie
et faisceau. Le bilan total 4,7–5,3 kg doit être recalculé après tranchage et
pesée de cette variante.

### 6.2 Batteries comparées

| Candidate | Énergie | Masse publiée | Dimensions nominales | Statut |
|---|---:|---:|---:|---|
| Tattu G-Tech 8 Ah 6S | 177,6 Wh | 1 044 ou 1 160 g | 172,2 × 65,58 × 45,5 mm | alternative légère ; fiche incohérente **À valider** |
| Tattu G-Tech 10 Ah 6S | 222 Wh | 1 350 ±20 g | 176 × 66 × 58 mm, tolérances publiées ±5/±2/±2 | candidate de dimensionnement **À valider** |
| Tattu Plus 12 Ah 6S | 266,4 Wh | 1 670 ±100 g | 202 × 76 × 61 mm | trop longue pour l'enveloppe actuelle |

Avec la 10 Ah, l'ancienne estimation donne 4,685–5,335 kg au décollage. La
masse maximale publiée du X650 et ses durées publicitaires ne constituent pas
une qualification de la configuration chargée.

### 6.3 Sensibilité d'autonomie

En supposant, uniquement pour étude, 80 % des 222 Wh disponibles avant réserve :

| Puissance moyenne totale | Durée calculée |
|---:|---:|
| 600 W | 17,8 min |
| 800 W | 13,3 min |
| 1 000 W | 10,7 min |

Cette table n'est pas une prévision de vol. Puissance chargée, température,
vieillissement et réserve de retour doivent être mesurés.

Avant gel de la plateforme :

- peser chaque référence et l'assemblage complet ;
- mesurer centre de gravité dans les trois axes ;
- vérifier poussée, marge de contrôle, vibration et endurance chargée ;
- vérifier rigidité des supports et maintien des calibrations ;
- réaliser bilan thermique du Jetson, des convertisseurs et de la batterie ;
- confirmer encombrements, champs de vue et absence de masque par le châssis.

Les limites commerciales du X650 ne sont pas des exigences qualifiées du projet.

## 7. Interfaces mécaniques critiques

| Interface | Risque | Vérification requise |
|---|---|---|
| châssis ↔ charge utile | flexion, desserrage, résonance | calcul/mesure de rigidité et essai vibratoire |
| Airy ↔ Basler | dérive extrinsèque | cible de calibration avant/après essai |
| bloc capteurs ↔ isolateurs | contact en butée, mode propre inadapté | débattement, modal et essai moteur |
| batterie ↔ cassette | éjection ou insertion partielle | essais multi-orientations, chocs et cycles |
| cassette ↔ SBS X-75A | effort transmis au connecteur | tolérances, guidage, cycles et traction câble |
| Jetson ↔ support | contact, chauffe, maintenance | contrôle d'interférence et essai thermique |
| antenne RTK ↔ structure | masque, multipath, vibration | champ libre, répétabilité et essai GNSS |
| câbles ↔ pièces mobiles/isolées | fatigue ou pont vibratoire | rayon, rétention, frottement et cycles |

## 8. Vérification et traçabilité

Les protocoles transversaux, résultats et statuts de qualification sont
centralisés dans [DOC-VAL](../VALIDATION_QUALIFICATION.md).

| Exigence | Composant | Test/preuve | Résultat |
|---|---|---|---|
| `MEC-ARC-001` réutiliser les références | arborescence FreeCAD | `verification/hierarchie.json` | contrôlé sur la maquette |
| `MEC-BAT-001` échange sans outil et verrouillage positif | P13, P14, loquet | `verification/echange_rapide.json` puis essai physique | CAO contrôlée ; physique **À valider** |
| `MEC-CON-001` ne pas charger mécaniquement le connecteur | guidage cassette, P15 | `verification/integration_SBSX75A.json`, cycles | implantation contrôlée ; cycles **À valider** |
| `MEC-VIB-001` préserver les capteurs et leur calibration | SA05 capteurs isolés | `verification/isolation_capteurs.json`, vibration et calibration | contacts corrigés ; huit poses contrôlées ; physique **À valider** |
| `MEC-AVI-001` retenue et intégration avionique | ancienne CAO P06, P20–P22 ; cible porteuse commune à intégrer | `verification/avionique_empilee_20260916.json`, puis nouvelle revue CAO et essai physique | ancienne CAO contrôlée ; cible et tenue **À valider** |
| `MEC-MAS-001` respecter masse et centrage qualifiés | assemblage complet | pesée et centrage | non exécuté |
| `MEC-INT-001` absence d'interférences | tous sous-assemblages | contrôles FreeCAD et revue physique | capteurs et avionique contrôlés sur périmètre déclaré ; contacts Jetson ouverts |
| `MEC-THM-001` maintenir les températures admissibles | calcul et enveloppes | banc à puissance nominale | **À valider** |

Les fichiers JSON de `hardware/mecanique/cartographe/verification/` sont des
preuves machine-lisibles. Ils ne remplacent pas les essais physiques.

## 9. Architecture du drone de traitement

Les sous-systèmes suivants sont requis mais non conçus : châssis porteur, bras
vertical rétractable, retenue en panne, distribution de fluide, buses par étage,
protection contre les fuites et volumes de collision. Géométrie, matériaux,
efforts, masse, cinématique et interfaces sont **À valider** avant toute CAO
présentée comme référence.

## 10. Références et historique consolidés

- Les principes CAO, la batterie interchangeable, le connecteur et l'isolation
  vibratoire sont définis respectivement aux sections 2 et 4.
- Sources primaires : [X650 Holybro](https://holybro.com/products/x650-development-kit),
  [Tattu 10 Ah](https://genstattu.com/ta-30c-10000-6s1p-ec5.html),
  [SBS X-75A Anderson](https://www.andersonpower.com/product-lines/sbsx-connector-series/),
  [bagues Sorbothane](https://www.sorbothane.com/sorbothane-products/standard-industrial-products/product/bushings/)
  et [loquets Southco 97](https://media.southco.com/media/static/Literature/97.en.pdf).
- Données techniques détaillées : `hardware/mecanique/cartographe/manifest.json`
  et fichiers machine-lisibles de `verification/`.

## Journal de modifications

| Date | Modification |
|---|---|
| 24 septembre 2026 | cible porteuse Holybro avec Pixhawk 6X module et Orin NX 16 Go ; BEC1/2 vers POWER1/POWER2, CA01 5 V local et XT30/12 V candidat ; SA03/SA04, manifeste et preuves CAO historiques non migrés |
| 22 septembre 2026 | cible PM08-CAN fixé au châssis près de la distribution, hors pack ; deux BEC affectés vol/radio et auxiliaires/synchronisation ; nouvelle enveloppe et masse à intégrer, CAO et circuits KiCad V0.3 non migrés |
| 22 septembre 2026 | PM02D complet en tête de distribution avec faisceau adapté ; BEC conservé hors CA01 ; support sur cassette à étudier ; simulation distincte de qualification électrique |
| 21 septembre 2026 | PM02D hors CA01, support isolant séparé à définir avec maintien, accès et décharge câbles ; liaison directe POWER1 et dérivation radio depuis le vol ; CAO SA03 inchangée |
| 17 septembre 2026 | intégration CA01 planifiée, PM02D rapporté candidat ; CAO SA03 conservée et limites explicites des réserves d'encombrement antérieures |
| 16 septembre 2026 | correction des contacts capteurs, bilan isolateurs et quantités ; pile avionique sur ancrages OEM, P20–P22, retenues, exports et points ouverts |
| 13 septembre 2026 | consolidation des décisions actives de CAO, montage capteurs, batterie et isolation ; retrait du registre ADR |
| 10 septembre 2026 | consolidation des choix, sous-assemblages, exigences batterie, BOM, masses, autonomie et preuves existantes |
