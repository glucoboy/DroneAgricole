# Architecture mécanique

| Champ | Valeur |
|---|---|
| Référence | `DOC-MEC` |
| Nature | document vivant |
| Dernière mise à jour | 5 octobre 2026 |
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

### 2.1 Catalogue courant et archives — 4 octobre 2026

Le tri historique du 4 octobre conservait **10 sous-assemblages courants et deux montages de
construction** dans `hardware/mecanique/cartographe/sous_assemblages/`.
Les versions précédentes sont dans `archives/avant_tri_20261004/`, avec une
copie de leurs pièces et montages liés aux mêmes chemins relatifs. Treize
anciens sous-assemblages, cinq assemblages globaux et 31 sauvegardes FreeCAD
ont quitté les répertoires courants. Aucun natif conservé ou archivé n'a
changé d'empreinte ; la géométrie et les placements restent identiques.

Le [catalogue](../../hardware/mecanique/cartographe/manifest.json), clé
`catalogue_courant_20261004`, décrit la sélection et la correspondance des
anciens chemins vers l'archive. Le manifeste et le guide précédents restent
dans l'instantané archivé. Les preuves datées conservent leur périmètre
historique ; les chemins des configurations archivées sont explicitement
relocalisés dans le catalogue et la BOM cible.

L'intégration locale de stack est le seul assemblage conservé dans
`assemblages/`. Le faisceau SA08 est lié à cette intégration locale ; GNSS et station sol restent séparés.
Aucun nouveau drone complet n'est assemblé ou qualifié par ce rangement.
La proposition GNSS sur plateaux reste **Planifié / À valider** ; les routes
du faisceau sont désormais recalées sur la stack revue (§4.1.3.3), avec ports
réservés et interfaces de lot À valider. La batterie mobile est désormais
`SA02_Cassette20Ah_Coulissante` et le récepteur fixe `SA02A_Dock20Ah`.
`SA02_Contacts20Ah` et `SA07_Distribution_Systeme_Candidat` sont conservés
comme montages historiques non installés ; ils ne sont pas des doublons à embarquer.

