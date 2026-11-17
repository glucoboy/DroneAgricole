# GO3B V2.1 — reconstruction et contre-validation

**GO3B_CAO_NO_GO_MOTIVE**, 17 novembre 2026. Les trois familles ont été
construites sur copies du prototype cartographe sans dock. Six variantes
ont été sauvegardées, recalculées et rouvertes. Une copie consolidée de
diagnostic réunit les seules corrections communes. La réception CAO est
refusée à cause de défauts mesurés et de contrôles incomplets.
La maturité du dossier est **Implémenté**, le montage reste **À valider**.

Les décisions actives sont intégrées à DOC-MEC, DOC-ELEC et DOC-VAL.
Ce rapport constitue le livrable de campagne explicitement demandé.
[Décision mécanique](../architecture/ARCHITECTURE_MECANIQUE.md#cartographe-go3b-reconstruction) ·
[Résultat de validation](../VALIDATION_QUALIFICATION.md#cartographe-go3b-reconstruction)

## Référentiel et périmètre

La porte d’exploration a été rejouée sur les trois demandes exactes
H-03, H-02 et H-01 avec le binaire scellé C. Chaque reçu rend
EXPLORATION_ALLOWED / PLANNED et contrôle 180 fichiers.
Le gel est `3fc42609…`, sa racine active `87eec083…`.
Le témoin reprend 137 natifs et quatre auxiliaires du gel.
Le registre de construction existant est ajouté comme cinquième auxiliaire
pour vérifier les occurrences et les poses. Les 142 fichiers sources
sont retrouvés identiques après la campagne.

L’environnement exécuté est Windows amd64, FreeCAD 1.1.3, OCCT 7.8.1,
Python FreeCAD 3.11 et Cables 0.3.7. Le repli Python a passé le probe
Part et les 19 tests natifs Cables. Les commandes, versions et SHA-256
sont dans le manifeste. Les contrôles portent sur les fichiers sauvegardés
et les critères gelés. [Manifeste](../verification/v21_go3b_manifest.json)

La couverture documentaire conserve 71 lignes, 142 côtés, 53 axes,
56 associations et 21 exceptions motivées. L2 et la netlist CA01 ont
été rejoués indépendamment. Les 43 broches documentaires, 15 références,
six feuilles et quatre options DNP sont conservées. L2 détecte GPS2
sur le témoin et confirme la réservation TELEM1 des copies corrigées.
Les contacts montés et la continuité physique restent inconnus.
[Preuve électrique](../verification/v21_go3b/electrical_evidence.json)

## Construction et budget

Le plafond de 12 expériences est conservé. Huit tentatives de variantes
ont réellement été lancées, avec six sauvegardes complètes et deux
échecs de génération H01-A/B sur sommets successifs confondus.
Les deux reprises natives sont conservées avec leurs échecs d’origine.
La consolidation ajoute une expérience, soit **9/12 crédits consommés**.
Le témoin et les mesures en mémoire sont exclus de ce compte.
Le budget d’achat consommé est 0 €.

Deux configurations ont été évaluées dans chacune des trois familles.
L’arrêt intervient après les rejets des deux configurations et la
contre-validation de la consolidée. Les trois crédits restants sont
inutilisés. L’instruction GO3B de conserver les variantes rejetées conduit
à archiver les six états paramétriques, en plus des échecs de génération.
[Variantes et décisions](../verification/v21_go3b_candidates.json)

| Famille | Réalisation native et limite |
|---|---|
| H-03 | Isolateur déplacé au chant ouest, orientations 180° et 270°, branches F40/F41 régénérées avec faces et gestes transformés ensemble. Les appuis restent des réservations ASSUMED. |
| H-02 | Isolateur fixe, corridors F41 dessous ou latéral, F40 reconnecté à la réservation TTL, témoin F16 natif repris. Les corps coudés et la ferrite sont des enveloppes ASSUMED. Le parcours M8 de référence est conservé et sondé. |
| H-01 | Isolateur fixe, F40/F41 régénérés avec deux réservations passives distantes et témoin F16. Le modèle réserve les raccords, leur pin à pin et leur montage restent incomplets. |
| Consolidée | F12 vers TELEM1, F35 au sud, F25 et P85 au chant P66. Les choix incompatibles des trois familles rejetées sont écartés. L’isolateur et les branches historiques de diagnostic restent à reprendre. |

Les deux extrémités incidentes à l’isolateur suivent la mutation H-03.
Les extrémités opposées BMS/hôte restent à leur repère de référence.
Les six variantes ont une concordance géométrique aux réservations TTL/USB.
Sur la consolidée, les axes historiques restent à **98,871 mm du TTL**
et **53,639 mm de l’USB-B**. Ce sont des écarts aux faces du modèle,
avec contacts réels encore inconnus.
[Revue indépendante des interfaces](../verification/v21_go3b/interfaces_review.json)

## Mesures comparables et rejets

Même inventaire des 53 axes, même repère XYZ et mêmes zones gelées.
Les longueurs par zone sont calculées par clipping à 96 et 384 points
par courbe. Le tableau emploie 96 points pour reproduire la référence.
La somme des axes ne constitue pas une liste de coupes de cordons.

| Copie | Axes cumulés mm | Baie mm | Au-dessus mm | Sous P66 stricte mm | Paires FAIL observées | Paires NOT_RUN |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 12125,900 | 4341,486 | 2421,421 | 451,202 | 7 | 0 |
| H03-A | 11722,215 | 4164,777 | 2338,767 | 480,198 | 8 | 120 |
| H03-B | 11709,510 | 4164,766 | 2340,767 | 451,202 | 9 | 178 |
| H02-A | 12051,961 | 4164,825 | 2338,945 | 493,327 | 9 | 396 |
| H02-B | 11662,262 | 4164,825 | 2338,945 | 493,327 | 8 | 283 |
| H01-A-reprise | 11852,685 | 4164,825 | 2226,075 | 552,251 | 9 | 303 |
| H01-B-reprise | 11861,050 | 4164,825 | 2226,075 | 552,251 | 10 | 307 |
| consolidee | 12143,722 | 4257,184 | 2318,252 | 451,202 | 7 | 60 |

Les couvertures des variantes diffèrent. Les défauts dénombrés sont
des bornes inférieures. Chaque variante conserve les sept défauts B.2.
H03-A ajoute F40/P72 à 18,258 mm³. H03-B ajoute F40/P72 à 24,317 mm³
et isolateur/P72 à 146,756 mm³. Les supports H03 recoupent P72 à
109,734 mm³ sous l’hypothèse d’appui et laissent un jeu de 0,300 mm
avec le module. Les H02 recoupent F40/P72 à 42,676 mm³.
H02-A ajoute F41/P72 à 41,433 mm³. Les H01 recoupent notamment
F40/P73 à 618,710 ou 78,781 mm³.
[Mesures et périmètres](../verification/v21_go3b/independent_evidence.json)

La consolidée mesure 12 143,722 mm d’axes contre 12 125,900 mm au témoin,
soit +17,822 mm. La baie passe de 4 341,486 à 4 257,184 mm et le dessus
de 2 421,421 à 2 318,252 mm. Sous P66 stricte et en hauteur de gaine,
les valeurs restent 451,202 et 173,278 mm.
Le volume occupé par union avec les fiches exactes, la masse complète,
le centrage et le nombre d’opérations de maintenance sont inconnus.
Le support H03 donnerait 15,595 g avec une densité analogue aluminium
de 2,70 g/cm³, hors ancrages et vis. Ce calcul conditionnel ne renseigne
pas la masse complète.

## Couverture de contre-validation

La consolidée a été sauvegardée puis rouverte dans de nouveaux processus
FreeCAD. La fermeture relocalisée compte 138 natifs, dont P85.
Ses 566 solides relus passent le contrôle de validité et de volume.
Les 53 routes restent INCONCLUSIVE pour les limites constructeur et
les repères de contact manquants. L4 et sa finalisation T0 ont été
exécutés et validés sur H03-A et la consolidée.

Le contrôle indépendant de la consolidée énumère 28 567 paires avec
au moins un câble et écarte 26 941 paires par AABB.
Les 1 629 paires retenues, incluant trois paires supplémentaires
hors câble, donnent **7 FAIL, 1 562 INCONCLUSIVE et 60 NOT_RUN**
pour l’admission. Parmi les mesures nominales réalisées, 1 562 ont
un résultat géométrique favorable et sept échouent.
1 533 résultats antérieurs sont repris seulement après égalité des
BRep, poses, visibilité et critères. Les 36 mesures fraîches comprennent
29 paires sans intersection et les sept défauts confirmés.

Les six recouvrements des branches Airy restent interdits selon le
référentiel gelé. La paire F37_POS/P73 reste en échec à
2,8373 × 10⁻⁸ mm³ avec un seuil gelé nul. Son interprétation à une
tolérance physique reste ouverte. Les couples porteur/F12, F25 et
F35 ont bloqué les calculs et sont explicitement NOT_RUN.
Les autres paires hors budget de calcul gardent le même statut.
[Contrôles et exigences](../verification/v21_go3b_validation.json)

Les 93 enveloppes de service sont mesurées comme hypothèses statiques
dans une preuve distincte. Elles couvrent CAN1, TTL, USB, ferrite,
sorties caméra/M8 et déports selon la famille. Le seuil local de
criblage est 10⁻⁴ mm³. Ces sondes restent INCONCLUSIVE pour la réception.
Les premières variantes ont une section CAN1 transposée en XY,
enregistrée telle que sauvegardée. La consolidée porte la section
4,15 × 6,25 mm. Le balayage continu caméra, les verrous réels et
les gestes de montage ne sont pas exécutés.

## Artefacts et suite

Les copies, échecs, paramètres et reçus sont archivés sous
`hardware/mecanique/cartographe/verification/go3b/artefacts/`.
Les liens XLink restent relatifs et les fichiers livrés sont
byte-identiques aux copies mesurées. Conserver toute l’arborescence.
Les natifs et rendus restent exclus de Git.
[Ouvrir la consolidée](../../hardware/mecanique/cartographe/verification/go3b/artefacts/consolidee/cad/assemblages/Prototype_Cartographe.FCStd)

Les trois planches comparent dessus, dessous, profil, baie transparente
et accès de service. Les enveloppes ASSUMED servent de sondes.
[Vues orthographiques](../../hardware/mecanique/cartographe/verification/go3b/vues/01_dessus_dessous_profil.png) ·
[Baie et service](../../hardware/mecanique/cartographe/verification/go3b/vues/02_service_et_camera.png) ·
[Détails des interfaces supposées](../../hardware/mecanique/cartographe/verification/go3b/vues/03_interfaces_supposees.png) ·
[Index des vues](../../hardware/mecanique/cartographe/verification/go3b/vues/vues.json)

La BOM électrique dérivée compte 142 côtés, 36 cordons et dix
jonctions documentaires. La BOM physique conserve 369 liens directs
en explicitant les sous-assemblages. Les masses, coupes et raccords
inconnus restent ouverts. La séquence de montage est proposée pour
revue et porte l’étape bloquante du diagnostic.
[BOM électrique](../verification/v21_go3b/electrical_bom.csv) ·
[BOM physique](../verification/v21_go3b/physical_bom.csv) ·
[Séquence](../verification/v21_go3b/assembly_sequence.json)

La prochaine expérience discriminante doit réaliser un appui effectivement
ancré de l’isolateur et un trajet F40 indépendant des retenues P72/P73,
puis recontrôler les deux branches avec CAN1, PDB et F25 présents.
Elle doit aussi définir la séparation géométrique des branches Airy
et instruire le défaut F37_POS/P73. L’épreuve de réception sera relancée
sur une copie complète après ces corrections.

Les essais sur exemplaires, continuité, isolement, mouvement, traction,
vibration/fatigue, thermique, CEM et vol sont NOT_RUN. Le plan GO4
porte leurs prérequis et les critères encore à définir.
[Liste GO4](../verification/v21_go3b/go4.json)