La recette de stack reprend le châssis rehaussé archivé puis rétablit en
mémoire ses liens vers les pièces courantes ; aucune dépendance vers des
pièces archivées n'est introduite dans le nouveau châssis à régénérer.
La reprise de source a été testée, sans relancer la génération de la stack.
Les recettes antérieures de variantes retirées restent des preuves historiques,
distinctes des commandes de maintenance du catalogue courant.
Contrôles de rangement et réouverture **Implémenté**, physique **À valider** :
DOC-VAL§12.1.6 et [guide d'ouverture](../../hardware/mecanique/cartographe/README.md).

## 3. Architecture mécanique du système

```text
 Integration_Stack_Revue_20261003 (principal, étude locale)
 ├── SA01_Chassis_Stack_Revue_20261003
 ├── SA02_Cassette20Ah_Coulissante — Batterie 20 Ah, 67 pièces mobiles
 ├── SA02A_Dock20Ah — Récepteur de batterie 20 Ah, 72 pièces fixes
 ├── SA03_CA01_Holybro_Revue_20261003
 ├── SA05_Capteurs_Isoles
 │   ├── SA05A_Bloc_capteurs
 │   └── 4 × SA05B_Appui_Sorbothane
 ├── SA08_Faisceau_Systeme_Candidat
 ├── PM08-CAN
 ├── PDB18138
 ├── P57, plateau énergie inférieur
 ├── JETI MainSwitch100
 ├── Commande magnétique JETI
 └── Isolateur UART Waveshare15817

 Sous-assemblages séparés de cette étude locale :
 SA06_RTK_Helical_Systeme_Candidat
 SA07_Station_sol
 Montages historiques non installés :
 SA02_Contacts20Ah
 SA07_Distribution_Systeme_Candidat
```

Dernière intégration mécanique à ouvrir :

- `hardware/mecanique/cartographe/assemblages/Integration_Stack_Revue_20261003.FCStd`.

Les anciennes intégrations complètes `Drone_Cartographe_20Ah` et
`Systeme_Cartographie_20Ah` sont dans l'archive du §2.1, ainsi que le candidat
système complet utilisant encore le précédent préplacement d'avionique.

La configuration de travail adopte la batterie **6S 20 Ah**, une cassette
coulissante et une rehausse du dernier plateau de **45 mm au total** :
20 mm historiques puis25 mm supplémentaires pour le BMS au-dessus du pack.
Les colonnes P37 mesurent95 mm et le plateau est à Z128…130 mm. Les assemblages précédents, dont `SA02_Energie_EchangeRapide`,
restent des archives. `SA05_Capteurs_Isoles` est conservé. L'état **Implémenté**
désigne la CAO ; la fabrication et le fonctionnement physique restent **À valider**.

L'orientation nadir Airy–Basler reste une hypothèse d'intégration **À valider**.
Les supports imprimés servent d'abord aux contrôles d'encombrement et de
rigidité ; une platine métallique reste une solution de repli après essais.
Les fixations critiques utilisent de la visserie métallique traversante. Les
éléments issus de la CAO fabricant qui ne font pas partie de la configuration
active restent masqués et explicitement exclus par le manifeste.

## 4. Sous-assemblages et fonctionnement

| Sous-assemblage | Fonction | Choix actuel | État |
|---|---|---|---|
| `SA01_Chassis_Stack_Revue_20261003` | structure, bras, train et propulsion | X650 V2, colonnes P37 de95 mm et plateau supérieur rehaussé de25 mm supplémentaires pour le BMS au-dessus du pack ; noms stables | CAO **Implémenté** ; résistance et vibrations **À valider** |
| `SA02_Cassette20Ah_Coulissante` | emporter la batterie et sa protection pendant l’échange | 67 pièces mobiles : pack, BMS supérieur, captures, coffret et contacts/fils TE mobiles | CAO **Implémenté**, migration contrôlée ; essais physiques **À valider** |
| `SA02A_Dock20Ah`, label Récepteur | guider et retenir la batterie dans le drone | 72 pièces fixes : rails, butées, loquet, support et contacts/fils TE fixes | CAO **Implémenté**, migration contrôlée ; verrouillage réel et essais **À valider** |
| six équipements et supports directs du principal | couper, mesurer et distribuer l’énergie, isoler l’UART | JETI et commande, PM08-CAN, PDB18138, P57 et Waveshare15817 ; ancien SA07 non installé | parentage CAO **Implémenté** et contrôlé ; montage physique **À valider** |
| contacts du dock 20 Ah | accouplement pendant la translation, indépendant de la retenue | paire TE ELCON 125A Middle Drawer répartie entre batterie et récepteur ; JETI directement lié au principal | sélection commerciale ; tolérances, courant et séquence **À valider** |
| `SA03_Avionique_Rehausse20` | libérer le logement et fixer l'avionique | Pixhawk historique déplacé au-dessus du plateau avec P27 ; niveau inférieur P06 conservé | CAO **Implémenté** ; migration vers porteuse commune **Planifié** |
| `SA04_Calcul` | fixer Jetson, SSD et refroidissement | maquette historique avec adaptateur P03 et quatre entretoises P04 | ancienne CAO **Implémenté** ; deux contacts connus, migration **Planifié** |
| `SA05A_Bloc_capteurs` | maintenir rigidement Airy, Basler et objectif entre eux | platine capteurs isolée | extrinsèques et champ de vue **À valider** |
| `SA05B_Appui_Sorbothane` | isoler le bloc capteurs tout en limitant son débattement | quatre appuis Sorbothane captifs | contacts locaux corrigés ; tenue **À valider** |
| `SA05_Capteurs_Isoles` | intégrer le bloc capteurs suspendu au drone | quatre appuis et retenues de câbles | huit poses contrôlées sans interférence ; **À valider** physiquement |
| `SA06_RTK` | étudier H-RTK F9P DroneCAN Helical STM32G4 et son antenne à ciel dégagé | nouveau support, câble CAN, UART2 PPS/GPRMC, antenne et dégagement | CAO historique Rover patch non migrée ; variante et montage **À valider** |
| `SA07_Station_sol` | porter H-RTK F9P Base, antenne HANT-X627A, poste et radio | mât/trépied, boîtier et éléments du commerce | implantation cible **À valider** |

### 4.1 Batterie interchangeable

La référence choisie pour l'intégration est **Tattu TAA200006S5X9S**, NMC 6S
20 Ah, 22,2 V nominaux, 444 Wh, 1 950 ±20 g et 193 ×76 ×58 mm. L'enveloppe
198 ×78 ×60 mm utilisée pour les jeux est une hypothèse d'étude, sans tolérance
fabricant publiée pour cette référence. La cassette entre au-dessus des bras.
Le logement initial Z33…Z103 et la rehausse de20 mm sont historiques :
la configuration BMS courante emploie le plateau supérieur à Z128…130 sur
colonnes P37 de95 mm (§4.1.3.3). Le Pixhawk historique avait été déplacé
au-dessus du plateau ; la pile Holybro/CA01 figure dans l’intégration locale courante.

La batterie reste montée dans sa cassette : les vis et captures sont permanentes
pour chaque pack. L'échange consiste à faire coulisser cet ensemble jusqu'aux
butées mécaniques réglables. La gâche **Southco R4-90-0521-10** entre alors dans
le loquet automatique à deux stages **R4-05-40-405-10**. La commande manuelle
libère le loquet pour l'extraction vers `+X`. La butée, les rails et le loquet
reprennent les efforts ; aucun effort de retenue ne doit passer par les contacts.
Les stages du cliquet et sa charge admissible ne sont pas simulés par la CAO.

Le mécanisme doit être vérifié pour insertion incorrecte, absence de verrouillage,
traction câble, vibrations, chocs, usure, remplacement avec gants et impossibilité
de court-circuit. Tous les critères et tolérances restent **À valider**.

| ID | Exigence de cassette | Résultat actuel |
|---|---|---|
| `HW-BAT-SWAP-01` | échange sans outil, vis déposée ni sangle refaite | cassette et poignée natives ; essai non exécuté |
| `HW-BAT-SWAP-02` | prise détrompée accessible, manipulation par le corps | contacts guidés accouplés par insertion ; tension coupée pendant l'échange |
| `HW-BAT-SWAP-03` | retenue positive et sécurité contre ouverture accidentelle | Southco R4-05-40-405-10 et gâche exacte ; effort et commande à valider |
| `HW-BAT-SWAP-04` | capture verticale/transversale et butée longitudinale | butées représentées ; retenue sous efforts dans toutes les orientations **À valider** |
| `HW-BAT-SWAP-05` | échange mécanique et connexion en moins de 30 s | exigence acceptée ; essai **À valider** |
| `HW-BAT-SWAP-06` | pas de détérioration après cycles avec poussière et gants | critères et essai **À valider** |

L'échange s'effectue au sol, PX4 désarmé et moteurs arrêtés. Les pales doivent
être orientées parallèlement au grand axe de translation pour dégager le passage.
Le disque d'hélice de 15 pouces laisse seulement 78,81 mm entre les rotors avant,
alors que le fond de cassette mesure 90 mm : une insertion sans condition sur
la position des pales serait bloquée. Les pales réelles ne sont pas présentes
dans le STEP OEM ; leur profil et le maintien de leur orientation sont **À valider**.
La coupure JETI doit être commandée avant la libération du loquet ; voir DOC-ELEC.
La connexion SBS manuelle et les pièces P13–P15 appartiennent à l'archive 10 Ah.

#### 4.1.1 Archive de préétude : berceau fixe et capot, 2 octobre 2026

L'intégration est réexaminée pour les candidats 6S 16 et 20 Ah, sans
sélectionner leur capacité. Le logement entre butées de P14 est **184 × 70 mm** :
il ne reçoit pas leurs enveloppes nominales de 192 × 76 et 193 × 76 mm.
L'objet natif `PatteGache` existe dans P14 mais n'est pas inclus dans
`CassetteBrute` ; la cassette finale ne comporte donc pas cette patte.
La réservation historique de loquet ne démontre pas un verrouillage fonctionnel.

Le plateau OEM `Part__Feature311` mesure 128 × 120 × 2 mm, à Z = 83…85 mm.
Ses quatre lumières de 27 × 3 mm sont centrées en X = ±36 et Y = ±33,5 mm.
Les trous de P13 en X = ±40 et Y = ±35 mm ne sont pas centrés sur ces lumières.
La reprise candidate utilise leurs centres, avec des perçages Ø3,2 mm dans
le nouveau berceau pour des fixations M3. Elle évite de proposer un nouveau
perçage OEM, mais l'accès sous-face, les rondelles, les fixations occupées,
l'anti-glissement et la résistance restent **À valider**.

Une variante de **berceau fixe avec capot articulé captif** est préparée pour
l'échange de la batterie seule. Ce principe supprime la cassette portée par
chaque pack et permet d'agir sur un cadre rigide plutôt que de serrer le loquet
directement contre la batterie. La cassette dédiée reste une alternative si
la protection du pack ou la manipulation réelle l'impose. La configuration
active `SA02_Energie_EchangeRapide` est conservée pour comparaison.

| Paramètre de la variante | Valeur candidate et justification |
|---|---|
| Logement intérieur XY | 204 × 84 mm ; enveloppe commune étudiée 198 × 78 mm, puis protection et jeu |
| Batterie 16 Ah | nominal 192 × 76 × 65 mm ; enveloppe avec tolérances publiées 197 × 78 × 67 mm |
| Batterie 20 Ah | nominal 193 × 76 × 58 mm ; enveloppe 198 × 78 × 60 mm issue de tolérances d'étude, **non publiées pour cette référence** |
| Appui inférieur | cadre Z85…89, plaque isolante candidate 1 mm, mousse réservée 2 mm ; batterie 16 Ah à Z92 |
| Compensation 20 Ah | cale candidate de 7 mm ; même hauteur nominale supérieure que la 16 Ah |
| Capture supérieure | capot rigide à Z160…163, ouverture intérieure 192 × 72 mm ; dépassement de la largeur du pack empêché en position fermée |
| Ouverture | axe Y candidat en X = −110, Z = 161,5 mm ; angle d'étude 110°, extraction du pack vers +Z |

À l'enveloppe maximale de 67 mm, le pack atteint Z159 : la garde rigide
supérieure est seulement **1 mm**. La mousse supérieure, la compression,
les arrondis de protection, le gonflement admissible du pack et les dispersions
de fabrication doivent être définis avant fabrication. Le jeu géométrique
ne démontre pas une précharge ni l'absence d'usure de l'enveloppe souple.

Pour le fast latching, la paire **Southco 91-361-52 / gâche 91-634-52** est
une candidate d'implantation : petit loquet inox réglable, avec sécurité
secondaire contre l'ouverture accidentelle. Les [données officielles Southco](https://southco.com/en_us_int/91-361-52)
et le [catalogue série 91](https://media.southco.com/media/static/Literature/91.en.pdf)
donnent une réservation fermée d'environ 58 × 24 × 17 mm et un entraxe
longitudinal réglable de 39 à 47 mm avec cette gâche. La base reste sur le
berceau et la gâche agit sur le capot rigide. Les cotes de perçage définitives,
l'orientation, le débattement du levier et l'accrochage réel restent **À valider**
sur le modèle fabricant ou un exemplaire reçu. La sécurité secondaire du
loquet ne constitue pas une seconde retenue indépendante en cas de rupture.

Le connecteur SBS demeure débranché manuellement avant l'ouverture et la
sortie du pack ; les câbles doivent être retenus hors du capot et du levier.
La variante ne démontre ni l'accès avec gants, ni la connexion en charge,
ni la durée d'échange. Elle n'est pas insérée dans l'assemblage drone actif.

Les arbres natifs et les liens externes sont **Implémentés** dans
`SA02_BerceauFixe_Candidat` (16 Ah) et `SA02_BerceauFixe_Candidat_20Ah`
(20 Ah). Chaque référence possède sa feuille de paramètres ; le capot est
piloté dans le sous-assemblage par `Parametres.AngleOuvertureCandidat`
(cellule B50, sauvegardée à 0°). Le fond et la cale sont ajourés, avec une
surface continue de protection sous le pack. Les rayons de contact,
les protections latérales et l'impossibilité d'agresser le softpack restent
à détailler avant fabrication.

Les preuves et leur périmètre sont tenus dans
`verification/construction_berceau_fixe_candidat_20261002.json`,
`integration_berceau_fixe_20261002.json` et
`controle_berceau_fixe_manifest_20261002.json` ; voir DOC-VAL §12.1.1.
Le contrôle des voisins utilise l'avionique historique du drone actif,
pas la nouvelle cible CA01/Holybro. Toute migration de cette pile impose
un nouveau contrôle d'intégration.
Les contrôles d'ouverture et de sortie ne vérifient pas la retenue sous
efforts dans toutes les directions en position fermée. La revue indépendante
confirme les liens, les paramètres, les empreintes et la cohérence des limites ;
elle ne qualifie ni la capture ni le mécanisme réel.

#### 4.1.2 Préétude de faisabilité entre plateaux — contexte historique

La demande du 2 octobre 2026 vise le logement au-dessus des bras : dessus du
plateau OEM `Part__Feature309` à Z33, dessous du dernier plateau
`Part__Feature311` à Z83. Il offre **50 mm libres**. Le plateau inférieur
mesure 160 × 160 mm ; le supérieur 128 × 120 mm. Les deux plateaux avionique
plus bas, Z0…2 et Z31…33, ne laissent que 29 mm et ne constituent pas ce logement.

Les packs 16 et 20 Ah ne rentrent pas dans les 50 mm actuels, même nus.
La préétude horizontale, grand axe X, réserve 4 mm de fond, 1 mm de plaque
isolante, 2 mm de mousse et au moins 2 mm de jeu supérieur. Ces épaisseurs
sont des hypothèses **À valider**, pas un support nouvellement conçu.

| Pack | Hauteur maximale étudiée | Hauteur libre nécessaire | Rehausse minimale calculée | Rehausse candidate arrondie |
|---|---:|---:|---:|---:|
| 6S 16 Ah | 67 mm, tolérances publiées | 76 mm | +26 mm | **+30 mm**, logement 80 mm, jeu haut 6 mm |
| 6S 20 Ah | 60 mm, tolérances d'étude non fabricant | 69 mm | +19 mm | **+20 mm**, logement 70 mm, jeu haut 3 mm |

Pour un logement commun aux deux candidats, **+30 mm** est une base de
dimensionnement à examiner. Les quatre colonnes OEM sont nominalement
`HUAZHU-LV-M3-50`, Ø extérieur 5 mm, aux axes X/Y = ±52 mm. Une rehausse
de 20/30 mm correspondrait à des colonnes nominales de 70/80 mm ; filets,
longueurs effectives, visserie, rigidité, contreventement éventuel et reprise
des efforts du plateau sont **À valider**. La présente étude ne remplace
aucune colonne et ne déplace aucun plateau dans les fichiers natifs.

Le passage entre rangées de colonnes est de 99 mm : la largeur maximale
du pack de 78 mm laisse 10,5 mm par côté avant guides et protections.
La longueur de 198 mm dépasse le plateau inférieur de 19 mm par extrémité,
et le supérieur de 35 mm ; les appuis et la capture doivent reprendre ces
porte-à-faux. Le volume actuel est occupé par P20, l'isolant, le Pixhawk et
sa sangle entre Z34 et Z81,6 : **la rehausse seule ne libère pas le logement**.
Une nouvelle implantation de l'avionique est nécessaire. La pile candidate
Holybro/CA01 possède son propre repère, sans placement drone validé ; elle
ne démontre pas que cette migration est déjà résolue.

Le capot ouvrant à 110° du §4.1.1 ne peut pas être repris sous un plateau
fixe. Une sortie longitudinale avec retenue frontale, ou un plateau supérieur
ouvrant captif pour un retrait vertical, reste **Planifié / À valider**.
La connexion SBS reste indépendante de la retenue et son accès doit être
redéfini avec le nouveau trajet du pack.

Les hélices sont absentes de la CAO OEM. À partir des axes moteurs
X/Y = ±229,90664 mm, une enveloppe hypothétique de disque Ø381 mm (15 pouces)
laisse environ **78,81 mm entre les disques** lors d'une sortie +X près
des moteurs. Un pack de largeur 78 mm n'y dispose que de 0,41 mm par côté,
hors mains, câbles et tolérances des hélices. La position statique centrale
et l'échange latéral sont donc deux problèmes distincts ; une absence
de collision avec les seules pièces CAO ne valide pas le passage réel près
des pales. Le plan d'hélice, le volume balayé, les dégagements et le scénario
d'échange doivent être vérifiés sur les références réelles.

Conclusion de préétude : rangement central envisageable après rehausse et
migration de l'avionique ; accès, fast latching, rigidité et centrage restent
**À valider**. Descendre le pack abaisse son centre propre, mais le centrage
du drone dépend également de l'avionique déplacée et de la masse des supports.
Preuve : `verification/logement_interplateaux_20261002.json` ; coupe de
principe `verification/logement_interplateaux_20261002.png` ; DOC-VAL §12.1.2.

#### 4.1.3 Cassette 20 Ah, rehausse et composants commerciaux

La préétude précédente est remplacée pour la configuration de travail par
les natifs du dock 20 Ah. Les originaux OEM et les variantes précédentes
restent inchangés. Les recettes, références, matrices et empreintes sont
dans `hardware/mecanique/cartographe/verification/` et le manifeste voisin.

| Interface | Définition d'intégration | Limite |
|---|---|---|
| logement | fond à Z33, plateau supérieur Z128…130, quatre colonnes P37 aluminium6061T6 Ø6×95 avec M3 aux extrémités ; ancien nom70 conservé | rigidité et reprise des efforts à vérifier sur pièces |
| avionique | pile Holybro/CA01 dans l’intégration locale courante ; ancienne variante P27/Pixhawk historique | montage physique de la pile commune **À valider** |
| rails | P28/P29, chanfreins d'entrée et flange captive ; jeu nominal0,5mm en dessous/dessus | usure, tolérances, poussière et efforts d'insertion à mesurer |
| cassette | fond P30 G10ép2, capture P31, deux bandes P32 G10ép2 avec vis fraisées affleurantes | pack maximal d'étude touche la capture haute ; calage du pack réel à mesurer sans comprimer le softpack |
| butée | P35 fixe et portée P36 sous fond ; réglage M4 indépendant des contacts | réglage du stage primaire et contrôle du jeu axial au banc |
| verrou | SouthcoR4-05-40-405-10 + gâcheR4-90-0521-10, montage aux cotes du plan J-R4-05-10 | tenue admissible, verrouillage et commande avec gants non qualifiés |
| contacts | TE1648151-1/1648156-1, deux positions de puissance, fixation flottante et supports P39/P40 | anomalies des cavités STEP signalées ; compatibilité et engagement à contrôler sur la paire réelle |
| chemin électrique mobile | pack retourné, fils AWG8 courts et cosses à 90° Klauke 742F5 M5 candidates sur TE ; BMS/P43/P44 au-dessus, protections locales des cosses dessous | lot, compatibilité AWG8, sertissage, isolation et échauffement **À valider** |
| coupure fixe | JETI MainSwitch100 et commande magnétique à l'étage inférieur sur P57 candidat | OFF avant déverrouillage ; mémoire ON et négatif commuté selon DOC-ELEC §6.2 |
| raccordement pack | XT90-S, adaptateurs AWG10 et P42/P45–P47 retirés ; TE/P39/P40 rapprochés encore40 mm, recul X12 mm après optimisation | ancrages préservés, bras raccourcis ; lot, préparation et rigidité **À valider** |
| faisceau fixe | entretoises Cu P48, protections P49/P50 et deux fils AWG8 vers JETI inférieur | raccords au kit JETI, section réelle, bridage et sorties à définir ; réservations CAO sans usinage du produit |
| équilibrage et reprise | coffret P51/P52 pour prise et mou dans le corridor intérieur ; anciennes retenues P41/P53 retirées | fixations des coffrets, calage, rigidité et vibration **À valider** |

La configuration courante est décrite au §4.1.3.2. L'ancienne implantation
P41/P53, les sept colliers et les épissures frontales ne définissent plus
les quantités courantes ; voir la BOM actualisée et Git pour leur historique.

Le choix s'appuie sur des produits existants : la famille SouthcoR4 est un
loquet commercial automatique pour fermeture par poussée ; la famille TE
ELCON Drawer est conçue pour accouplement guidé de tiroirs, avec appuis et
butées séparés ; la coupure/anti-étincelle JETI est un module commercial.
Ces implémentations ne constituent pas une qualification d'application UAV.
Les originaux, plans et notices sont conservés dans
`sources_fabricants/batterie20Ah_20261002/`, avec les exemples et leur provenance.

La [BOM du dock](../../hardware/mecanique/cartographe/verification/bom_dock20Ah_20261002.json)
définit les quantités pour un drone et une cassette, les MPN commerciaux,
les standards et longueurs de vis, les pièces fabriquées et leurs fichiers.
Les fixations permanentes sont posées lors de la préparation d'un pack ;
elles ne sont pas déposées à chaque échange. Une seconde cassette reprend
uniquement les lignes mobiles. Les pièces P13–P15 et le SBS sont retirés de
la configuration active, P23–P26 restant des candidats archivés.

Les contrôles antérieurs de course au DOC-VAL §12.1.3 portaient sur leur
géométrie nominale et leur enveloppe de pack d'étude. Le contrôle courant
au §12.1.8 porte uniquement sur le pack nominal de 193 × 76 × 58 mm ;
l'enveloppe de 198 × 78 × 60 mm et le lot réel restent **À valider**.
Les supports du loquet ont été repris après détection d'un
accrochage, les fixations de rails déportées hors flange et les vis supérieures
rendues affleurantes pour traverser sous le plateau pendant toute l'extraction.
La preuve d'intégration distingue le balayage continu, les poses échantillonnées,
les volumes fonctionnels des composants achetés et les modèles simplifiés.
Voir DOC-VAL§12.1.3 : aucune absence de blocage physique ni qualification du
verrouillage n'est déduite d'une simple ouverture du fichier.

##### 4.1.3.1 Couleurs et compacité du dock — 4 octobre 2026

Le fichier courant reste `SA02A_Dock20Ah.FCStd`. Les noms des pièces et
assemblages sont conservés lors des évolutions ; aucun nouveau suffixe de
révision n'est ajouté. Les 91 petits natifs du dock et de ses dépendances
(2,31 Mo avant édition) sont suivis explicitement par Git. L'état initial est
conservé sur `codex/batterie-avant-evolution-20261004`, sans changement de la
branche de travail ni de l'index utilisateur. Les sources fabricant et
exports lourds restent exclus.

Les matériaux de présentation persistants distinguent pack bleu, rails
bleu-vert, isolants ocre, retenue orange, cuivre, JETI violet et câbles rouge/noir.
Ces couleurs ne définissent pas les matériaux physiques ni une qualification.
Les références natives et les 181 occurrences conservent leurs arbres et
placements. Les deux cordons fixes gardent `Chemin`, `Section` et `Part::Sweep`.

Le premier compactage **Implémenté** replie les grandes boucles arrière
avec des demi-tours inclinés et raccords en S de rayon50mm. Départs, arrivées,
tangentes, pack, fixations et protections sont conservés. L'enveloppe
conservatrice FreeCAD passe de548,64×135,84×212,89mm à543,84×135,84×150,57mm :
hauteur−29,3%, volume de boîte−29,9%, longueur−0,9%. Ce volume de boîte
n'est ni un volume de matière ni une réduction équivalente de masse.
La longueur480,91/425,75mm ne démontre ni la distance spatiale152,4mm
au premier collier ni la liberté réelle de la fixation flottanteTE. Résultats et limites dans
[DOC-VAL§12.1.7](../VALIDATION_QUALIFICATION.md#1217-couleurs-et-compacité-du-dock--4-octobre-2026).
L'intersection préexistante positif/P49, environ 84,525 mm³, restait ouverte
lors de cette première étape ; elle est traitée par le nouveau trajet au §4.1.3.2.

| Solution explorée lors de la première étape historique | Effet et décision à cette étape | Suite nécessaire à cette étape |
|---|---|---|
| Replier les deux boucles fixes | gain de hauteur calculé29,3%, appliqué en place | liberté flottante, courbures, retenue, vibration et thermique au banc |
| Rapprocher/repositionner JETI et ses raccords | potentiel sur la longueur arrière, **Planifié / À valider**, non chiffré | relever les sorties du kit et reprendre support, reprise de traction et routes |
| Repositionner le XT90 frontal et P47 | équipement jusqu'àX209,85 contreX99 pour le pack maximal ; potentiel de raccourcissement, **À valider** | conserver les150mm de fils du pack, ranger le mou, vérifier accès et maintien |
| Retoucher la cassette | fond202×90 pour pack nominal193×76 et étude198×78 : gain limité | maintenir jeux, gonflement et captures sans comprimer le softpack |

Cette première étape est historique ; l'orientation du pack et son
raccordement sont maintenant repris au§4.1.3.2. La capacité et le mécanisme
de coupure sont conservés ; le compactage physique reste **À valider**.

##### 4.1.3.2 Énergie à l'étage inférieur et pack directement au TE — étape historique du 4 octobre 2026

Cette étape sans BMS conserve les résultats et cotes alors obtenus. Ses
coffrets, reculs TE et longueurs de fils sont historiques ; l’implantation
courante est décrite au §4.1.3.3. Le placement de JETI/PM08/PDB à l’étage
inférieur et le raccordement direct au TE sont conservés.

Choix utilisateur **Implémenté en CAO**, physique **À valider** : JETI,
commande magnétique, PM08-CAN et PDB 18138 sont placés dans SA07 sous la
batterie, autour de la pile centrale. Le plateau P57 candidat comporte trois
îlots étagés, appuis, butées, lumières et attaches sur deux axes OEM ; vis,
sangles, maintien vertical/axial, dissipation et procédure restent à définir.
Les modules débordent latéralement de l'empreinte du pack. Une implantation
centrale entre les plateaux a été écartée pour collisions et manque de place
aux prises. Les sources fabricant ne sont pas usinées.

Le pack est tourné de 180° autour de Z. Le TE et les panneaux P39/P40 reculent
de 82 mm ;
leurs bras sont allongés vers les ancrages existants. Cette concession donne
la place aux deux fils AWG8 directs et aux cosses à 90° candidates Klauke
742F5 M5. Le XT90-S frontal, les deux adaptateurs AWG10, les longues barres
P42 et leurs protections longitudinales sont retirés. Les chemins mobiles
mesurent 89,70/90,56 mm, avec des arcs de rayon 50 mm. La 742F5 a une section
nominale de 10 mm² : sa compatibilité exacte AWG8, son sertissage et la géométrie du
coude ne sont pas confirmés. Sa représentation est une enveloppe d'étude
**À valider** ; la définition directe AWG8/742F5 M5 n'est pas qualifiée.
Les sorties du lot pack ne sont pas cotées ; aucun travail sur les cellules scellées.

Le contrôle CAO courant porte uniquement sur le pack nominal de
193 × 76 × 58 mm. L'enveloppe d'étude de 198 × 78 × 60 mm, sans tolérance
fabricant publiée, et le lot réel restent **À valider**.

P43/P44 deviennent un coffret arrière court sous Z102,5 ; le plateau commence
à Z103 (jeu nominal de 0,5 mm, tolérances **À valider**). P51/P52 et la boucle
d'équilibrage sont dans le corridor intérieur, pour éviter les colonnes Y±52
pendant l'extraction. Des passages sont ajoutés à P31 ; les fixations des
coffrets, protections contre le frottement et la résistance des bras en
porte-à-faux de 82 mm restent **À valider**. Les anciennes vis de retenue
de l'équilibrage ne sont plus posées.

Les deux fils fixes descendent vers JETI, avec des arcs de rayon 50 mm et des
longueurs de 354,42/354,07 mm. Leur dressage et les sorties du kit doivent
être approuvés avant fabrication ; la distance
TE de 152,4 mm concerne le premier collier si utilisé, pas la longueur bouclée.
Le rayon nominal de 50 mm ne démontre pas une conformité globale au dressage
et au flottement TE. Les faisceaux JETI → PM08-CAN → PDB restent à recoter,
ainsi que les prises accouplées. PM08-CAN est la sélection courante ; PM08D
désigne une autre famille de module, sans substitution.

La charge hors drone nécessite un adaptateur de puissance TE protégé,
**Planifié**. La prise JST d'équilibrage seule ne remplace pas la liaison
de puissance de charge ; la charge ne passe pas par JETI OUT.

Natifs conservés en place : SA02A, SA02Cassette, SA02Contacts, SA07 et
Integration_Stack_Revue_20261003. Point Git avant migration :
`codex/batterie-avant-etage-inferieur`. Manifeste et BOM courants renvoient
au contrôle et à la nomenclature dans `verification/` ; les preuves antérieures
et leurs empreintes sont historiques. Mesures et limites : DOC-VAL §12.1.8.
L'état courant est sauvegardé sur `codex/batterie-etage-inferieur` ; les
branches de conception et les fichiers natifs conservent la possibilité
de revenir à la définition précédente sans renommer les assemblages.

##### 4.1.3.3 BMS au-dessus du pack et raccordement TE compact — 5 octobre 2026

`ELEC-BMS-001` / `SAFE-REQ-011` : le **JBD-SP22S003 Li-ion A01 100 A**
reste solidaire de la cassette, **au-dessus de la batterie**. CAO
**Implémentée** ; modèle équipé, retenue, courant et qualification physique
**À valider**. Le TE Middle Drawer1648156-1/1648151-1 et ses cinq fonctions
signal sont conservés (DOC-ELEC§6.2). Les supports doivent reprendre les
efforts d’accouplement sans charger les cellules ni le PCB ; cette règle
reste à vérifier par calcul et essai de retenue/rigidité.

Le volume entre pack et TE est réduit en rapprochant le connecteur, en
réorientant la cosse négative et en supprimant la grande chambre de fils.
Le PCB maximal documenté **130,5×65,5×12 mm** reste à
**X±65,25, Y±32,75, Z107…119 mm**. Les ports sont des réservations hors PCB,
pas des positions cotées fabricant ; prises, dissipateur, maintien et
sorties du lot restent à définir. Les mêmes fichiers évoluent en place :

- **P58** reste l’appui isolant de1 mm à Z106…107. **P43** conserve le coffret
  supérieur de170×76 mm à Z104…123 ; **P44** le ferme à Z123…125.
  La chambre inférieure78×46×42 mm est supprimée au profit de protections
  locales autour des deux cosses, avec parois2 mm et jeu d’étude0,5 mm.
  Leur attache au coffret, retenue, accessibilité et protection au toucher
  restent **À valider**.
- **P49**, protection fixe du TE, est reprise pour relier ses brides au corps
  principal : l’ancien jeu4 mm séparait ces éléments. Les liaisons sont
  élargies/épaissies pour obtenir une protection monobloc sans augmenter le
  sommetZ121 mm. La relecture indépendante confirme un solide BOP sain et
  24 interfaces sans collision ; cette continuité géométrique ne qualifie
  pas la rigidité, les efforts ou la vibration.
- **P37** garde sa longueur95 mm et son nom historique
  `P37_Entretoise70_6061_M3.FCStd`. Plateau et fixations restent rehaussés
  de25 mm, à Z128…130. Les jeux d’étude de3 mm au capot et4 mm au fond
  n’acceptent pas les tolérances, flexions, vibrations ou la thermique.
- Par rapport à l’état supérieur enregistré dans Git `1ccbad81`, le TE
  avance de **40 mm sur X**, avec décalage **Y−6,1535/Z+12,255 mm**.
  Son recul sur X depuis l’implantation frontale historique passe de52 à12 mm.
  P39/P40 conservent leurs ancrages et leurs bras sont raccourcis.
  Orientations des douilles, contacts, rondelles et vis sont rétablies et
  préservées ; la cosse négative tourne de−90° autour de X. Axes et entrées
  sont cohérents dans la représentation, sans qualification de l’accouplement
  ou de la fixation flottante TE.

Les détours polygonaux sont remplacés par des routes courbes, sauf le
positif axial direct. Mesures des natifs recalculés dans
[la preuve de raccordement compact](../../hardware/mecanique/cartographe/verification/compactage_raccord_bms_te.json) :

| Route mobile | Avant `1ccbad81` (mm) | Courante (mm) | Rayon de la représentation |
|---|---:|---:|---|
| Pack B+ → TE39 | 59,6998 | 17,2548 | segment axial droit |
| Pack B− brut → BMS | 94,5410 | 77,6861 | R16,7705 |
| BMS C−/P− protégé → TE40 | 105,1497 | 49,3353 | arc unique R51,9802 |
| Équilibrage interne | 74,8244 | 52,9941 | R12,4122 |
| UART BMS → signaux TE | 191,0000 | 83,6733 | R10,1535 et deux R8 |

Les deux cordons fixes vers JETI mesurent305,7557/325,2341 mm, avec trois
arcsR50 chacun. Ils partent de(−191,9, −11,4, Z82/98,51) et rejoignent les
réservations JETI(−40, −115/−99, −16,5) ; prises et dressage du lot non qualifiés.

Les diamètres réservés sont5 mm pour AWG8,3,5 mm pour l’équilibrage et2,8 mm
pour l’UART. Diamètres réels, rayons minimaux du lot, tangentes aux ports,
reprises de traction et frottement restent **À valider**. Une ligne positive
courte ne prouve pas le dressage ni la liberté flottante TE. Le solde
arithmétique de **132,7452 mm** sur les150 mm OEM n’est pas une longueur de
coupe : insertion réelle dans le fût, coupe/sertissage ou stockage du
surplus sont à accepter. La cosse candidate Klauke742F5 M5/10 mm² conserve
ses réserves de compatibilité AWG8, de coude et d’outillage.

B+ va directement au TE sans XT90-S ni borne B+ de puissance ajoutée au BMS.
BC22=B6 du faisceau cellules alimente/mesure la carte ; B− brut rejoint le
BMS puis C−/P− protégé rejoint TE40. JETI/PM08/PDB gardent l’étage inférieur
et deviennent des pièces directement liées au principal, avec P57, la commande
magnétique et l’isolateur fixe. Aucun déplacement n’est demandé par ce changement
de parentage.
P51/P52, XT90-S et barresP42 restent retirés. Aucun pont de masse ne doit
contourner BMS ou JETI. L’isolateur fixe Waveshare15817 reste une
réservation90×80×26 mm ; les contacts #20 et cavités restent provisoires.

Comparaison du dernier compactage depuis `1ccbad81` : **143 sources natives
identiques aux fichiers Git et quatre sources OEM lourdes figées localement
par SHA**, sans reconstruction paramétrique de cette référence. Utiliser
`bbox_apres_verification_mm` de la preuve, issu du recalcul frais ; le cache
auteur immédiatement enregistré donnait une borne X légèrement différente.

| Périmètre identique avant/après | Dimensions avant L×l×H (mm) | Dimensions courantes (mm) | Variation du volume englobant |
|---|---|---|---|
| Batterie et étage énergie | 399×210,5×181 | 388×210,5×181 | −2,757 % |
| Cassette mobile seule | 346,337×108,5×91 | 295,900×113,6535×91 | −10,505 % |
| Intégration locale, propulsion comprise | 538,596×511,015×501,529 | 538,596×511,015×501,529 | 0 % |

La cassette gagne **50,4369 mm sur X** et s’élargit de **5,1535 mm sur Y**.
Ce résultat inclut la correction d’orientation des douilles ; il ne mesure
pas seulement la translation du TE.
L’ensemble énergie gagne11 mm sur X ; l’isolateur fixe borne désormais son
extrémité X−235. Les bras limitent l’enveloppe d’intégration locale, qui
reste inchangée : avancer le TE de40 mm ne donne pas40 mm de gain global.
Ces volumes englobants ne mesurent ni la matière ni la masse et ne qualifient
pas un drone de mission complet équipé.

L’implantation arrière Git `94d04d0` et la première implantation supérieure
Git `1ccbad81` sont historiques. Le comparatif arrière utilisait145 sources
exactes et deux reconstructions isolées P37=70/rehausse=20 ; il ne décrit
pas la référence du dernier compactage. Les noms restent stables pour les
retours arrière par Git.

Les résultats géométriques ci-dessous précèdent le découpage batterie/récepteur ;
leur transfert aux nouveaux parents est démontré par identité des sources de
pièces et des placements mondiaux (§4.1.3.4), sans nouveaux booléens de collision. Le [contrôle BMS du compactage](../../hardware/mecanique/cartographe/verification/controle_bms_cassette.json)
en processus neuf confirme147 sources, aucune erreur de recalcul ou lien
rompu, axes/entrées cohérents, cinq routes valides au contrôle BOP et aucune
collision non classée. Les huit poses d’extraction0/10/25/50/100/200/350/500 mm
sont libres ; seul le recouvrement86,5901 mm³ de l’entrée du câble dans la
réservation JST est intentionnel. Cela ne prouve ni course continue ni
accouplement du lot.

SA08 évolue sur `Integration_Stack_Revue_20261003.FCStd` ; son départ fixe
TE à cinq signaux est recalé vers **(−195, −26,1535, 90,255) mm**.
Le [contrôle complet des37 routes](../../hardware/mecanique/cartographe/verification/controle_routes_systeme_courant.json)
est réussi en mode «natifs enregistrés», sans collision et avec sources
externes stables. La relecture finale en processus neuf confirme37 routes
BOP saines,109 sources obstacles et38 fichiers de faisceau aux empreintes
courantes, et identité géométrique natif/candidat : différence symétrique
maximale0 mm³, seuil1e−5 mm³. Elle réutilise le contrôle de collision des
candidats et ne recalcule pas les booléens contre les obstacles. Aucune
réserve géométrique non classée ne reste ouverte dans le périmètre nominal
contrôlé. Les registres sont actualisés :182 occurrences,115 références et
629 placements dans le manifeste. Les deux rendus finaux sont relus, sans
modification des147 sources ; P49 monobloc et suppression de la chambre
sont visibles. La dernière mise en concordance des registres et du schéma
électrique doit être vérifiée après gel documentaire ; les résultats et
empreintes sont consignés dans les preuves courantes, sans qualification
matérielle implicite.
Les réussites antérieures ne certifient pas cette configuration. GNSS et
plusieurs équipements de mission restent candidats. Validation : DOC-VAL§12.1.9.

##### 4.1.3.4 Batterie, récepteur et équipements directs — 5 octobre 2026

La hiérarchie adoptée sépare les fonctions d’échange : les67 pièces mobiles
sont dans `SA02_Cassette20Ah_Coulissante`, label «Batterie 20 Ah», et les72
pièces fixes dans `SA02A_Dock20Ah`, label «Récepteur de batterie 20 Ah».
Les noms de fichiers restent stables. Le pack, le BMS, le coffret et les
raccords TE mobiles sortent ensemble ; le récepteur demeure dans le drone.
L’extraction doit être appliquée une seule fois aux67 pièces mobiles.

L’assemblage principal contient12 liens directs : six sous-assemblages et
six pièces, PM08-CAN, PDB18138, plateauP57, JETI, commande magnétique et
isolateurUART. `SA07_Distribution_Systeme_Candidat.FCStd` est conservé comme
montage historique non installé. Cela rend le montage principal lisible
sans dupliquer ces équipements ni conserver un dock monolithique.

La migration est **Implémentée** en CAO et sa réouverture est réussie :
aucun objet Invalid ni lien manquant. Le multiensemble des149 éléments
affectés conserve ses références et poses mondiales (139 anciens éléments
du dock, six équipements et quatre liens principaux traités comme blocs).
Les apparences complètes sont identiques. Les sources des pièces et du
faisceau restent inchangées ; seules la batterie, le récepteur et le
principal ont été sauvegardés pour leur nouveau parentage. L’enveloppe
du principal est identique avant/après dans le périmètre de cette preuve. Les mesures du compactage au §4.1.3.3 ne constituent pas un
nouveau gain de volume dû au rangement. La preuve dédiée est
`verification/decoupage_sous_assemblages_batterie.json` : parentage67/72,
principal6+6, absence de doublon, liens résolus et identité géométrique après
réouverture. Les contrôles frais et l’extraction sont dans
`verification/controle_hierarchie_batterie.json`, la concordance des registres
et de la BOM dans `verification/hierarchie_batterie_recepteur.json`, et les
vues dans `verification/rendu_hierarchie_batterie.json`. Les translations
0/50/500 mm déplacent uniquement les67 mobiles, une fois, et maintiennent
72 éléments du récepteur, six équipements et37 routes fixes. Le contrôle
ne sauvegarde aucun natif. Les registres publiés confirment182 occurrences
et115 références sur le périmètre batterie/récepteur/énergie/SA08, sans
double installation ; ces nombres ne décomptent pas tout le drone.
Les contrôles de collision antérieurs sont transférés par identité des
sources et poses, sans nouveaux booléens. La recette et les registres évoluent en place ;
les anciennes recettes monolithiques doivent refuser ce parentage avant
toute mutation. Maintenance : README cartographe ; protocole : DOC-VAL§12.1.10.

### 4.2 Isolation du bloc capteurs

La caméra et le LiDAR restent solidaires sur `SA05A_Bloc_capteurs` afin de
préserver leur calibration extrinsèque. Quatre appuis Sorbothane isolent ce bloc
du châssis et des moteurs. Des pièces métalliques captives limitent le débattement
en cas de choc ou rupture. Les câbles doivent former une boucle souple et ne pas
court-circuiter l'isolation.

Le [guide fabricant Airy v1.3, pages PDF 20–21](../../hardware/electronique/cartographe/sources_fabricants/RoboSense_Airy_User_Guide_v1.3_20251105.pdf)
demande trois vis M3×8 avec dispositif anti-desserrage (dépassement
4,5 mm), une surface d'appui de planéité meilleure que 0,15 mm, deux piges
de positionnement Ø3 (dépassement 3 mm) et plus de 2 cm de mou au câble. Il recommande un support métallique rigide assurant
la dissipation par contact avec la base ou le dessus du LiDAR ; la fréquence
du premier mode de l'ensemble LiDAR-support doit dépasser 50 Hz. La platine
P16 actuelle, prototype imprimé, ne démontre ni le chemin thermique ni ces
tolérances et modes. Reprendre son interface Airy puis vérifier planéité,
fixation, conduction thermique, vibrations et dégagement du câble sur
l'assemblage réel : **À valider**.

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
L'intégration au drone reste **Planifiée**. Une variante native CA01/Holybro
est **Implémentée** au §4.4.1 ; la configuration active du drone conserve
l'assemblage du 16 septembre.

La carte commune **CA01** regroupe dans la cible la radio RP4TD, ses conversions
locales 5 V et les adaptations de synchronisation, hors porteuse. Le
**PM08-CAN** reste fixé au châssis près de la distribution, sur un support
séparé de CA01 et de la cassette batterie. Il reste sur le drone pendant
l'échange de pack. La PDB Holybro 300A Top Entry, SKU 18138, est une
**candidate** pour la distribution fixe en aval du PM08-CAN : batterie →
PM08-CAN → PDB → départs ESC et CA01. Le BEC1 dessert POWER1 et le BEC2
POWER2 du Pixhawk ;
la mesure DroneCAN rejoint CAN1 par un faisceau distinct. Les deux BEC ne
sont pas mis en parallèle. Le 5 V local protégé de CA01 est issu d'un départ
batterie aval du PM08-CAN et alimente notamment la radio, indépendamment du
Jetson. Un rail 12 V candidat dessert l'entrée XT30 de la porteuse ; le rail
LiDAR et les adaptations de synchronisation sont des circuits candidats
KiCad V0.5-pre, implémentés mais non qualifiés. Brochages,
protections, budgets et essais sont décrits dans
[DOC-ELEC §4.2](ARCHITECTURE_ELECTRIQUE_RESEAUX.md#42-cahier-des-charges-de-la-carte-avionique-commune-ca01)
et [§4.3](ARCHITECTURE_ELECTRIQUE_RESEAUX.md#43-câblage-global-du-cartographe).

Le support fixe du PM08-CAN est **Planifié** : prévoir un appui isolant
vis-à-vis du carbone, un maintien positif accessible, une décharge des efforts
sur les câbles et l'accès aux connecteurs. Réserver l'enveloppe fabricant
45 × 41 × 26 mm hors câbles et tenir compte des 185 g annoncés câbles inclus ;
ce ne sont ni l'encombrement installé ni une masse mesurée dans notre montage.
[Source Holybro PM08-CAN](https://holybro.com/collections/power-modules-pdbs/products/dronecan-pm08-power-module-14s-200a).
La [PDB candidate](https://holybro.com/products/power-distribution-board-pdb-300a-top-entry)
porte six XT90 et deux XT30 orientés vers le haut, des bornes à vis de puissance
et des trous de fixation M3. Prévoir un support isolé du carbone et un accès
aux connecteurs, aux protections des départs et aux opérations de maintenance.
Un XT30 est envisagé pour l'entrée 6S de CA01 ; son courant admissible dans
le montage, la polarité, les dégagements, le cheminement, la décharge des câbles,
l'encombrement et la masse installée sont **À valider**. La PDB ne remplace ni
le PM08-CAN en série ni les connecteurs de signaux de CA01. Aucune géométrie
PDB n'est encore intégrée à la CAO active.
Les rayons de courbure, terminaisons de puissance, dégagements de maintenance,
fixations, isolation des vis, vibrations et dissipation restent **À valider**.
Les fixations ne doivent pas contraindre le boîtier, les composants ou les
soudures ; aucun effort de cassette ne doit transiter par les câbles du PM.

Le raccordement batterie, le détrompage, la coupure et la séquence d'échange
sont définis pour le dock20Ah au§4.1.3 et dans DOC-ELEC§6.1 ; leur mise en
œuvre physique reste À valider. POWER1, POWER2, DroneCAN et les départs
d'alimentation restent sur le châssis pendant l'échange. Cinq positions signal TE candidates sont réservées à UART isolé et présence
passive (§4.1.3.3) ; aucun échange sous courant de puissance n'est prévu.

La CAO avionique est héritée de l'empilage du 16 septembre ; la variante
SA03_Avionique_Rehausse20 déplace le Pixhawk historique surP27. Ces modèles
et SA04/P03/P04/P06 ne représentent ni la porteuse
Pixhawk Jetson, ni le module Orin NX 16 Go, ni le rail XT30 et ses câbles,
ni la nouvelle implantation CA01, la PDB candidate ou le support fixe
PM08-CAN. L'enveloppe PM02D demeure historique. Les anciennes enveloppes RC et télémétrie séparées
ne représentent pas deux modules à ajouter au RP4TD. Aucune réserve de hauteur
ni absence de collision antérieure ne qualifie la nouvelle implantation.

La cible nécessite une reprise des sous-assemblages, du manifeste et du bilan
de masse après choix des révisions matérielles et des modèles fabricants. Le
contour de CA01, ses fixations, les dégagements antennes, l'isolation du carbone,
les connecteurs XT30, POWER1/POWER2 et CAN, le refroidissement et les rayons
de courbure restent **À valider**. Les circuits internes KiCad V0.5-pre
et le préplacement CA01 sont implémentés ; le 5 V local protégé et les
nouvelles interfaces restent à qualifier électriquement. Les nouvelles masses
alimenteront le modèle de simulation ; la CAO et Gazebo ne démontrent pas la
tenue thermique du module, de la porteuse ou des faisceaux.

#### 4.4.1 Préplacement CA01 et variante Holybro, 1 octobre 2026

Le contour candidat CA01 mesure **126 × 80 mm**, avec quatre trous Ø3,2 mm
aux centres (3 ; 3), (123 ; 3), (123 ; 77) et (3 ; 77) dans le repère local.
Il reprend les entraxes 120 × 74 mm de la porteuse. Le PCB natif CA01
est paramétrique : corps de 1,6 mm, quatre perçages M3 et quatre
perçages MOD401 candidats Ø0,8mm, composants importés
du STEP KiCad, dont MOD401 RP4TD 23,7 × 16,3 × 4 mm tourné de 90°.
Les 151 composants schématiques incluent désormais MOD401 ; avec quatre
fixations, le PCB contient 155 empreintes. Le contour, les fixations, connecteurs et la radio restent conservés
dans le routage complet quatre couches (DOC-ELEC§4.2.11, DOC-VAL§12.7.13).
Le placement électrique de48références a été repris le02/10 ; les associations
de modèles3D restent présentes, mais les exports FreeCAD/STEP du01/10
représentent les positions antérieures des composants déplacés. Leur mise
à jour est maintenant réalisée dans la variante de revue du §4.4.1.1 ; le
contrôle d'accès/hauteur complet reste **À valider** avant fabrication.
Les pistes, plans et vias ne sont pas détaillés dans le natif
FreeCAD ; la thermique et le montage réels restent **À valider**.

Source : STEP inchangé de la [page de téléchargement Holybro](https://docs.holybro.com/autopilot/pixhawk-baseboards/download),
`sources_fabricants/Pixhawk-Jetson-Baseboard-3D.stp`. Ses métadonnées
indiquent ORIN_NX-RC02 et un export du 19 juin 2024 ; elles ne démontrent
pas la révision commerciale reçue. Le PCB STEP mesure environ 1,992 mm
contre 1,6 mm sur le dessin : la révision et l'épaisseur restent **À valider**.

Ouvrir `sous_assemblages/SA03_CA01_Holybro_candidat.FCStd` en conservant
les pièces liées. Les deux occurrences externes sont Holybro à l'identité
et CA01 retournée de 180° autour de X, décalée à Z = −9,97 mm.
L'écart entre faces de PCB est **10 mm candidat**, piloté par une expression ;
les composants CA01 regardent vers l'extérieur inférieur. Cette variante
ne remplace pas `SA03_Avionique` dans l'assemblage actif du drone.

Les modèles3D de dix familles, soit **16 occurrences**, remplacent les
anciennes boîtes : Q101–Q104, U101, U201/U301, D503/D504, R116, F101,
J103/J104, J201/J301 et J502. Les modèles détaillés XT30-M et PH proviennent
de la bibliothèque de leur auteur ; les autres sont reconstruits depuis
les plans cotés fabricants, avec arbre natif et terminaisons représentées.
Ce sont des modèles nominaux **Implémentés / À valider**, pas des STEP OEM.
Les originaux sont conservés sans modification et les pièces dérivées
restent distinctes. Le modèle XT30-M conserve une hauteur5,0mm contre
5,2mm sur le plan ; PH5,6mm contre5,5mm. Les queues VH1,14mm carrées
ont une diagonale1,612mm dans des trous1,7mm : tolérances à vérifier.

Les modèles détaillés KiCad déjà présents, dont GH et XAL1010, sont conservés
avec copies locales. Les 21 fichiers de bibliothèque utilisés ne dépendent
plus du répertoire d'installation KiCad. Les MPN encore absents de la BOM
restent des représentations de boîtier, sans sélection électrique nouvelle.
L'[inventaire courant](../../hardware/electronique/cartographe/carte_avionique/modeles_3d.json)
porte chemins, références, provenance et hashes. Les exports courants sont
dans `exports/ca01_modeles3d_20261001/` ; les anciennes boîtes et l'export
à163solides restent historiques. Les valeurs maximales de l'enveloppe du
shunt précédente ne deviennent pas les cotes nominales du modèle actuel.

Le STEP courant comporte **308 solides composants pour141 composants
représentés**, plus le substrat. Les DNP, trous M3, points de test et jumper
ouvert n'ajoutent pas de composants physiques. Le PCB natif conserve son
arbre : une boîte additive, quatre perçages M3 et quatre perçages radio.
La réouverture en processus neuf confirme les liens externes, la concordance
STEP/natif et la conservation de `SA03_Avionique` actif.

Les shapes nominales des composants distincts n'interfèrent pas. Le volume
commun CA01/Holybro est nul, avec une distance minimale entre les formes
représentées de **1,9446mm**. Les intervalles Z des boîtes englobantes se
recouvrent désormais de0,0604mm à cause des queues traversantes : l'ancienne
preuve par intervalles disjoints ne s'applique plus. Ces contrôles ne
qualifient pas les tolérances, entretoises, retenues, fiches accouplées,
câbles, thermique ou vibrations. La TVS conserve seulement une réserve2D.
Protocole et preuves courants : DOC-VAL §12.7.9.

Le RP4TD standard **MOD401** reste la seule famille de boîte provisoire :
aucun STEP détaillé fiable trouvé, et le modèle d'une variante RP4TD-M a
été rejeté. Son enveloppe nominale23,7×16,3×4mm reste à
(16,5;20,5)mm/90°, une seule occurrence. J401/W11 et l'ancienne
réserve séparée restent supprimés. Le profil sous-face, les composants du
module, les broches et leur hauteur installée ne sont pas connus.

**Empreinte THT candidate Implémentée / À valider :** quatre trous0,8mm
sont ajoutés dans la construction native, alignés aux centres photographiques
X11,85,Y±3,9/±1,3mm des contacts dans le repère d’empreinte. Le plan coté
OEM n’est pas disponible ; cette estimation doit être mesurée sur le module.
Le profil sous-face reste à relever. Le dessous est peuplé ; aucun jeu Z
radio/CA01 n’est défini. La méthode retenue emploie quatre broches
verticales soudées dans CA01 puis aux demi-trous du récepteur, avec axes
alignés à leurs centres. Section ronde0,5mm, trou0,8mm et pad1,6mm sont candidats ; leur compatibilité
aux demi-trous et la hauteur libre restent à vérifier. La géométrie courante
ne représente pas les broches3D ni leur hauteur installée. La pose Z du corps
nominal est uniquement illustrative : elle ne prouve ni contact soudable
ni absence d’interférence sous le module. Le gap inter-PCB Holybro/CA01
de 10 mm reste l’hypothèse antérieure ; il ne fixe pas ce jeu local.
Maintien, isolation et accès BIND/U.FL/antennes restent ouverts selon
DOC-ELEC §4.2.10 ; résultats et limites DOC-VAL §12.7.8.

Traçabilité : `CARTE-010 / CARTE-012` → PCB et variante native →
`T-CA01-10 / T-CA01-12` → preuves `verification/holybro_stack_source_20261001.json`
et `verification/revue_stack_ca01_20261001.json`, recettes DOC-VAL §12.7.5/12.7.6.
État **Implémenté**, qualification **À valider** ; aucune fabrication ni
mesure physique exécutée.

##### 4.4.1.1 Reprise de la stack sur le plan Holybro, 3 octobre 2026

Le [plan coté Holybro](https://docs.holybro.com/autopilot/pixhawk-baseboards/pixhawk-jetson-baseboard/dimension-and-weight)
est la référence des interfaces : PCB126×80×1,6mm, quatre trousØ3,2,
entraxe120×74mm ; vue avec Orin : quatre fixationsM3 et appuis8mm.
L'ensemble annoncé avec refroidissement/FCU mesure38,6mm de haut.
Les deux dessins originaux sont conservés sous `sources_fabricants/Holybro_*_Dimensions.jpg`.
Le STEP fabricant déjà disponible reste inchangé ; son pied inférieur est
àZ−8,0254 et sa sous-facePCB àZ0,03, soit8,0554mm apparents. Le plan
définit les cotes nominales ; cette différence de révision/tolérance et
l'épaisseurSTEP1,99232mm restent **À valider** sur le matériel reçu.
Ne pas redimensionner globalement le STEP pour masquer ces écarts.

La première proposition de visCHC sous la plaque basse est rejetée : les
têtes et rondelles touchent les quatre P17. Les mêmes axes(±60,±37)mm
servent à la stack, à la plaque basse et aux passagesØ3,4 deP17.
La variante native `SA03_CA01_Holybro_Revue_20261003` représente donc
une **fixation commune candidate**, sans ajouter une deuxième vis d'ancrage
P17 absente de la CAO initiale. Les M2 d'isolation capteurs restent distinctes.

| Élément de la chaîne candidate | Quantité | Définition nominale représentée |
|---|---:|---|
| P55 entretoise basseG10 | 4 | longueur24mm, Ø6, passageØ3,2 ; appui plaqueZ−90 versPCBZ−66 |
| CA01 retournée, composants vers le bas | 1 | PCBZ−66..−64,4 ; placement courant02/10 ; quatre axesM3 |
| P54 appui supérieurG10 | 4 | longueur2mm, Ø5,5, passageØ3,2 ; appuiPCBZ−64,4 verspiedOEMZ−62,4 |
| VisCHCM3×65 et rondellesM3 | 4+4 | têtes sousP17, face d'appuiZ−121,674 ; pointeZ−56,674 |
| P56 plaque basse dérivée | 1, substitution | sourceOEM intacte ; quatre trousØ3 reprisØ3,2, sans fraisage du carbone |

La pose de la porteuse estZ−54,3746mm, dérivée des appuis24/2 et du pied
STEP ; le gapPCB est10,0554mm. Ces valeurs décrivent la variante calculée,
pas des cotes qualifiées de fabrication. L'engagement géométrique dans les
piedsM3 est5,726mm, avec1,274mm avant le fond représenté ; profondeur
filetée utile, longueur sous tête réelle et couple restent à confirmer.
Cette chaîne reprend aussiP17 : desserrer les vis libère ses ancrages.
L'outil axial rencontreP16 ; déposer le bloccapteursSA05A pour monter ou
entretenir la stack, puis remonter les isolateurs selon leur procédure.
Ces paramètres ne pilotent pas globalement toute la quincaillerie : pour
une autre pose ou un autre gap, reprendre la recette et recontrôler les
appuis, les longueurs de vis et l'accès ; ne pas déduire un montage complet
d'une modification isolée du gap dans le natif.

Le PCB de revue conserve son arbre natif et ajoute42perçages de pads aux
huit trous historiques, soit50. Les308solides composants proviennent du
PCB courant, avec46composants physiques déplacés depuis le préplacement.
L'exportKiCad sans cuivre extérieur représente un substrat1,46mm ; la
convention mécanique restitue1,6mm au PCB et translate les composants
de+0,14mm. Ce changement de repère est explicite dans la preuve, sans
qualification du stackup fabricant ni détail des251vias de routage.

Ouvrir `assemblages/Integration_Stack_Revue_20261003.FCStd` pour examiner
la pose avec la plaqueP56, le dock et les capteurs. Les assemblages actifs
et la maquette avec ancien faisceau restent préservés. Le manifeste et
la BOM cible référencent cette revue séparément : aucun recalage du
faisceau ni gel du drone complet n'en résulte. Vues produites directement
parFreeCAD dans `exports/stack_avionique_revue_20261003/`.

Chaîne `MEC-AVI-001 / MEC-INT-001 / CARTE-010` → variante native →
`T-STACK-REVUE-NATIF/GEOM` → DOC-VAL§12.7.14 et
`verification/controle_stack_revue_20261003.json` ; revue indépendante
`verification/revue_independante_stack_20261003.json`.
CAO **Implémenté**, conception et tenue **À valider** : compression/fluage
P17 et G10, précharge du PCB, résistance de la longue vis, serrage,
vibrations, fiches accouplées, réserves radio et refroidissement non
qualifiés. Les appuisG10 ne prouvent pas l'isolement des tiges dans le
carbone ou les trousPCB ; stratégie de masse/isolants à définir.

#### 4.4.2 Empilage historique du 16 septembre

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

#### Revue de configuration et faisceau système — 3 octobre 2026

La [nomenclature cible](../../hardware/mecanique/cartographe/configuration_cible_20261003.json)
recense 60 postes embarqués, avec quantités, références connues, masses publiées,
inclusions et données manquantes. Elle complète la BOM détaillée du dock ; elle
ne transforme pas une sélection candidate en référence qualifiée. Objectif,
SSD, accessoires de vol, antennes RF, fournitures de câblage, procédés et
supports définitifs restent **À valider**. Le kit X650 comprend déjà une
avionique, une PDB XT60/XT30, des moteurs, ESC, LED et câbles : les retraits
doivent être individualisés avant d'ajouter la cible, sans crédit de masse
inventé. Les quatre départs XT90 de la PDB candidate exigent des adaptateurs
vers les XT30 des ESC OEM.

Une nouvelle maquette de revue **Implémenté**, inactive et **À valider**, est
disponible dans
`hardware/mecanique/cartographe/assemblages/Drone_Cartographe_Systeme_Candidat.FCStd`.
Elle conserve les liens vers châssis, dock et capteurs ; elle remplace dans
cette seule variante l'avionique/calcul/RTK historiques par la pile
Holybro/CA01, la distribution PM08/PDB et une enveloppe RTK Helical.
La pile est translatée de `(-63, -40, -65) mm` ; PM08 et GNSS sont des
primitives nominales, la PDB provient d'un STEP fabricant inchangé.
Après les interférences de l'itération initiale, le PM08 est placé en
`(-138, -82, -28) mm` et l'enveloppe de la PDB occupe
`X = 90..150`, `Y = -135..-55`, `Z = -52..-29 mm` (étage courant).
Cette implantation n'est pas un montage fixé : les supports, isolants,
prises accouplées et accès de maintenance restent à concevoir.

Le sous-assemblage `SA08_Faisceau_Systeme_Candidat` contient désormais
37 références de cordons à chemins arrondis et balayages natifs, pilotées
par la [recette](../../hardware/mecanique/cartographe/verification/routes_systeme_candidat_20261003.json).
Le faisceau recoté est lié à l'intégration locale courante avec BMS/TE.
Les sorties sont des passages réservés, pas des prises accouplées de lot.
Trois groupes restent non routés : refroidissement, accessoires de vol et LED.

Le contrôle courant est [la relecture native BMS](../../hardware/mecanique/cartographe/verification/controle_faisceau_natif_bms.json).
Les37 routes sont recalées après le dernier rapprochement du TE. Le contrôle
complet et la relecture finale sont réussis, sans collision ni différence
géométrique natif/candidat. La méthode contrôle les candidats contre les
obstacles puis les empreintes,
la validité BOP et l’identité des volumes natifs avec ces candidats ; les
booléens contre les obstacles ne sont pas répétés dans cette relecture.
Rayons, contacts, retenues, repli des bras, mouvement du bloc
isolé et course continue restent **À valider**.
Le contrôle du3octobre et ses 32 cordons avec recouvrements est historique ;
ses anciennes empreintes ne certifient pas les routes actuelles.
Aucune qualification matérielle ni bilan de centrage n'est déduit.

| Point | Traitement réalisé / décision de travail | Donnée ou validation nécessaire pour clôturer |
|---|---|---|
| contacts capteurs | géométrie corrigée, huit poses contrôlées et bilan statique mis à jour | interface Airy selon guide v1.3 : planéité, vis/piges, chemin thermique et premier mode >50 Hz ; câbles, rotations, essai vibratoire et calibration |
| fixation avionique | ancienne CAO P06, P20–P22 et retenues créées sur trous OEM | nouveau support de porteuse, matériau/procédé, tolérances, freinage, accès et essais de retenue |
| Jetson / P04 | deux collisions de l'ancienne maquette Orin Nano restent ouvertes | modèle exact porteuse/Orin NX, nouvelle fixation et contrôle d'interférence avant fabrication |
| loquet batterie | SouthcoR4-05-40-405-10 + gâcheR4-90-0521-10, indépendant des contacts | stage primaire, efforts, commande avec gants, protection contre ouverture accidentelle et cycles |
| batterie et cassette | TattuNMC6S20Ah TAA200006S5X9S et cassette interplateaux | réception du pack, tolérances, gonflement, calage, isolation et masse réelle |
| TE / faisceau du dock 20 Ah | liaison directe candidate AWG8/742F5 M5 vers contacts Middle Drawer ; JETI à l'étage inférieur ; XT90-S/AWG10/P42 retirés | engagement réel, compatibilité et sertissage, liberté flottante, courbure, traction, précharge et échauffement (DOC-ELEC §6.1) |
| RTK / antenne | supports P07–P09 et enveloppes Rover patch historiques conservés | candidat Helical STM32G4 : support/antenne et SMA éventuel, câbles CAN + UART2 de temps, ciel dégagé, carbone/propulsion, masse et repères à vérifier |
| caméra / optique | Basler conservée ; translation Airy traçable | objectif réel, champ de vue, masques, longueur des vis et extrinsèques |
| distribution / convertisseurs / radios | cible CA01 avec RP4TD et 5 V local ; PM08-CAN et PDB 300A Top Entry candidate directement liés au principal, sur P57 candidat | fixations et isolation, accès XT90/XT30 de la PDB, protection W08 au plus près du port, retenue des départs, contour/fixations CA01, encombrement, vibrations et thermique (DOC-ELEC §4.2 et §6.1) |
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

La variante de berceau fixe utilise les références ci-dessous. Leurs quantités
sont celles de la variante ; leur quantité dans le drone actif reste **zéro**.

| Référence candidate | Quantité dans la variante | Rôle | État |
|---|---:|---|---|
| `P23_BerceauFixe_Candidat` | 1 | logement ajouré, butées et ancrages OEM candidats | CAO **Implémenté** ; matériau/fixations/tenue **À valider** |
| `P24_ProtectionG10_Candidat` | 1 | plaque continue inférieure de 1 mm | CAO **Implémenté** ; G10 et isolation **À valider** |
| `P25_CapotCaptif_Candidat` | 1 | capture supérieure articulée | CAO **Implémenté** ; axe/capture/verrouillage **À valider** |
| `P26_Cale20Ah_Candidat` | 1 uniquement en 20 Ah | compensation de hauteur de 7 mm, réseau et peau continue | CAO **Implémenté** ; appui/protection **À valider** |

Les enveloppes natives des packs 16/20 Ah, de la mousse basse, de l'axe et du
loquet sont des réservations commerciales **À valider**, pas des modèles OEM.
La visserie, la gâche fonctionnelle et la capture axiale définitives ne sont
pas définies par ces réservations.

La table précédente conserve les références historiques. La configuration
20 Ah et l'étage énergie emploient les références P27–P58 selon les quantités effectives de la
[BOM du dock](../../hardware/mecanique/cartographe/verification/bom_dock20Ah_20261002.json).
P37 est répété quatre fois et P32 deux fois ; P42 et P45–P47 sont retirés.
P57 est le plateau énergie candidat. P38 dérive le plateau 309
du kit sans achat d'un second kit. Les vis OEM réutilisées, les vis remplacées
et les vis ajoutées sont distinguées par les recettes et la BOM.

### 5.2 Équipements et fournitures à impact mécanique

| Réf./famille | Qté | Rôle | État |
|---|---:|---|---|
| châssis X650 V2 et propulsion associée | 1 | structure et portance | candidat **À valider** |
| batterie TattuNMC6S20Ah TAA200006S5X9S | 1 par cassette | énergie et masse principale amovible | choix d'intégration ; énergie réelle et profil électrique **À valider** |
| TE ELCON 1648151-1/1648156-1 et contacts M5 1766283-1/6648335-1 | 1 paire, 2 contacts par côté | connexion guidée du dock | références existantes ; engagement et courant **À valider** |
| Southco R4-05-40-405-10 et R4-90-0521-10 | 1 loquet + 1 gâche | verrouillage positif automatique | choix implémenté ; essais **À valider** |
| JETI J-MSW-100-MS, commande et plateau P57 candidat | 1 jeu fixe | coupure avant échange, à l'étage inférieur | CAO **Implémenté** ; fixations, séquence et charge réelle **À valider** |
| EPDM RS PRO 205-513, découpes et cales de pack | selon hauteur mesurée | protection et calage permanent | EPDM dense70ShA, pas mousse compressible ; ne pas forcer le softpack |
| Sorbothane 30 duro | 4 appuis | isolation du bloc capteurs | géométrie finale **À valider** |
| vis M2, écrous frein et capture métallique | 4 jeux visés | limitation sûre du débattement | dimensionnement **À valider** |
| Airy, Basler et objectif | 1 chacun | bloc optique/LiDAR calibré | équipements candidats/présélectionnés |
| porteuse Holybro Pixhawk Jetson, Pixhawk 6X module seul et Orin NX 16 Go | 1 chacun | ensemble calcul/vol de la nouvelle cible | représentation groupée **Implémenté** dans la maquette inactive ; fixation et thermique **À valider** |
| H-RTK F9P DroneCAN Helical STM32G4 et antenne candidats | 1 module embarqué | navigation RTK et PPS ; interface de fixation | enveloppe nominale **Implémenté** dans la maquette inactive ; référence, interfaces, masse et montage **À valider** |
| PM08-CAN et plateau P57 candidat | 1 par drone | distribution mesurée et deux BEC, à l'étage inférieur, directement dans le principal | enveloppe 45 × 41 × 26 mm hors câbles **Implémenté** ; 185 g avec câbles ; fixations et faisceaux **À valider** ; PM08D distinct |
| PDB Holybro 300A Top Entry, SKU 18138, et plateau P57 candidat | 1 candidate par drone | distribution en aval du PM08-CAN ; six XT90 et deux XT30 orientés vers le haut, fixation M3 | STEP fabricant directement lié au principal, CAO **Implémenté** ; fixations, masse, isolation, accès et faisceaux **À valider** |
| H-RTK F9P Base, HANT-X627A, mât/trépied, boîtier et poste QGC | 1 jeu sol | référence RTK et opérateur | sélection cible **Planifiée** ; assise, repère et câbles **À valider** |

Les références électriques détaillées sont tenues dans `DOC-ELEC`. Les
références et occurrences CAO exactes restent dans
`hardware/mecanique/cartographe/manifest.json`.

## 6. Budgets mécaniques

Le bilan historique estime le cartographe avec batterie candidate entre 4,7 et
5,3 kg. Cette plage provient de volumes CAO et provisions, pas d'une pesée ; elle
reste **À valider**. La cassette rapide ajoute de la matière et doit être
réintégrée au bilan après définition du loquet et du faisceau. Ce bilan historique
n'intègre ni le remplacement par PM08-CAN, ni la PDB candidate, ni la
porteuse commune avec Orin NX.
Réconcilier le contenu du kit, retirer les anciens modules et supports devenus
inutiles, puis compter le PM08-CAN, la PDB, la porteuse, l'Orin NX, leurs
supports, refroidissement et faisceaux réels sans double comptage des câbles inclus.
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

La reprise de berceau fixe du §4.1.1 conserve environ **96,084 cm³** de cadre
P23, **17,488 cm³** de capot P25 et **17,136 cm³** de protection P24.
La 20 Ah ajoute une cale P26 de **51,564 cm³**. À la même densité hypothétique
de 1,25 g/cm³ pour P23/P25/P26, ces seules pièces représentent environ
**142 g en 16 Ah** et **206 g en 20 Ah**. La plaque G10, les mousses,
le loquet et sa gâche, l'axe, les fixations, P15/SBS et le faisceau sont exclus
de ces chiffres : ils ne constituent pas une masse installée ni une économie
de masse démontrée. Les estimations d'autonomie du §6.3 restent rattachées
à la configuration mécanique précédente ; aucun gain n'est attribué à cette
variante avant fermeture du bilan complet.

#### Budget du dock20Ah — intégration du 2–3 octobre 2026

Le [bilan partiel de la BOM](../../hardware/mecanique/cartographe/verification/bom_dock20Ah_20261002.json)
remplace P13–P15/P20 et les quatre colonnes50mm, ajoute les nouveaux supports,
captures, visserie, protections, conducteurs et moduleJETI. Les matériaux
et densités de calcul sont des hypothèses de fabrication, sans pesée.
Une provision séparée pour les logements/contacts TE porte déjà la borne
haute historique au-dessus des **6,3kg annoncés pour le X650**, avant fermeture
de toutes les masses de faisceaux, cales et loquet. Il n'existe donc aucune
marge de masse démontrée pour le drone complet. La variante Holybro/CA01
cible et le contenu réel du kit doivent également être réconciliés.

Le sous-total final est **5,888–6,502kg** ; avec les provisions TE, EPDM de
fond et masses publiées des cosses/épissures, il devient **6,112–6,726kg**.
Ces intervalles héritent des hypothèses historiques et ne sont pas des
bornes garanties. Ils excluent encore plusieurs masses, ainsi que la
propagation des±20g du pack ; aucune compatibilité en vol n'est démontrée.

La BOM détaille ce qui est calculé, publié et noncompté ; aucune masse manquante
n'est assimilée à zéro. Avant un vol, peser le drone complet, mesurer le
centrage, confronter la propulsion au chargement et adapter la structure ou
alléger les composants si la limite applicable est dépassée. Les anciennes
estimations20Ah de§6.3 ne décrivent pas cette nouvelle configuration.

Le [complément de masse du 3 octobre](../../hardware/mecanique/cartographe/verification/bilan_masse_systeme_candidat_20261003.json)
identifie **83,35 g de cuivre nominal** pour les quatre fils ajoutés déjà
routés dans le dock, hors isolants, étamage, fiches et terminaisons. Leur
addition au budget historique porte ce sous-total à environ
**6,195–6,809 kg**. Ce résultat reste partiel et historique : ce n'est ni
la masse complète du faisceau, ni celle de la nouvelle cible, ni une borne
garantie. La tolérance du pack, les matériaux réels et la réconciliation des
ensembles restent ouverts. Les réservations système comportent des fils
livrés dans les ensembles PM08/JETI/kit : leur cuivre ne doit pas être ajouté
une seconde fois. La masse complète de la cible reste inconnue ; aucune
marge sous les 6,3 kg commerciaux du X650 n'est démontrée.

#### Scénario GNSS sur plateaux et antennes radio déportées — 4 octobre 2026

Option **Planifié / À valider**, sans modification de placement FreeCAD :
retirer le bras OEM côté GPS (+Y, objets146–156), placer l'antenne Helical
au-dessus de la batterie et son récepteur sur le plateau inférieur. Le bras
opposé (−Y, objets157–167) est supposé conservé pour les deux antennes RP4TD ;
cette interprétation du « plateau déporté » reste à confirmer. Aucun crédit
de masse n'est attribué au bras conservé. Le raccord SMA déjà représenté sur
ce bras ne démontre pas une interface compatible avec les deux antennes U.FL.

La [preuve de calcul conditionnel](../../hardware/mecanique/cartographe/verification/scenario_gnss_plateaux_20261004.json)
réutilise les volumes vérifiés et contrôle les empreintes des sources.
Le bras retiré représente **41,1 g provisionnels** avec tube carbone,
ferrures aluminium, visserie acier, raccord SMA laiton et mousse EVA.
Avec des ferrures polymères, la provision devient **28,8 g** : ce sont deux
hypothèses de matériaux, pas des bornes garanties ni des masses mesurées.
Les anciens P07×1/P08×4/P09×1 représentent encore **39,7 g** à 1,25 g/cm³,
en volume plein. P07 est le support inférieur du récepteur, distinct du bras OEM.
Le retrait de 41,1 g suppose également que raccord SMA, visserie et EVA du
bras sortent du drone ; tout accessoire réutilisé reste compté embarqué.

| Scénario de retrait sur la configuration historique | Retrait brut, hypothèse ferrures aluminium |
|---|---:|
| bras OEM +Y seul | 41,1 g |
| bras +Y et tous les anciens supports P07–P09 | 80,8 g |

Dans le deuxième scénario, la soustraction seule sur le sous-total historique
6,195–6,809 kg donne **6,115–6,729 kg**, avant les nouveaux supports,
coaxiaux, connecteurs et changements de câbles. Ce résultat n'est pas la
masse complète de la cible. P07–P09 sont déjà absents de la maquette Helical
candidate : aucun second crédit de 39,7 g ne lui est applicable. Réutiliser
une pièce impose également de la conserver dans le bilan. Le retrait OEM
est compté une seule fois dans le contenu conservé du kit X650.

Le gain net et la masse totale cible restent inconnus. Définir les supports
antenne/récepteur/radio, les coaxiaux et leurs retenues, vérifier la place
disponible, les passages, les masques RF et le compas intégré au récepteur
inférieur près des câbles de puissance (DOC-ELEC§6). Les extrinsèques GNSS
doivent suivre la nouvelle position réelle de l'antenne ; aucun centrage,
montage, essai magnétique ou RF n'est qualifié par ce calcul.

### 6.2 Batteries comparées

| Candidate | Énergie | Masse publiée | Dimensions nominales | Statut |
|---|---:|---:|---:|---|
| Tattu G-Tech 8 Ah 6S | 177,6 Wh | 1 044 ou 1 160 g | 172,2 × 65,58 × 45,5 mm | alternative légère ; fiche incohérente **À valider** |
| Tattu G-Tech 10 Ah 6S | 222 Wh | 1 350 ±20 g | 176 × 66 × 58 mm, tolérances publiées ±5/±2/±2 | candidate de dimensionnement **À valider** |
| Tattu Plus 12 Ah 6S | 266,4 Wh | 1 670 ±100 g | 202 × 76 × 61 mm | trop longue pour l'enveloppe actuelle |
| Tattu classique 12 Ah 6S 30C XT90, TAA120006S30X | 266,4 Wh | 1 544 ±20 g | 192 × 72 × 54 mm | candidate distincte du Plus historique ; montage **À valider** |
| Tattu G-Tech classique 16 Ah 6S 30C XT90-S, fiche US | 355,2 Wh | 1 988 ±20 g | 192 × 76 × 65 mm | candidate ; cassette, centrage et masse complète **À valider** |
| Tattu semi-solid 20 Ah 6S 5C XT90-S, TAA200006S5X9S | 444 Wh | 1 950 ±20 g | 193 × 76 × 58 mm | technologie distincte ; énergie sous charge, profil électrique et montage **À valider** |

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

Cette table seule n'est pas une prévision de vol. Puissance chargée, température,
vieillissement et réserve de retour doivent être mesurés.

#### Estimation avec la mécanique disponible au 2 octobre 2026 — À valider

La lecture des volumes natifs des pièces actives non métalliques donne
507,565 cm³, soit 634,456 g sous l'hypothèse uniforme de pièces pleines à
1,25 g/cm³. Le remplacement du poste historique de 350 g ajoute environ
284 g ; P18/P19 ajoutent encore environ 2–6 g selon leur matériau. Avec la
batterie nominale de 1 350 g, cela conduit à environ **4,99–5,61 kg**,
en conservant les provisions électroniques historiques. Ce bilan partiel
n'est pas la masse complète actuelle : PM08-CAN, PDB, porteuse/Orin/CA01,
refroidissement et faisceaux doivent être réconciliés avec les éléments
remplacés, sans double comptage. Densités, remplissage, contenu exact du kit
et tolérance batterie restent à mesurer. Voir la
[preuve de volumes et de masse](../../hardware/mecanique/cartographe/verification/bilan_masse_volumes_20261002.json).

Pour estimer le stationnaire, chaque moteur fournit un quart du poids.
La [courbe T-Motor MN4014 KV330](https://store.tmotor.com/product/mn4014-kv330-motor-navigator-type.html)
à 22,2 V avec hélice 15×5CF fournit les couples poussée/puissance
830 g/79,92 W, 1 150 g/130,98 W, 1 430 g/173,16 W, 1 690 g/224,22 W
et 1 920 g/264,18 W. La puissance est interpolée linéairement en poussée,
puis multipliée par quatre. Le budget avionique de DOC-ELEC §5.1 ajoute
75 W / 0,80 = 93,75 W côté batterie, une seule fois pour tout le drone.
Les hélices du kit sont des Gemfan 1555 : la courbe 15×5CF est une
approximation d'étude et ne qualifie pas cette propulsion.

Avec 20 % d'énergie nominale conservée en réserve **par hypothèse**,
E = 22,2 × 10 × 0,80 = 177,6 Wh et t = 60 × E / P totale :

| Masse totale étudiée | Puissance totale interpolée | Stationnaire avant réserve | Sensibilité : puissance totale +20 % |
|---:|---:|---:|---:|
| 5,0 kg | 678 W | 15,7 min | 13,1 min |
| 5,3 kg | 723 W | 14,7 min | 12,3 min |
| 5,6 kg | 768 W | 13,9 min | 11,6 min |
| 6,0 kg | 841 W | 12,7 min | 10,6 min |

Le bilan mécanique partiel conduit ainsi à **environ 14–16 min au
stationnaire** ; une consommation totale supérieure de 20 % donne
**environ 12–13 min**. Ce supplément de puissance est une sensibilité
choisie, pas une marge démontrée pour une mission, le vent ou les pertes.
La réserve de 20 % ne démontre pas le retour depuis une distance donnée.
Ces durées portent sur le vol total avant réserve ; transits, décollage,
retour et atterrissage doivent être déduits pour une durée de cartographie.
La capacité délivrée à froid, le vieillissement, la chute de tension et les
seuils PX4 peuvent encore diminuer cette estimation.

Le [calcul détaillé](../../hardware/mecanique/cartographe/verification/estimation_autonomie_20261002.json)
conserve entrées, formules, résultats et limites. L'interpolation et les
quatre scénarios ont été recalculés indépendamment avec résultats concordants.
Cette vérification analytique ne qualifie ni `MEC-MAS-001` ni
`ELEC-PWR-002` : pesée/centrage, poussée et consommation avec les hélices
réelles, capacité délivrée et essais selon DOC-VAL restent à exécuter.
État de l'estimation : **À valider** ; aucun essai de vol ni simulation exécuté.

#### Comparaison énergétique 12S — À valider

L'étude du 12S conserve 10 Ah par hypothèse : 44,4 V nominaux,
50,4 V pleine charge et 444 Wh, dont 355,2 Wh avant réserve d'étude de
20 %. Deux packs 6S 10 Ah candidats représenteraient 2,70 kg, soit
1,35 kg supplémentaires. Cette masse est une construction de comparaison,
pas la sélection d'un pack 12S commercial. La cassette actuelle à un pack
ne couvre pas ce nouvel encombrement ; fixation, centrage et volume sont à
redéfinir. Les masses des adaptations nécessaires ne sont pas incluses.

**La chaîne actuelle ne peut pas recevoir directement une batterie 12S** ;
voir [DOC-ELEC §5.2.1](ARCHITECTURE_ELECTRIQUE_RESEAUX.md#521-compatibilité-dune-batterie-12s).
Les résultats suivants supposent une nouvelle propulsion compatible 12S
conservant exactement les mêmes watts par poussée que la courbe 6S du
§6.3. Ce transfert de rendement est une hypothèse non démontrée : ces durées
ne sont pas une prévision du matériel actuel, ni d'une propulsion 12S choisie.

| Masse 6S de référence | Masse avec batterie 12S hypothétique | Puissance de référence | Durée hypothétique avant réserve | Sensibilité : puissance +20 % |
|---:|---:|---:|---:|---:|
| 5,00 kg | 6,35 kg | 910 W | 23,4 min | 19,5 min |
| 5,30 kg | 6,65 kg | 969 W | 22,0 min | 18,3 min |
| 5,60 kg | 6,95 kg | 1 024 W | 20,8 min | 17,3 min |

Dans ce modèle, doubler l'énergie tout en ajoutant 1,35 kg donne environ
50 % de durée supplémentaire. Une 12S 5 Ah ne fournit que 222 Wh : à masse
et rendement identiques à la 6S 10 Ah, sa durée reste identique. Le gain
calculé vient de l'énergie ajoutée ; un gain dû à la tension seule n'est pas
démontré. Une 6S 20 Ah de même masse et rendement donnerait également ce
résultat dans le modèle, sans démontrer la faisabilité de cette autre variante.

Les trois masses dépassent déjà la limite de décollage **publiée** du
[X650, 6,3 kg](https://holybro.com/products/x650-development-kit), avant
refonte de propulsion et montage : elles ne sont pas admissibles pour la
configuration actuelle sur la base de cette publication. Le
[calcul 12S](../../hardware/mecanique/cartographe/verification/estimation_autonomie_12s_20261002.json)
conserve les hypothèses, formules, incompatibilités et résultats recalculés
indépendamment. Aucun changement de sélection batterie, de CAO, de câblage,
de paramètres PX4 ou de qualification n'est engagé par cette comparaison.

#### Comparaison énergétique 8S — À valider

À capacité maintenue de 10 Ah, le 8S représente 29,6 V nominaux,
33,6 V pleine charge et 296 Wh. La masse est supposée proportionnelle aux
cellules : 1,35 × 8/6 = 1,80 kg, soit +450 g. Aucun pack 8S n'est choisi ;
sa masse et sa compatibilité avec la cassette ne sont pas vérifiées.
Les masses des nouveaux ESC, des modifications CA01, du montage et des
faisceaux sont exclues. Le bilan d'avionique initial reste partiellement ouvert.

En conservant **par hypothèse** les watts par poussée de la courbe 6S et
le budget avionique de 93,75 W, avec 80 % des 296 Wh disponibles avant
réserve d'étude, on obtient :

| Masse 6S de référence | Masse avec pack 8S hypothétique | Puissance de référence | Stationnaire avant réserve | Sensibilité : puissance +20 % |
|---:|---:|---:|---:|---:|
| 5,00 kg | 5,45 kg | 746 W | 19,1 min | 15,9 min |
| 5,30 kg | 5,75 kg | 792 W | 17,9 min | 14,9 min |
| 5,60 kg | 6,05 kg | 851 W | 16,7 min | 13,9 min |

Le gain calculé est environ 20–22 % par rapport aux scénarios 6S 10 Ah,
et ne constitue pas une mesure d'autonomie en 8S. Les masses restent
250–850 g sous la limite X650 publiée de 6,3 kg **avant adaptations** ;
cela ne qualifie ni le centrage, ni la résistance, ni la marge de contrôle.

Les moteurs MN4014 KV330 sont annoncés pour 4–8S, mais les hélices Gemfan
1555 et leur charge en 8S ne sont pas qualifiées par la courbe à 22,2 V.
Les ESC actuels et la protection d'entrée CA01 restent incompatibles ; voir
[DOC-ELEC §5.2.2](ARCHITECTURE_ELECTRIQUE_RESEAUX.md#522-compatibilité-dune-batterie-8s).
Le [calcul 8S](../../hardware/mecanique/cartographe/verification/estimation_autonomie_8s_20261002.json)
conserve les formules et limites ; les trois scénarios ont été recalculés
indépendamment. Aucun changement matériel ou de paramètres PX4, aucune
simulation et aucun essai en 8S ne sont réalisés par cette comparaison.

#### Augmentation de capacité en conservant le 6S — À valider

Le 6S est conservé pour respecter la plage de tension des ESC actuels.
Une capacité plus élevée peut augmenter l'énergie sans relever la tension
standard 22,2 V nominal / 25,2 V pleine charge. La capacité de référence
reste 10 Ah ; aucune candidate ci-dessous n'est sélectionnée ou qualifiée.

La comparaison retient le scénario central de 5,30 kg, dont 1,35 kg de
batterie actuelle, remplacée par la masse publiée de chaque référence.
La courbe propulsion 6S du §6.3, les 93,75 W d'avionique, la réserve
d'énergie de 20 % et la sensibilité de puissance +20 % sont conservées :

| Candidate précise | Masse du pack | Masse totale centrale, hors adaptation | Stationnaire avant réserve | Sensibilité : puissance +20 % |
|---|---:|---:|---:|---:|
| 10 Ah actuelle | 1,350 kg | 5,300 kg | 14,7 min | 12,3 min |
| [12 Ah classique XT90](https://gensace.de/products/tattu-12000mah-22-2v-30c-6s1p-uav-lipo-battery-pack-with-xt90-plug) | 1,544 kg | 5,494 kg | 17,0 min | 14,2 min |
| [16 Ah classique, fiche US](https://genstattu.com/ta-30c-16000-6s1p-xt90.html) | 1,988 kg | 5,938 kg | 20,6 min | 17,1 min |
| [20 Ah semi-solid 5C](https://gensace.de/collections/semi-solid-state/products/tattu-nmc-20000mah-22-2v-5c-6s1p-lipo-battery-pack-with-xt90-s-plug) | 1,950 kg | 5,900 kg | 25,9 min | 21,6 min |

La 16 Ah classique est une candidate à examiner pour un gain central
d'environ 40 %. La 20 Ah semi-solid apporte un gain analytique central
d'environ 76 %, mais son profil de tension et son énergie délivrée sous
charge ne sont pas assimilés à ceux d'une LiPo classique. La fiche déclare
5C et vise des usages nominaux 1–3C ; courants continus et transitoires,
chargeur, tension de charge, affaissement de tension, température, réserve
et seuils PX4 doivent être vérifiés. Les 1 800 g d'une brochure ne
correspondent pas à la masse de 1 950 g de la référence retenue pour ce calcul.

Les packs comparés dépassent l'enveloppe nominale actuelle de
176 × 66 × 58 mm. Cassette/berceau, retenue, centre de gravité, connectique
et faisceau sont à vérifier ou adapter ; aucune CAO n'est modifiée ici.
L'augmentation de capacité ne suffit pas à établir la compatibilité du montage.

Le bilan mécanique initial partiel est 4,991–5,605 kg. Avec les masses
nominales, la 16 Ah conduit à 5,629–6,243 kg, et la 20 Ah à
5,591–6,205 kg, **avant adaptations**. À la borne haute, les marges sous
la limite commerciale X650 de 6,3 kg sont seulement 56,5 g et 94,5 g,
ou 36,5 g et 74,5 g avec +20 g de tolérance pack. Une pesée et la fermeture
du bilan d'avionique/montage sont donc requises avant de retenir une capacité.
Les durées varient aussi avec cette masse : environ 19,2–22,1 min au
stationnaire pour la 16 Ah, et 24,2–27,8 min pour la 20 Ah, sous les
mêmes hypothèses de calcul. Ces intervalles ne bornent pas toutes les incertitudes.

Deux packs actuels 10 Ah en parallèle donneraient 6S 20 Ah, mais
2,70 kg de batteries et 6,65 kg au scénario central, au-dessus des 6,3 kg
publiés avant câblage/montage. Cette intégration n'est pas retenue ici.

La [preuve de calcul des capacités 6S](../../hardware/mecanique/cartographe/verification/estimation_autonomie_capacite_6s_20261002.json)
conserve références, formules, bornes de masse et limites. Les scénarios
centraux et bornes 16/20 Ah ont été recalculés indépendamment avec résultats
concordants. État **À valider** : aucune pesée, décharge, simulation,
qualification de vol ou modification de paramètres PX4 réalisée.

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
| cassette ↔ TE MiddleDrawer | effort transmis au connecteur ou engagement incomplet | tolérances, liberté flottante, guidage, cycles et traction câble |
| Jetson ↔ support | contact, chauffe, maintenance | contrôle d'interférence et essai thermique |
| antenne RTK ↔ structure | masque, multipath, vibration | champ libre, répétabilité et essai GNSS |
| câbles ↔ pièces mobiles/isolées | fatigue ou pont vibratoire | rayon, rétention, frottement et cycles |

## 8. Vérification et traçabilité

Les protocoles transversaux, résultats et statuts de qualification sont
centralisés dans [DOC-VAL](../VALIDATION_QUALIFICATION.md).

| Exigence | Composant | Test/preuve | Résultat |
|---|---|---|---|
| `MEC-ARC-001` réutiliser les références | arborescence FreeCAD20Ah | `verification/hierarchie_20Ah_20261002.json`, `T-BAT20-NATIF` | références liées dans la maquette active ; pièces physiques **À valider** |
| `MEC-BAT-001` échange sans outil et verrouillage positif | railsP28/P29, cassetteP30–P33, butéeP35/P36, SouthcoR4 | `T-BAT20-INSERT/FIX`, puis essai du verrou | CAO **Implémenté** ; fonctionnement et tenue **À valider** |
| `MEC-CON-001` ne pas charger mécaniquement le connecteur | butée séparée, supportsP39/P40, contactsTE | `T-BAT20-CONTACT/INSERT`, cycles | géométrie de course contrôlée ; engagement réel et flottement **À valider** |
| `MEC-VIB-001` préserver les capteurs et leur calibration | SA05 capteurs isolés | `verification/isolation_capteurs.json`, vibration et calibration | contacts corrigés ; huit poses contrôlées ; physique **À valider** |
| `MEC-AVI-001` retenue et intégration avionique | ancienne CAO P06, P20–P22 ; cible Holybro/CA01 et fixation communeP17 dans variante inactive | `T-STACK-REVUE-NATIF/GEOM`, DOC-VAL §12.7.14 ; maquette avec faisceau §12.1.4 et ancienne preuve16/09 de périmètres distincts | montage candidat **Implémenté** ; tenue, précharge, accès/maintenance et isolation **À valider** |
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
| 5 octobre 2026 | Batterie67 pièces et récepteur72 séparés, six équipements d’énergie directement dans le principal ; fichiers stables, anciens montages non installés ; réouverture149 références/poses/apparences conservées, extraction unique0/50/500 et registres182/115 contrôlés (§4.1.3.4). |
| 5 octobre 2026 | Raccordement compact : TE avancé encore40 mm, positif axial17,2548 mm et C−49,3353 mm, protections locales ; depuis1ccbad81 cassette−10,505 %, énergie−2,757 %, intégration inchangée ; contrôle BMS réussi, contrôles complets et persistance SA08 réussis (§4.1.3.3). |
| 5 octobre 2026 | Première implantation supérieure historique Git1ccbad81 : BMS au-dessus du pack ; P37 portée à95 mm, plateau/fixations +25 mm, P43/P44 adaptés et TE avancé74 mm ; comparaison BMS contrôlée −13,738 % batterie/énergie, +12,246 % cassette seule et −10,028 % intégration locale ; contrôles BMS, SA08 enregistrés et registres réussis (§4.1.3.3). |
| 5 octobre 2026 | Étape arrière historique dans Git94d04d0 : BMS/P58 dans P43/P44 de142×76, recul TE additionnel44 mm et SA08 recoté ; remplacée par l’implantation au-dessus du pack. |
| 5 octobre 2026 | Préparationinitiale BMS solidaire de la cassette Planifié ; compartiment arrière P43/P44 privilégié après réaménagement, faible jeu au-dessus mesuré ; aucun module/cote ni remplacement de connecteur supposé (§4.1.3.3) |
| 4 octobre 2026 | Étage énergie inférieur et liaison directe candidate AWG8/742F5 M5 au TE ; pack retourné, supports reculés de 82 mm, coffrets et passages repris ; contrôle du seul pack nominal, enveloppe d'étude/lot/fixations/thermique **À valider**, adaptateur de charge **Planifié** (§4.1.3.2, DOC-VAL §12.1.8) |
| 4 octobre 2026 | Couleurs natives du dock et suivi Git de91 petits natifs ; noms stables, repli des deux cordons fixesR50 et hauteur calculée−29,3% ; pistes JETI/XT90/cassette et intersectionP49 ouverte (§4.1.3.1, DOC-VAL§12.1.7) |
| 4 octobre 2026 | Tri des natifs : 10 sous-assemblages courants et deux montages de construction, 13 anciens SA et cinq globaux archivés avec leurs dépendances ; catalogue/guide actualisés, réouvertures séparées et reprise de source stack contrôlées (§2.1, DOC-VAL§12.1.6) |
| 4 octobre 2026 | Scénario GNSS sur plateaux et antennes radio déportées : bras OEM identifié, retraits bruts conditionnels de 41,1/80,8 g, hypothèses matériaux et absence de gain net/masse cible distinguées ; aucun placement CAO modifié (§6.1) |
| 3 octobre 2026 | Stack revue sur plan Holybro4M3/120×74 : CA01 synchronisée, perçages natifs repris, appuis24/2, fixation communeP17 et vis65, plaqueP56 dérivée ; première visserie rejetée, accès outil avec déposebloccapteurs et qualification mécanique/électrique ouvertes (§4.4.1.1) |
| 3 octobre 2026 | Revue BOM système à 60 postes et maquette cible inactive avec 35 routes natives ; présélections et masses incluses distinguées, rayons/interférences ouverts et cuivre du dock ajouté au budget historique seulement ; aucun gel de montage ni qualification des passages (§4.5, §6.1, DOC-VAL §12.1.4) |
| 3 octobre 2026 | Sélection6S20Ah, rehausse20mm, déplacementPixhawk et cassette coulissanteP27–P53 ; loquetSouthcoR4, contactsTE et coupureJETI existants, faisceaux protégés et retenus, BOM consolidée ; vérifications de course et limites STEP/hélices/masse distinguées de la qualification physique (§4.1.3, DOC-VAL§12.1.3) |
| 2 octobre 2026 | Faisabilité batterie entre plateaux OEM Z33/Z83 : 50 mm actuels insuffisants ; rehausses candidates +20 mm en 20 Ah et +30 mm en 16 Ah, déplacement avionique et nouvel accès/verrou nécessaires ; dégagement près des hélices non qualifié (§4.1.2) |
| 2 octobre 2026 | Reprise batterie 6S : logement P14 trop petit, patte de gâche hors solide final et ancrages décentrés ; variantes natives de berceau fixe P23–P26/capot captif pour 16/20 Ah, Southco91 candidat et contrôles distincts de la tenue physique (§4.1.1, DOC-VAL §12.1.1) |
| 2 octobre 2026 | Maintien 6S et comparaison capacités : 12/16 Ah classiques et 20 Ah semi-solid avec références et masses publiées ; gains conditionnels, cassette/centrage et bilan complet à fermer, marge faible sous limite X650 à la borne haute ; aucune nouvelle capacité sélectionnée (§6.2–6.3) |
| 2 octobre 2026 | Comparaison 8S 10 Ah hypothétique : 296 Wh, batterie provisionnelle de 1,80 kg et gain analytique 20–22 % ; moteur dans plage fabricant mais ESC et CA01 incompatibles, masses et fonctionnement chargé À valider (§6.3) |
| 2 octobre 2026 | Comparaison hypothétique 12S 10 Ah : 444 Wh, batterie de 2,70 kg et durée analytique 21–23 min avant réserve, 17–20 min sous sensibilité +20 % ; propulsion actuelle incompatible, masse supérieure à la limite X650 publiée et cassette à reprendre ; aucune migration engagée (§6.3) |
| 2 octobre 2026 | Estimation d'autonomie avec batterie 6S 10 Ah : correction partielle des volumes mécaniques, interpolation poussée/puissance, budget avionique et réserve d'étude ; environ 14–16 min au stationnaire et 12–13 min sous sensibilité +20 % de puissance ; masses électroniques, hélices réelles et vol À valider (§6.3) |
| 2 octobre 2026 | Routage CA01 : contour/fixations/connecteurs conservés,48placements électriques repris ; exports mécaniques01/10 à réactualiser, aucune qualification de montage (§4.4.1) |
| 2 octobre 2026 | Démarrage du routage CA01 quatre couches : placements, modèles, contour et fixations conservés ; distinction entre PCB électrique et exports mécaniques, thermique et fabrication À valider |
| 1 octobre 2026 | Préplacement CA01 126 × 80 mm et quatre trous Ø3,2 ; variante native sous Holybro avec gap candidat 10 mm et onze familles d'enveloppes ; R116 CSM3637 et MOD401 RP4TD direct synchronisés dans PCB/STEP/natif, J401/W11 et ancienne réserve retirés ; 163solides historiques ;10familles/16occurrences de boîtes remplacées par modèles détaillés nominaux,308solides/141composants courants ;réouverture/liens et interférences contrôlés ;RP4TD détaillé introuvable ;4trousTHT natifs photoestimés, pads/broches/hauteur À valider, thermique/fabrication À valider |
| 25 septembre 2026 | Variante H-RTK Helical STM32G4 candidate pour PPS : SA06, antenne et passage CAN/UART2 à reprendre ; CAO Rover patch conservée comme historique |
| 25 septembre 2026 | Guide Airy v1.3 intégré pour fixation, planéité, piges, mou câble, rigidité et dissipation ; P16 actuelle à reprendre et vérifier |
| 25 septembre 2026 | PDB Holybro 300A Top Entry SKU 18138 inscrite comme candidate en aval du PM08-CAN ; support M3, XT90/XT30, isolation, accès et masse installée à valider, CAO non migrée |
| 24 septembre 2026 | Rover H-RTK F9P à patch intégré et Base H-RTK F9P/HANT-X627A sélectionnés ; supports SA06/SA07 et enveloppes historiques à reprendre |
| 24 septembre 2026 | cible porteuse Holybro avec Pixhawk 6X module et Orin NX 16 Go ; BEC1/2 vers POWER1/POWER2, CA01 5 V local et XT30/12 V candidat ; SA03/SA04, manifeste et preuves CAO historiques non migrés |
| 22 septembre 2026 | cible PM08-CAN fixé au châssis près de la distribution, hors pack ; deux BEC affectés vol/radio et auxiliaires/synchronisation ; nouvelle enveloppe et masse à intégrer, CAO et circuits KiCad V0.3 non migrés |
| 22 septembre 2026 | PM02D complet en tête de distribution avec faisceau adapté ; BEC conservé hors CA01 ; support sur cassette à étudier ; simulation distincte de qualification électrique |
| 21 septembre 2026 | PM02D hors CA01, support isolant séparé à définir avec maintien, accès et décharge câbles ; liaison directe POWER1 et dérivation radio depuis le vol ; CAO SA03 inchangée |
| 17 septembre 2026 | intégration CA01 planifiée, PM02D rapporté candidat ; CAO SA03 conservée et limites explicites des réserves d'encombrement antérieures |
| 16 septembre 2026 | correction des contacts capteurs, bilan isolateurs et quantités ; pile avionique sur ancrages OEM, P20–P22, retenues, exports et points ouverts |
| 13 septembre 2026 | consolidation des décisions actives de CAO, montage capteurs, batterie et isolation ; retrait du registre ADR |
| 10 septembre 2026 | consolidation des choix, sous-assemblages, exigences batterie, BOM, masses, autonomie et preuves existantes |
