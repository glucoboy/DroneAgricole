# Architecture mécanique

| Champ | Valeur |
|---|---|
| Référence | `DOC-MEC` |
| Nature | document vivant |
| Dernière mise à jour | 28 novembre 2026 |
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
- natifs FreeCAD `.FCStd` suivis dans Git avec leurs dépendances ;
- sauvegardes FreeCAD, sources fabricant lourdes et exports dérivés exclus de Git ;
- placements, références et occurrences décrits dans `manifest.json`.

Le manifeste est l'autorité pour les noms de fichiers et matrices de placement.
Ce document explique l'intention et la nomenclature, sans recopier toutes les
coordonnées.

**Suivi Git — 17 novembre 2026.** À la demande du responsable du projet,
les natifs `.FCStd` existants sont intégrés au dépôt, y compris les variantes
et archives, pour conserver les montages et leurs liens externes lors d'un
transfert du dépôt. Cette intégration préserve les fichiers en place et ne
modifie pas leur état de qualification. Les répertoires `sources_fabricants/`
et `exports/`, ainsi que les sauvegardes `.FCStd1` et `.FCBak`, restent exclus.

### 2.1 Catalogue historique et archives — 4 octobre 2026

**Réserve de preuve du 7 octobre, consignée le 8 :** le fichier courant
`Integration_Stack_Revue_20261003.FCStd` diffère à l'octet près de l'empreinte
de la revue du 5 octobre. La portée reste inconnue : aucune régression
géométrique n'est démontrée, aucune nouvelle sauvegarde CAO n'a été effectuée
par l'audit. Examiner le contenu puis contrôler la portée nécessaire avant
de réutiliser cette revue comme preuve de l'état présent
([AUD-007](../VALIDATION_QUALIFICATION.md#aud-007)). Les contraintes historiques
encore présentes dans la configuration cible doivent aussi être distinguées
de la course continue restant à valider
([AUD-008](../VALIDATION_QUALIFICATION.md#aud-008)).

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

Lors de ce rangement, l'intégration locale de stack était le seul assemblage
conservé dans `assemblages/`. Le faisceau SA08 est lié à cette intégration
historique ; GNSS et station sol y restent séparés. Ce rangement n'avait pas
assemblé ni qualifié un nouveau drone complet. Le prototype actif est
désormais décrit au §2.2.
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

<a id="assemblage-prototype"></a>
### 2.2 Assemblage actif du prototype — 25 octobre 2026

L’assemblage actif est
[`Prototype_Cartographe.FCStd`](../../hardware/mecanique/cartographe/assemblages/Prototype_Cartographe.FCStd).
**État antérieur du 22 octobre**, dont les contrôles sont conservés avec leurs
empreintes : la reconstruction comportait **118 références
et 346 occurrences** dans sept sous-assemblages liés. Les fichiers sauvegardés
ont été rouverts, recalculés et contrôlés sous FreeCAD 1.1 avec les empreintes
de cette construction. Les résultats, la revue indépendante et les inspections
visuelles sont délimités dans [DOC-VAL §14.4](../VALIDATION_QUALIFICATION.md#assemblage-prototype).
La faisabilité matérielle reste **À valider** ; aucun essai physique n’a été exécuté.

Le montage conserve le X650 OEM sans dock : batterie sanglée sous le plateau
central, BMS au-dessus du pack, perception sous la batterie et avionique
au-dessus du plateau OEM supérieur. L’énergie reste à l’étage supérieur et
la caméra conserve sa position avec ses deux prises coudées. Le choix du
terminal au sol reste différé et sans incidence sur cette CAO.

| Référence native | Fonction |
|---|---|
| `SA01_Prototype_Structure` | structure OEM, bras, train et propulsion |
| `SA02_Prototype_Batterie` | pack, sangles, butées, BMS et protection amont |
| `SA03_Prototype_Energie` | PM08-CAN, PDB et isolateur UART sur supports isolants |
| `SA04_Prototype_Perception` | Airy, Basler et objectif sur bloc isolé |
| `SA05_Prototype_Avionique` | CA01, porteuse Holybro avec 6X/Orin et refroidissement |
| `SA06_Prototype_Navigation` | GNSS, antennes radio et réservation de sécurité |
| `SA07_Prototype_Faisceaux` | 53 parcours natifs Cable Workbench, guides et retenues |

Le [tri initial](../../hardware/mecanique/cartographe/verification/inventaire_reconstruction_prototype.json)
et la [construction](../../hardware/mecanique/cartographe/verification/historique/orch_cao_masse_1/construction_prototype.json)
possèdent les sources, références et placements. Les sources OEM et les études
historiques restent préservées. Quatre colonnes invalides de la source X650
sont remplacées dans la seule dérivée. La porteuse conserve les modules Orin
et 6X déjà présents ; les douze solides de refroidissement générique et huit
fixations nylon remplacés ne sont pas comptés en plus du Waveshare et de la
visserie retenus. Les rails, brides et plateau déporté inutiles ne sont pas
reconduits ; aucun gain de masse n’est déduit sans pesée.

**Énergie et supports réemployés.** P64 G10 mesure 188 × 176 × 2,8 mm,
à Z36,2..39, sur quatre cales P74 de 3,2 mm. Ses deux axes M3 communs
avec P72/P73 assurent sa retenue ; ils sont comptés une fois. Les modules
restent à Z39, avec une garde nominale PM08/UART de **18 mm** sous Z83.
La garde ne comprend pas les fiches ni la chaîne de tolérances. P62/P63
conservent la plateforme BMS. La tablette du MIDI est intégrée à P73 et ses
deux bandes évitent les bornes et les gaines. P76 réemploie les deux vis de
la butée droite, sans fixation au softpack. Les interfaces fabricant encore
inconnues des modules énergie restent des réservations à confronter aux plans
ou lots ; aucune bride pressant un PCB ou un composant n’est prescrite par hypothèse.

P69 et P71 possèdent chacun une plaque, des bras et des pattes fusionnés
nativement en un solide. Quatre ensembles M2 × 12 réemploient les trous
X±43/Y±29 de P66 et du plateau OEM, sans nouveau perçage fabricant. P70
conserve les positions des antennes et se reprend sous P75 par deux boucles
natives. Pour RF1, la boucle `CollierAncrageRF1` retient aussi le corps
d’antenne dans le sandwich P70/antenne/P75 ; RF0 possède une seule boucle
de corps supplémentaire vers P75 à Z141. La propriété générique de construction
ne prescrit donc pas deux colliers d’antenne supplémentaires. Les lumières
de 3 × 4,8 mm et le passage des bandes de 4,6 mm ont été contrôlés.
La fixation des supports est ainsi démontrée géométriquement ; les interfaces
des modules GNSS/USL et la tenue réelle des antennes restent **À valider**.

**Cheminements et retenues.** Les
[53 parcours](../../hardware/mecanique/cartographe/verification/routes_prototype.json)
sont des objets Cable et WireFlex éditables de Cable Workbench 0.3.7. Ils
longent les plateaux, P72/P73/P75 et les bras, avec réemploi des quatre P79
et huit P80. Les huit départs signal/LED sont fermés par douze stations :
deux par commande MAIN/F04 et une par LED de bras, contrôlées sur les
natifs sauvegardés. Trois boucles communes traversent les lumières de P77
et retiennent la réserve USB ; neuf liaisons entre supports sont contrôlées.

Le [contrat de retenues](../../hardware/mecanique/cartographe/verification/retenues_faisceaux_prototype.json)
et ses preuves possèdent les affectations et les budgets de portée. La BOM
compte **281 colliers nominaux dans le périmètre de contrôle** :
269 colliers uniques du contrat, sept liaisons supplémentaires et quatre
boucles RF/MIDI, auxquels s’ajoute la seule boucle de corps RF0. Les deux
liaisons P75–P72 sont déjà incluses dans les 269 ; les trois boucles USB
le sont également. QS8 réemploie F37_POS_-20, RF1 réemploie sa boucle native.
Les captures des trois corps QS8/RF0/RF1 et leurs têtes sont contrôlées.
Les provisions historiques ne s’additionnent pas. Ces contrôles de bandes,
passages, portées et interférences
ne qualifient ni le serrage, ni l’abrasion, ni les vibrations. Les 53 parcours
comprennent des conducteurs et branches communs : ils ne constituent pas
53 achats ni des longueurs de coupe libérées.

**Caméra et accès.** La géométrie fabricant de la fiche USBFireWire
RR-ASMUK-20GRHF et l’enveloppe M8 Phoenix 1522341 sont conservées à la
position actuelle de la Basler. Le corps USB laisse 1,82 mm nominaux sous
P60, soit 1,62 mm avec sa seule tolérance de +0,2 mm. Le M8 utilise un
engagement de 6 mm hypothétique, avec dégagement local de P60 et du pad.
La [définition des prises coudées](../../hardware/mecanique/cartographe/verification/connecteurs_coudes_camera_prototype.json)
et [DOC-ELEC §6](ARCHITECTURE_ELECTRIQUE_RESEAUX.md#definition-electrique-prototype)
portent les sources et limites : engagement, polarisation, montage simultané,
rayons dynamiques et faible marge du cordon USB restent à vérifier sur matériel.
La source fabricant Basler signalée invalide par OCCT reste identifiée ;
cette limite de représentation n’établit pas un défaut du matériel.

La [BOM](../../hardware/mecanique/cartographe/nomenclature_prototype.json),
le [classeur](../../hardware/mecanique/cartographe/exports/Nomenclature_Prototype_Cartographe.xlsx)
et la [couverture BOM/CAO](../../hardware/mecanique/cartographe/verification/historique/orch_cao_masse_1/couverture_bom_cao_prototype.json)
sont rapprochés des fichiers vérifiés. Les **20 détails matériels ouverts**
portent réception OEM, interfaces fabricant et fabrication ou essais physiques.
Ils ne remplacent aucun défaut CAO constaté. Restent notamment les interfaces
modules, brochages et terminaisons, tolérances, protections, tenue, thermique,
masses installées et centrage/endurance. Le QS8 est une réservation monobloc :
son demi-corps fixe, sa face de joint, l’accouplement et l’extraction hors
bande ainsi que la prise en main sont à vérifier sur plan/lot ; adapter la
pose si la bande recouvre le joint. La configuration est **Implémenté** ;
la qualification et la libération matérielle restent **À valider**.

#### 2.2.1 Réconciliation ORCH-CAO-MASSE-1

La priorité courante est la complétude géométrique et massique de cette seule
configuration. Les nouveaux développements et campagnes Gazebo/PX4 sont
suspendus ; les capacités et preuves historiques restent conservées. Les
contrôles du 22 octobre ci-dessus ne s'appliquent pas aux références reprises.
Le registre courant contient **132 références et 368 occurrences**, dont
361 liens de sous-assemblages. Leur développement produit **512 occurrences
physiques et 328 couples fichier/objet source** ; aucune forme physique
invalide au contrôle exécuté. Ces nombres ne démontrent pas une complétude :
six postes embarqués restent sans détail CAO identifié et cinq occurrences
sans propriétaire massique unique résolu, après application des inclusions.

Les sources et investigations sont consolidées dans trois preuves :
[structure et propulsion](../../hardware/mecanique/cartographe/verification/orch_cao_masse_structure.json),
[équipements](../../hardware/mecanique/cartographe/verification/orch_cao_masse_equipements.json)
et [fabrication/faisceaux](../../hardware/mecanique/cartographe/verification/orch_cao_masse_fabrication.json).
Elles conservent provenance, révision, consultation, droits connus et empreinte.
La source STEP X650 et les fichiers fabricant originaux ne sont pas modifiés.
Les 73 liens OEM ont été développés en 200 feuilles, dont quatre objets sans
identité résolue ; une étiquette du kit d'achat ne sert plus de décomposition
de masse. Les variantes moteur 31228/31229 sont distinguées, deux de chaque.
La référence pré-câblée ESC 31230 ne reçoit pas les dimensions ou les 5,8 g
de la carte seule 31104. Les variantes d'hélice, leurs perçages et la matière
des colonnes de remplacement restent bloquants.

Les natifs PM08, Basler, fan 24076, GNSS, Waveshare 15817, SSD et Fujinon
évoluent en place depuis les sources disponibles. Le PM08 contient le boîtier
OEM v003 ; Basler et objectif conservent leur plan de bride optique. Les
géométries reconstruites sont partielles : les cotes déduites ou manquantes
ne deviennent pas des données fabricant. Le QS8 reste une enveloppe de
60,9 ×29,7 ×15,4 mm, avec demi-corps/joint non décrits. P76 est agrandi,
P73 dégagé et P10/P65 reçoivent les passages/fixations manquants. Le relief
de P10 libère l'ancrage voisin. Les deux axes de vis Basler et le fan sont
recalés selon les interfaces documentées ; les poses des équipements
principaux sont autrement conservées dans cette première passe.

La reprise du 26 octobre supprime les sept interférences PM08/QS8 constatées
et celle du départ F20. Le PM08 passe à (5,5 ; −39 ; 39) mm avec rotation
de 180° autour de Z ; le fusible CA01 et l'isolateur UART sont décalés.
Huit parcours de puissance suivent ces interfaces extérieures, et P73/P75
reçoivent des dégagements locaux. P64 reçoit deux passages Ø3,4 mm et deux
lamages inférieurs Ø5,8 mm, profondeur 0,5 mm. Deux vis M3×12 introduites
par dessous, deux rondelles et deux écrous au-dessus assurent le montage
nominal du PM08, à préassembler hors châssis avant pose du plateau. Le voile
G10 restant de 2,3 mm et la tenue des fixations restent **À valider**.
Le contrôle est lié aux paramètres et aux natifs dans
[la reprise appliquée](../../hardware/mecanique/cartographe/verification/orch_reprise_collisions.json).

Les réservations F37/F38 s'arrêtent à 0,55 mm de l'enveloppe QS8 et F38/F05
à 0,5 mm du boîtier PM08. Le premier point F20 est déplacé à 0,1 mm du
volume extérieur du ventilateur. Ces dégagements corrigent les pénétrations
de volumes pleins ; les demi-corps, soudures, traversées et segments de
raccordement réels restent inconnus. Aucune longueur coupée ni diminution
de masse de cordon n'est déduite de ces réservations.

Les têtes M3×16/M3×40 et les fraisures P60/P66 sont corrigées à 90° dans
leurs arbres natifs, avec huit placements recalés. Le cône de tête Ø6,72 mm
est un **gabarit théorique conservateur**, distinct du diamètre matériel
maximal publié de 5,81 mm ; le contour réel, les congés et la portée d'appui
restent à documenter. Les fraisures projet Ø6,92 mm laissent 1,14 mm de
matière au bord du passage. Les masses fournisseur restent indépendantes
de ce gabarit. La [preuve d'application](../../hardware/mecanique/cartographe/verification/orch_reprise_vis_fraisees_application.json)
et le [contrôle des BRep sauvegardés](../../hardware/mecanique/cartographe/verification/controle_reprise_collisions.json)
conservent paramètres, empreintes et contacts nominaux, sans qualification
de résistance ni libération de fabrication.

Les têtes cylindriques M2×12, M3×55 et M3×75 ont également été ramenées aux
diamètres documentaires de 3,8 mm et 5,5 mm : trois natifs et douze occurrences
contrôlés, placements inchangés. Les filets, empreintes et congés restent
simplifiés ; leur volume n'est pas utilisé pour remplacer la masse fournisseur.
La [preuve CHC](../../hardware/mecanique/cartographe/verification/orch_reprise_tetes_chc_application.json)
conserve les empreintes et paramètres avant/après.

Les 25 références fabriquées reçoivent grades et procédés **candidats** :
G10 NP500A, POM-C TECAFORM AH, aluminium 6061-T6, inox 304, SLS PA2200 et
FFF TPU 95A. Le calcul utilise les solides terminaux avec évidements et
épaisseurs ; le TPU utilise le volume de filament commandé par Cura 4.9.1,
0,15 mm, AA0.4, quatre parois/quatre peaux, remplissage lignes 100 % et débit
106 %, hors supports/adhésion/purge. La retessellation identique lie le STL
au natif ; cette recette n'est ni une impression exécutée ni une qualification.
Les tolérances matière et les masses des inserts/consommables non identifiés
restent inconnues. La [fiche Constellium 6061](https://assets.ctfassets.net/e62qtriulv4v/Snx9pjCdtrYCSlsFquBvt/e0f6b8cb7bfb0e1533e0aeec55796f03/Material_sheet_6061.pdf)
documente la densité typique utilisée pour le grade candidat de P65.

La sauvegarde utilise FreeCAD App ; les données GUI utiles et leurs fichiers
d'apparence sont conservés. Les résultats de découpe/fusion nouveaux
reprennent l'apparence de leur source ; les objets intermédiaires sont
masqués, sans réinjecter de géométrie antérieure. Les nouveaux liens
héritent des apparences source par défaut.
La réouverture dans un nouveau processus et les contrôles sur fichiers
sauvegardés sont distingués du contrôle GUI interactif non exécuté.
La [preuve consolidée](../../hardware/mecanique/cartographe/verification/controle_orch_cao_masse_1.json)
porte le résultat et les anomalies ; la définition n'est pas libérée.
Les collisions corrigées sont distinctes des interfaces PM08, QS8, GNSS,
sorties F20, prises Basler et engagements Key M, encore **À valider** dans
leurs périmètres. L'orientation de l'interface SMA GNSS reste incohérente
avec la réservation d'antenne et demande une définition documentée.
Une séparation nominale des quatre disques rotor ne démontre pas la
compatibilité des hélices réelles ni le vol.

<a id="integration-electromecanique"></a>
#### 2.2.2 Méthode réutilisable d'intégration des faisceaux — 28 octobre 2026

La skill [electromechanical-integration](../../.agents/skills/electromechanical-integration/SKILL.md)
est **Implémenté** pour préparer la future reprise des faisceaux. Elle soutient
ORCH-CAO-MASSE-1 sans reconstruire le drone ni reprendre les campagnes suspendues.
La décision est de planifier globalement les corridors, groupes compatibles,
branches et protections avant leurs solides. Le regroupement physique conserve
chaque connexion électrique. Les contraintes impératives précèdent les gains
de dispersion, fixations, encombrement, maintenance, longueur et masse.

Un planificateur C++17/Qt6Core propose des topologies bornées sur un graphe
fourni ; les helpers Python mesurent les BRep FreeCAD et préparent les copies
avec dépendances et empreintes. Le constructeur
`cable_workbench_prototype.py` est réutilisé sans modification. Les API locales
FreeCAD 1.1.3/Cables 0.3.7 ont été inspectées et exercées sur des objets
synthétiques. Le MCP installé refuse la connexion ; le repli par Python
FreeCAD dans un processus distinct a été vérifié.

Les essais historiques de splines motivent un contrôle de la courbe effective,
de ses rayons et des interférences. Un rayon échantillonné favorable ne prouve
pas une borne globale ; 22 mm reste une hypothèse candidate. Un échec natif
peut conserver un ancien solide : la vérification de reconstruction doit
écarter ce cache. Les inclusions dans une enveloppe de gaine sont distinguées
des interférences avec sa matière.

La découverte automatique de corridors, le routage complet des solides, le
packing des câbles, la certification de courbure des splines et les contrôles
physiques ne sont pas implémentés par le planificateur. Les sites proposés ne
sont pas des fixations réalisées ; les diamètres de gaine sont des bornes
d'aire préliminaires. Les critères et preuves sont dans
[DOC-VAL §12.1.11](../VALIDATION_QUALIFICATION.md#validation-skill-electromecanique).
Aucun gain ni qualification du faisceau réel ne découle de cette création.

**Autonomie de conception — 28 octobre.** La même skill applique désormais
`INVESTIGATE → DERIVE → DESIGN → SIMULATE → VERIFY → DECIDE` : une inconnue
déclenche recherche, inspection, calcul ou scénarios bornés. Les guides,
corridors, longueurs et protections hérités sont reclassés selon leur rôle
avant de devenir des contraintes de routage. Les variantes réversibles sont
arbitrées sur copie isolée ; les contraintes fonctionnelles et de sûreté
justifiées restent prioritaires. Cette évolution soutient la complétude
électromécanique du lot courant sans modifier le prototype, reprendre les
campagnes suspendues, acheter ou intervenir sur un équipement réel.

Les données distinguent mesure, documentation, calcul, estimation, hypothèse
et inconnue avec provenance ; le contrat réduit du planificateur reste
compatible et conservateur. Les liaisons mobiles demandent une étude des
degrés de liberté, butées, positions et réserves ; une amplitude inconnue
déclenche une étude paramétrique justifiée, sans qualification de fatigue.
Le journal des décisions est intégré à la preuve structurée d'expérience,
avec synthèse utile dans les documents vivants, sans registre narratif séparé.
Les verdicts de conception distinguent géométrie vérifiée, candidat
conditionnel, non-conformité, absence de contrôle et besoin de validation
physique ; ils ne remplacent pas les maturités du projet. Un seuil hypothétique
ne devient pas une exigence fournisseur par la réussite d'un calcul.

L'intervention utilisateur est réservée à une donnée indispensable demeurée
inaccessible ou à une action hors autorisation ; les tâches indépendantes
continuent. L'exploration s'arrête sur résultat suffisant, budget ou absence
d'information nouvelle, pas au premier échec. Méthode **Implémenté** ; portée
des évaluations synthétiques et limites dans DOC-VAL §12.1.11, sans extension
des capacités automatiques du planificateur ni qualification du faisceau réel.

<a id="moteur-electromecanique"></a>
**Moteur de banc — action 1, 10 novembre 2026.** Le
[moteur électromécanique](../../electromechanical_engine/README.md) met à
l’épreuve les contrôles nécessaires à la complétude CAO du lot
ORCH-CAO-MASSE-1. Le modèle système et les exigences sont gelés séparément
des variantes. La CLI explore des corridors déclarés, construit des câbles
paramétriques dans un dossier isolé et évalue les solides rouverts dans un
nouveau processus FreeCAD. Les corrections sont associées aux défauts et les
candidats admissibles sont comparés sur des objectifs mesurés. Le prototype
reste la référence du lot.

L’extracteur relève la structure et les liens natifs. Le constructeur de
banc travaille sur une représentation explicite des enveloppes, ports et
corridors. Sur le banc mobile, il sauvegarde un câble paramétrique par pose
déclarée. Le validateur mesure la longueur, le rayon et les collisions après
réouverture. Il mesure les portées entre retenues au nominal sur l’axe natif
et vérifie la présence d’une couronne fermée dans le solide de la retenue.
Le raccordement entre inventaire natif et modèle métier demande un mapping
documenté pour chaque assemblage. GO 1 clôt le développement sur les bancs.
L’intégration du prototype reste **À valider**.
[Résultats et périmètre dans DOC-VAL](../VALIDATION_QUALIFICATION.md#validation-moteur-electromecanique)

**Interfaces L2 — 12 novembre 2026.** Le banc synthétique représente deux
équipements et un cordon de quatre conducteurs. Chaque interface possède
ses repères de montage, d’accouplement et de sortie, ses corps et contacts,
sa reprise d’effort et son volume de retrait. Le natif sauvegardé rattache
les conducteurs aux terminaux Cables. La réouverture indépendante vérifie
les liens, le déplacement lors d’une réorientation et les dégagements du
banc. Le montage et l’extraction des prises réelles restent **À valider**.
[Banc et preuve native](../../hardware/mecanique/banc_interconnexion/manifest.json) ·
[Périmètre L2](../VALIDATION_QUALIFICATION.md#moteur-electromecanique-v2-l2)

**Reconception du prototype — action 3, 11 novembre 2026.** L’étude
conditionnelle compare trois familles pour la configuration sans dock :
corridors sous plateau et latéraux à équipements fixes, réimplantation
locale du PM08 et de l’isolateur pour dégager CAN1, puis regroupement
électronique si son bénéfice et sa compatibilité sont démontrés. Le
[catalogue des pistes](../verification/cartographe_action3_architectures.json)
porte les hypothèses et leurs critères d’exclusion. La suite dépend d’une
baseline complète réouvrable et d’un mapping métier des ports et enveloppes.
La [validation de l’action 3](../VALIDATION_QUALIFICATION.md#cartographe-action3)
porte les mesures et les limites du GO 2. L’architecture reste **À valider**.

**Reprise sur copie corrigée.** La branche OEM de la copie utilise quatre
réservations nominales dérivées de la colonne Ø5 × 90 mm de référence, avec
alésage simplifié. Les quatre occurrences actives et leurs poses sont
conservées. La copie complète sauvegardée et rouverte sert de référence
géométrique à la reprise A1. Les limites de la copie et des premiers
contrôles de faisceau sont dans [DOC-VAL](../VALIDATION_QUALIFICATION.md#cartographe-action3).

Le trajet F35 essayé sur une copie issue d’A1 contourne au sud le volume
nominal de retrait de CAN1. L’assemblage a été rouvert avec ce trajet.
Retenue haute, jeu à F25/P75 et déverrouillage restent **À valider**.
[Contrôles CAN1 et F35](../VALIDATION_QUALIFICATION.md#cartographe-action3)

La copie consolidée regroupe le nouveau F16 à deux rayons, le trajet
F25 abaissé sur le chant est avec P85 et le contournement F35 de CAN1.
Les jeux statiques, la comparaison à 53 axes et les limites de montage
sont consignés dans [DOC-VAL](../VALIDATION_QUALIFICATION.md#cartographe-action3).

**Contrat V2 — L0, 12 novembre 2026.** Le raccordement entre le modèle
métier et la CAO reste **Planifié**. L1 prend l’assemblage actif et la copie
consolidée comme deux fermetures XLink distinctes, identifiées par leurs
empreintes complètes. Les réservations OEM de la copie sont traçables et
leur applicabilité reste **À valider**. Les routes, segments, enveloppes et
poses sont reliés aux cordons, avec une preuve de provenance par donnée.
[Contrats V2](../electromechanical_v2/DATA_CONTRACTS.md) ·
[Référentiel L0](../electromechanical_v2/BASELINE_MANIFEST.json)

<a id="geometrie-cartographe-go3a"></a>
**Architecture H-01 — GO3A conditionnel, 14 novembre 2026.** Sur le
prototype sans dock, préserver le porteur P75, les supports d’antenne et
les équipements ORCH. Affecter la puissance aux passages protégés de
dessous et de chant qui restent compatibles, les liaisons temporelles et RF
à leurs corridors distincts. Instruire F35 au sud de CAN1, F25 au chant est
de P66 avec P85 candidat, et une réserve séparée pour F16/M8. Le témoin F16
R50/R24 avec décalage Z10 fournit une géométrie exploratoire. Le cordon,
les efforts, la tolérance, la cinématique continue et l’applicabilité du
modèle OEM restent **À valider**. Réserver le chant ouest pour le diagnostic
en tenant compte des sorties de l’isolateur, de la PDB et des accès depuis
la baie. [Variantes et mesures](../verification/go3a/GO3A_VARIANTS.md) ·
[Conditions de réception](../verification/go3a/GO3A_HANDOFF.md)

<a id="cartographe-go3a-architecture"></a>
**Portefeuille GO3A V2.1 — À valider.** Comparer le service direct de
l’isolateur déplacé (H-03), les sorties de cordons par faces à équipements
fixes (H-02) et le déport passif à équipements fixes (H-01). Prioriser
H-03 afin de tester l’obstruction PDB avec une seule réimplantation et
les interfaces de référence. Réserver au plus 5 h, 4 h et 3 h
respectivement. Les trois familles reprennent TELEM1, le témoin F35 au
sud et la réservation F25/P85 sur la même copie de l’actif. PM08, PDB,
CA01 et porteuse restent à leur pose de référence. Les appuis et les
gestes de dépose sont contrôlés avant de retenir la géométrie. Toute
réimplantation régénère les deux extrémités mobiles de F40/F41 et
leurs volumes de service, avec contrôle inverse des incidences après
sauvegarde et réouverture.

La comparaison utilise les boîtes gelées `bay`, `above` et
`sous_P66_emprise_stricte` de l’actif. Vérifier d’abord contraintes et
accès conjoints, puis comparer les métriques communes, dont encombrement
avec fiches, masses nettes, supports et maintenance. Les résultats du
couple historique A/par faces renseignent seulement ce couple. Le
périmètre actif/copie consolidée possède son propre témoin. Les sept
paires B.2 en échec restent à instruire sur chacune des copies construites.
[Plan GO3B et mesures](../verification/v21_go3a_candidates.json) ·
[Prise en main](../electromechanical_v2_1/05_GO3A_ARCHITECTURES.md)

<a id="cartographe-go3b-reconstruction"></a>

**Reconstruction GO3B V2.1 — Implémenté, 17 novembre 2026.** Six
variantes natives des familles H-03, H-02 et H-01 ont été sauvegardées
et rouvertes sur une copie du gel actif. Les huit tentatives incluent deux
échecs de génération H01-A/B, corrigés sur copies neuves et conservés.
Une neuvième expérience construit la consolidée des seules corrections
compatibles F12/TELEM1, F35 au sud et F25/P85. Le plafond de 12 expériences
laisse trois crédits inutilisés après les rejets des deux configurations
de chaque famille et la contre-validation de la consolidée.
[Variantes, paramètres et budget](../verification/v21_go3b_candidates.json)

La réception donne `GO3B_CAO_NO_GO_MOTIVE`. Chaque variante conserve
les sept défauts B.2 et présente une intersection supplémentaire mesurée.
H03-A recoupe F40/P72 à 18,258 mm³. H03-B recoupe aussi isolateur/P72
à 146,756 mm³. Les appuis ASSUMED H03 laissent 0,300 mm au module
et recoupent P72 à 109,734 mm³. Les deux hypothèses sont rejetées.
Les H02 recoupent F40/P72 à 42,676 mm³. Les H01 recoupent F40/P73
à 618,710 ou 78,781 mm³. Les corps coudés, raccords passifs et ferrites
demeurent des réservations candidates, avec raccordement matériel
**À valider**. Les défauts comptés sont des bornes inférieures de
couvertures différentes. [Contre-validation](../verification/v21_go3b/independent_evidence.json)

La consolidée relocalisée compte 138 natifs et 53 axes, avec sauvegarde
puis réouverture sans lien rompu ni objet en erreur. La longueur cumulée
des axes passe de 12 125,900 à 12 143,722 mm, la baie de 4 341,486 à
4 257,184 mm et le dessus de 2 421,421 à 2 318,252 mm dans les zones
gelées. Sous P66 stricte et en cote haute de gaine, les valeurs restent
451,202 et 173,278 mm. Les branches F40/F41 historiques restent à
98,871 et 53,639 mm des réservations de face TTL/USB-B. La masse totale,
le centrage, l’union des volumes connectés exacts et les gestes réels
restent inconnus. [Revue d’interface](../verification/v21_go3b/interfaces_review.json)

Les copies, échecs et paramètres sont conservés sous
`verification/go3b/artefacts/`, avec la nomenclature physique dérivée,
la nomenclature d’interconnexion, les vues et les essais GO4 référencés
dans le manifeste. Les 137 natifs et les cinq auxiliaires sources restent
identiques au préflight. La prochaine expérience doit définir un appui
effectivement ancré pour l’isolateur et un trajet F40 dégagé des retenues
P72/P73, tout en traitant les défauts Airy et F37_POS/P73. La tenue et
l’intégrité électriques attendent les essais sur exemplaires.
[Manifeste](../verification/v21_go3b_manifest.json) ·
[Rapport demandé](../electromechanical_v2_1/06_GO3B_REPORT.md)

**Interfaces natives V2.1 — À valider.** La copie XLink relue donne 108 poses
d’équipement pour 142 côtés documentaires. Les 106 bouts WireFlex observés
restent sans attache native à un contact. L’intégration d’une fiche demande
les repères du corps, de la face d’accouplement, de la sortie de fil et les
enveloppes du geste de retrait et d’accès à l’outil. Sur W16/B, le STEP
USBFireWire RR-ASMUK-20GRHF donne le corps de la fiche candidate. À la pose
étudiée, le corps moulé est dégagé sur les cinq paires contrôlées. Le pack
recoupe les gabarits conservateurs de retrait et d’outil. Leur résolution
dépend de la course réelle, des vis et du mouvement caméra, encore **À valider**.
[Preuve V2.1](../verification/v21_connector_tests.json)

Le [rejeu XLink](../VALIDATION_QUALIFICATION.md#preuve-xlink-v21) associe la
pose et la géométrie à un chemin d’occurrence complet, y compris pour une
pièce répétée. Il mesure les solides sauvegardés sur la copie de 137 natifs.
Les seuils de criblage, les solides OEM simplifiés et les gabarits de
connectique limitent l’interprétation des paires. Les retenues, l’accès aux
fiches et les enveloppes de mouvement restent **À valider**.

<a id="reconstruction-faisceaux"></a>
Le [gel XLink V3-A](../verification/v3/a/native_receipt.json) reproduit sur
deux emplacements les 137 natifs du prototype et distingue définitions
partagées, occurrences et réservations géométriques. Pour F40/F41, l’appui
de l’isolateur, son ancrage, les reprises P72/P73 vers P66, les surfaces
candidates et les volumes de retrait portent leur niveau de preuve dans
[les autorités du graphe](../electromechanical_v3/cartographe.json). La
tenue en charge, les domaines de modification et le montage restent
**À valider**.

#### 2.2.3 Reconstruction des faisceaux sur copie

<a id="faisceaux-modulaires"></a>
**Faisceaux modulaires sur les interfaces existantes — 9 novembre 2026.**
La [copie modulaire](../../hardware/mecanique/cartographe_faisceaux_modulaires/assemblages/Prototype_Cartographe.FCStd)
est une définition **À valider** pour ORCH-CAO-MASSE-1. L'unité de montage est
le sous-ensemble déposable. Les 53 trajets sont répartis en onze modules.
Les quatre bras sont indépendants et les deux cordons de la caméra suspendue
gardent des boucles séparées. Les chemins WireFlex sont éditables dans les
fichiers de câble et restent des objets de construction. Les gaines et les
retenues physiques proviennent de définitions distinctes dans la recette.

L'[audit du candidat précédent](../../hardware/mecanique/cartographe_faisceaux_modulaires/verification/audit_baseline.json)
identifie les cinq pièces orange, leurs ancrages et les dépendances introduites
par le constructeur. P72/P73 liaient plusieurs étages. P75 ajoutait deux
niveaux de traverses et ses œillets se multipliaient avec les passages.
P77 retenait la réserve du cordon USB de diagnostic. P78 portait la remontée M8.
Les cinq occurrences sont retirées. Le
[relevé des interfaces](../../hardware/mecanique/cartographe_faisceaux_modulaires/verification/corridors_structure.json)
compare les solutions à partir du chant et des lumières de P64, des colonnes
P68, des points de fixation libres et des tubes OEM.

| Retenue locale | Interface et principe de pose |
|---|---|
| Patte MIDI P81 | Deux trous M3 de P60 aux axes X88 et X96, Y−43 mm. Patte PA12 SLS candidate, pose avant la batterie. Les deux bandes existantes serrent le boîtier sur la tablette locale. |
| Deux pinces P82 | Chant sud de P64 à X−30 et +35 mm. Corps POM usiné candidat, insertion depuis le sud, vis de pression M3 à patin isolant côté inférieur et bande ouvrable côté faisceau. |
| Quatre bandes départ bras | Les doubles lumières déjà présentes dans P64 servent de passage. Pré-enfiler les bandes avant pose de P64 et fermer depuis le dessus. |
| Clip P83 | Colonne P68 de l'avionique, axe (60,37), diamètre nominal 6 mm. Clip TPU 95A candidat, insertion latérale du corps puis du câble F12. |
| Pince P84 au départ de F41 | Chant ouest de P64 à Y24 mm, siège à Z54 mm. Pince POM usinée candidate, insertion depuis l'ouest, vis de pression sous P64 et bande ouvrable à garniture souple. |
| Deux supports d'antenne P70 repris | Colonnes P68 aux axes X−60 et Y±37 mm. Douilles souples fendues, posées latéralement, à course axiale bornée par les faces existantes. Le dipôle nord se clipse dans son support. Le dipôle sud a sa propre bande. |
| Selles conservées P79/P80 | Douze selles locales sur les tubes OEM Ø20, rayons de 180, 250 et 280 mm. Garder les gorges distinctes, libérer les bandes et les connexions avant le pliage ou la dépose d'un bras. |

La [définition des supports et protections](../../hardware/mecanique/cartographe_faisceaux_modulaires/verification/integration.json)
donne les occurrences, poses, procédés candidats et interfaces. La
[reprise RF et USB](../../hardware/mecanique/cartographe_faisceaux_modulaires/verification/integration_radio.json)
porte les deux supports d'antenne et les pièces du départ F41. Le
[registre des modules](../../hardware/mecanique/cartographe_faisceaux_modulaires/verification/modules_electriques.json)
porte la nomenclature, les tronçons, les branches et la séquence de
pose, dépose et réparation par sous-ensemble.

| Mesure à périmètre comparable | Candidat précédent | Copie modulaire |
|---|---:|---:|
| Supports fabriqués dans SA07 | 17 | 17, dont 12 selles conservées et 5 pièces nouvelles |
| Références de supports fabriqués dans SA07 | 7 | 6 |
| Volume de matière des supports fabriqués dans SA07 | 222,0 cm³ | 30,5 cm³ |
| Grandes structures P72/P73/P75 | 3 | 0 |
| Occurrences de supports de faisceau, quincaillerie et boucles modélisées, tous sous-assemblages | 75 | 58 |
| Protections ouvrables candidates | 4 | 2 |
| Longueur cumulée des axes | 12 207,3 mm | 11 124,7 mm |

F41, F06 et trois commandes de bras ont été redessinés. Les autres axes servent
de réservations. La longueur cumulée est celle des axes CAO. Les coupes
et réserves de service dépendent des terminaisons et du montage réel.
Le volume de matière provient des solides sauvegardés. Il exclut les deux
supports d'antenne modifiés dans SA06 et ne donne pas la masse du faisceau.
Les deux protections F38 de 105 mm ont une composition explicite dans la
recette. Chaque tronçon couvre un seul câble de puissance Ø6,5 mm. La gaine
est ouvrable à la maintenance et peut être installée après les prises.

Les vues séparent le
[châssis](../../hardware/mecanique/cartographe_faisceaux_modulaires/verification/vues/01_structure.png),
les [faisceaux](../../hardware/mecanique/cartographe_faisceaux_modulaires/verification/vues/02_faisceaux.png),
les [retenues](../../hardware/mecanique/cartographe_faisceaux_modulaires/verification/vues/03_retenues.png)
et le [détail assemblé](../../hardware/mecanique/cartographe_faisceaux_modulaires/verification/vues/04_integration.png).
Les planches de référence isolent les
[anciens supports](../../hardware/mecanique/cartographe_faisceaux_modulaires/verification/audit_baseline_supports.png)
et les [interfaces avant reprise](../../hardware/mecanique/cartographe_faisceaux_modulaires/verification/audit_baseline_structure.png).

Les retenues locales n'assurent qu'une partie du maintien. La suppression
des cinq pièces invalide 263 affectations historiques de station, dont des
appuis qui conditionnaient les trajets longs. Les travées hautes et la décharge
de traction caméra restent à résoudre. La première copie a laissé les deux
supports P70 sans ancrage. La reprise les rattache à P68, avec un contrôle
des [butées axiales nominales](../../hardware/mecanique/cartographe_faisceaux_modulaires/verification/validation_radio.json).
L'effort d'encliquetage, les jeux réels et la tenue de la bande sud restent
**À valider**. Le trajet court F41 suppose un cordon de remplacement et des
retenues supplémentaires dans la montée et la traversée. Les valeurs de coupe et la masse
complète demeurent ouvertes. Les résultats et anomalies de la copie sont
regroupés dans [DOC-VAL](../VALIDATION_QUALIFICATION.md#validation-faisceaux-modulaires).
Le [relevé du maintien haut](../../hardware/mecanique/cartographe_faisceaux_modulaires/verification/releve_maintien_haut.json)
consigne l'alternative sur P66 pour F04_1, avec accès aux vis conditionné
par le préassemblage et dépose en place encore ouverte.

<a id="refonte-faisceaux-globale"></a>
**Refonte globale du 9 novembre 2026 — Implémenté sur copie, À valider.**
L'[assemblage candidat](../../hardware/mecanique/cartographe_faisceaux_refonte/assemblages/Prototype_Cartographe.FCStd)
organise les 53 parcours en 21 groupes physiques. Le
[graphe](../../hardware/mecanique/cartographe/verification/refonte_faisceaux/graphe_physique.json)
identifie les gaines, les branches terminales, les appuis et les tronçons
empruntés par chaque câble. La [partition et ses règles](../../hardware/mecanique/cartographe/verification/refonte_faisceaux/architecture.json)
couvrent les étages énergie et avionique, les quatre bras, la perception, la
navigation, la radio et la sécurité. Les groupes d'arbre indiquent un corridor
ou une fonction commune. La présence d'une paroi native identifie une gaine
effectivement représentée. Les conducteurs y conservent des axes séparés.

| Décision dans la copie | Justification et limite |
|---|---|
| Protéger les quatre commandes MAIN sur 8 mm au-delà des stations de maintien du peigne | Déporter deux sommets de F04_1 de 6 mm en X et dégager localement P75. Les autres branches et les terminaisons restent en place. Les allongements plus grands ont rencontré P75 ou une autre commande. |
| Ajouter 30 mm de gaine au nord de l'avionique pour F24A/F24C | F24A transporte PPS et retour, F24C la référence 3,3 V et son retour. Ouvrir localement P75 et conserver les branches vers leurs ports. Le mélange avec la sortie PWM F33 à l'est reste écarté. |
| Étendre la protection aller-retour F38 de 80 à 105 mm | Réserver un passage ovale dans P73. La variante 139 mm sur le guide précédent recoupe davantage le guide. Courant, thermique et fixation restent à vérifier sur la fourniture choisie. |
| Protéger ensemble les deux NTC sur 9 mm | Les deux voies du BMS traversent la même fenêtre. La coupe BRep locale exclut une portion éloignée des mêmes câbles qui faussait le contrôle précédent. Les positions des sondes et les retenues P62 sont conservées. |
| Réutiliser les douze selles P79/P80 et leurs gorges distinctes | Les quatre bras conservent leurs branches propres de puissance, de commande et de balisage. Les efforts de fixation et le dégagement au pliage restent à vérifier. |
| Séparer POWER1/POWER2, RF, sécurité, GNSS et boucles caméra aux interfaces sensibles | Les corridors voisins restent exploitables. Le gain de 9 mm testé sur GNSS ne ferme pas la séparation fonctionnelle ni le couplage avec PPS. L'éclatement Airy garde trois branches et son intérieur reste à caractériser. |

Les vues de l'[ensemble du drone](../../hardware/mecanique/cartographe/verification/refonte_faisceaux/controles_vues/01_ensemble.png),
des [troncs et retenues](../../hardware/mecanique/cartographe/verification/refonte_faisceaux/controles_vues/02_troncs_retenues.png),
des [liaisons de perception](../../hardware/mecanique/cartographe/verification/refonte_faisceaux/controles_vues/03_camera_airy.png)
et des [quatre gaines](../../hardware/mecanique/cartographe/verification/refonte_faisceaux/controles_vues/04_gaines.png)
sont issues des solides enregistrés. Le jeu de 0,25 mm visé entre la paroi
et le guide est nominal. Les quatre emplacements de bandes du corridor
nord demandent une nouvelle définition de retenue. Le réemploi des ponts
F38 aux abscisses −5 et 40 mm conserve leurs appuis modélisés.

Les coupes de guide sont des enlèvements locaux. La tenue des sections
résiduelles et des attaches, la pose et la dépose des gaines, la réserve de
service, les tolérances et la masse complète du faisceau restent **À valider**.
Le modèle reprend F16 à R50 mobile et R24 fixe. Pour la famille candidate,
les valeurs fabricant de 48 mm en flexion continue et 22 mm en statique
s'appliquent sous réserve de la référence effectivement achetée. Le parcours
de 494,608 mm dépasse de 66,108 mm la longueur utile estimée pour le cordon
catalogue de 508 mm, qui comporte de plus un Type A droit. Un cordon sur mesure
de l'ordre de 600 mm constitue une estimation de travail. Sa prise, son rayon,
la tenue USB3 et la fatigue demandent une confirmation spécifique.
[Fiche USBFireWire](https://www.usbfirewire.com/parts/rr-asmuk-xxgrhf.html).

Le M8 conserve son tracé nominal de 296,877 mm. La référence candidate
1522341 donne un rayon de 52 mm. Les variantes améliorant la faisabilité de
la courbure en mouvement déplacent le risque vers la semelle et la rondelle
du BMS. La mesure de course, de sortie de fiche et de marge d'installation
autour de ces deux obstacles précède la sélection d'une autre boucle.
[Fiche Phoenix Contact](https://www.phoenixcontact.com/en-us/products/sensoractuator-cable-sac-6p-m-8mr-15-pur-sh-1522341).

Les [résultats et limites](../VALIDATION_QUALIFICATION.md#validation-refonte-faisceaux)
définissent la portée de cette copie. La prochaine décision d'intégration
dépend des longueurs et interfaces réellement disponibles, de la mesure de
course caméra et de l'essai de montage des protections. Le modèle courant du
prototype conserve son rôle de référence de la configuration active.

**Reprise du 8 novembre 2026.** F16, le guide P73 et la protection F38 sont
**Implémentés** dans l'[assemblage candidat isolé](../../hardware/mecanique/cartographe_faisceaux_autonome/assemblages/Prototype_Cartographe.FCStd).
L'intégration reste **À valider**. Les 53 parcours conservent leurs identifiants
et leurs terminaisons. La protection est une occurrence mécanique distincte.
Les mesures, empreintes et décisions sont reliées dans le
[bilan technique](../../hardware/mecanique/cartographe/verification/reconstruction_faisceaux/bilan_autonomie.json).

**Extension au faisceau complet.** Les 53 parcours de l'assemblage ont été
reconstruits en mémoire depuis leurs natifs, avec contrôle des liens, des
extrémités et des volumes. Cette revue a fait apparaître des supports restés
sur les anciens axes après la reprise de la distribution. P73 et P75 sont
réalignés dans la copie pour cinq stations F08_AVAL et deux F05_NEG. Les axes
de ces deux câbles et leurs terminaisons sont conservés. Les sept stations
coïncident désormais avec les axes au nominal. Le jeu avec les guides vaut
0,20 mm pour F08 et 0,50 mm pour F05_NEG. Le montage des colliers reste à
vérifier. Sur P73, le premier essai croisait le châssis, la platine avionique
et F08. Le pied F05 a été déplacé de X25 à X20 et le sommet de la console
F08 à X5 a été abaissé à Z81 pour libérer ces passages.

Les trois variantes M8 à sortie droite et R52/R56/R60 ont été écartées après
mesure des recouvrements avec la semelle, une rondelle et P78. Les rayons
exploratoires R28/R35/R42 du tronc Airy interfèrent avec P72. Les chemins
existants restent les candidats nominaux de ces cordons. L'étude de montage
et de mouvement du M8, ainsi que la définition de l'éclatement Airy, restent
ouvertes. Les positions de colliers dont le point de référence reste écarté
de l'axe sont identifiées par liaison, avec distinction entre points propres
à un câble et points communs de peigne.
[Preuve des 53 parcours et variantes](../../hardware/mecanique/cartographe/verification/reconstruction_faisceaux/bilan_faisceau_complet.json).

Le F16 retenu est un câble natif sur deux parcours WireFlex raccordés par
CompoundPath. Il mesure **494,608 mm** sur l'axe, dont 315,440 mm entre la
prise caméra et la première retenue fixe. Ses arcs valent R50 dans cette zone
mobile et R24 au-dessus. Les limites publiées par USBFireWire pour le cordon
de référence sont respectivement 48 et 22 mm. L'axe s'allonge de 69,434 mm
par rapport à la baseline. Il faut confirmer un cordon sur mesure avec les
deux sorties Up. Avec la même allocation de 79,5 mm aux extrémités, 574,1 mm
est une estimation de longueur hors tout. La convention de mesure, les
tolérances, les dégagements des surmoulages et la réserve de montage restent à établir.

[Projection de F16 et coupe de la protection F38](../../hardware/mecanique/cartographe/verification/reconstruction_faisceaux/vues/04_autonomie_F16_F38.png).

Les extrémités et axes de sortie sont les interfaces conservées. Les huit
stations de guidage provenaient de l'ancien parcours et sont modifiables.
Trois doigts P73 aux niveaux −45, 0 et 35 mm sont retirés de la fusion native.
La station V75 borne la zone mobile, avec 25 mm de droit en amont du collier.
Les quatre stations du P75 sont conservées. Le choix R50/X200/Z0 privilégie
une emprise latérale de boucle plus faible et 25 mm de droit à V75. X200/Z10
et Z20 ramènent cette longueur à 15 et 5 mm. Les 24 variantes et leurs rejets
sont documentés dans le bilan. Au Type A, le droit nominal de 1,05 mm impose
de vérifier la transition réelle du surmoulage avant fabrication.

La platine suspendue porte Airy, Basler, l'objectif et les deux prises mobiles.
Quatre appuis Sorbothane et quatre tampons de rebond autorisent des déplacements
et rotations couplés. La compression statique documentaire ne donne pas la
course maximale. Sur 27 poses hypothétiques à longueur F16 constante,
16 présentent une intersection entre éléments rigides du bloc suspendu et
équipements fixes. Le +X de 1 mm atteint notamment les supports P17 avec les
vis P10. En +Z de 1 mm, une retenue P10 atteint un support. Le pivot utilisé
est le centre géométrique choisi pour le calcul. La course réelle, avec masse,
précharge, efforts des câbles et butées, reste inconnue. Les poses et les
limites de la méthode figurent dans [DOC-VAL](../VALIDATION_QUALIFICATION.md#validation-reconstruction-faisceaux).

Pour F38, deux ponts locaux relèvent de 2 mm le dessous des rails P73 au-dessus
du tronçon commun. Les extrémités des rails restent en place. La paroi ovale
de 80 mm représente une gaine textile ouvrable candidate, avec enveloppe
extérieure 19,8 × 9,8 mm et paroi idéale 0,9 mm. Le jeu nominal est de
0,60 mm avec le guide et de 0,75 mm avec chaque conducteur. Les stations
communes X −5 et +40 mm restent à matérialiser par des colliers adaptés.
L'ouverture, le recouvrement, les tolérances, les contraintes du pont et
le montage doivent être vérifiés sur le produit réel. Les sept autres groupes
sont traités dans [DOC-ELEC](ARCHITECTURE_ELECTRIQUE_RESEAUX.md#regroupements-faisceaux-autonomie).

**Baseline conservée du 28 octobre 2026.** Les résultats qui suivent décrivent
la copie initiale et l'essai R23,5 séparé.

**Implémenté : inventaire, architecture conditionnelle, copie isolée et prototype
paramétrique F16. Reconstruction globale non réalisée ; intégration À valider.**
Cette mission soutient ORCH-CAO-MASSE-1. Le problème est la dispersion physique
des câbles et leur maintenabilité, sans modifier leur connectivité. La copie
réversible permet de mesurer les propositions sans publier une nouvelle
configuration du drone. L'arrêt est la porte F16 et la justification des
cohabitations ; un gain de rayon statique ne suffit pas à franchir cette porte.

La [copie complète](../../hardware/mecanique/cartographe_faisceaux/assemblages/Prototype_Cartographe.FCStd)
conserve l'assemblage initial et ses liens. Les 143 fichiers du
[reçu d'isolation](../../hardware/mecanique/cartographe_faisceaux/experiment.json)
restent identiques aux sources ; les originaux, `cable_workbench_prototype.py`
et ses sorties existantes n'ont pas été écrasés. Le
[candidat F16 séparé](../../hardware/mecanique/cartographe_faisceaux/verification/candidats/F16_ARCS_R23_5.FCStd)
contient WireFlex, profil circulaire et ArchCable paramétriques. Il n'est lié
ni au prototype actif ni à la copie d'assemblage conservée.

L'[inventaire et la topologie](../../hardware/mecanique/cartographe/verification/reconstruction_faisceaux/analyse_connectivite.json)
distinguent 53 parcours CAO, 31 postes BOM associés, 43 entrées de liaisons du
registre (incluant internes, sol et retraits) et 26 postes équipements.
Ces comptages ne sont pas interchangeables. Le tronc Airy et ses branches,
le cordon M8 multiconducteur et les enveloppes triphasées ne doivent pas
devenir artificiellement des câbles commerciaux supplémentaires.

**Architecture cible conditionnelle.** Les gaines principales candidates
regroupent les paires aller/retour protégées QS8–PM08, PM08–PDB et batterie–QS8.
Les troncs secondaires candidats concernent NTC1/2, F24A/B/C, F33/F35,
F21/F36 et éventuellement F16/M8. Chaque groupe, destination et condition
est explicite dans l'inventaire. Les quatre bras conservent des passages
distincts pour puissance, phases, commande et LED sur des supports communs
à étudier ; les deux alimentations de vol et la frontière isolée UART restent
distinctes. Aucune proximité géométrique n'a été transformée en autorisation CEM.
Le planificateur conserve les 53 routes mais retourne trois propositions
`unresolved` : les corridors observés ne démontrent ni largeur libre ni montage.
Les alternatives A1 (retenues locales), A2 (troncs fonctionnels) et A3
(protection caméra) restent **Planifié / À valider**.

Le [prédimensionnement des huit gaines](../../hardware/mecanique/cartographe/verification/reconstruction_faisceaux/dimensionnement_gaines.json)
utilise les diamètres CAO, un remplissage hypothétique de 40 % et des offsets
de disques alignés explicites. Les diamètres intérieurs candidats sont
14,534 mm pour chacune des trois paires de puissance, 4,025 mm pour les NTC,
7,200 mm pour F24A/B/C, 5,367 mm pour F33/F35, 6,277 mm pour F21/F36 et
11,968 mm pour F16/M8. Ce sont des enveloppes de calcul, pas des références
achetables : paroi, tolérances, matière, diamètre extérieur, thermique et
masse restent inconnus. Une gaine ouvrable est à étudier pour les cordons
préterminés. Aucun solide de gaine commune n'est présenté comme installé.

**Comparaison F16 à périmètre identique.** Les huit stations historiques et
leur tolérance documentaire de 0,6 mm sont conservées. Les axes terminaux
comparés sont des axes candidats issus du parcours initial, pas une mesure
indépendante des connecteurs réels.

| Critère mesuré | F16 initial | Candidat isolé R23,5 |
|---|---:|---:|
| Longueur de l'axe effectif | 425,173842 mm | 425,855847 mm |
| Rayon minimal analytique | 22 mm | 23,5 mm |
| Stations respectées | 8/8 | 8/8 |
| Réserve sur longueur utile documentaire 428,5 mm | 3,326158 mm | 2,644153 mm |
| Solide frais puis réouvert | valide | valide |
| Intersections positives, 360 autres occurrences, seuil 0,0001 mm³ | 0 | 0 |
| Calculs de collision F16 non conclus | 0 | 0 |
| Distance minimale, contacts compris | 0 mm | 0 mm |
| Contacts nominaux avec la structure | 2 | 0 |
| Contacts nominaux avec les connecteurs | 2 | 2 |

Le gain local est la suppression des contacts avec `OEM_Part__Feature066`
et `OEM_Part__Feature100`, au prix de 0,682005 mm de longueur supplémentaire.
La [preuve F16](../../hardware/mecanique/cartographe/verification/reconstruction_faisceaux/comparaison_f16.json)
ne démontre aucune marge vibratoire. Le fournisseur du
[RR-ASMUK-20GRHF](https://www.usbfirewire.com/parts/rr-asmuk-xxgrhf.html)
documente 22 mm statique et 48 mm en flexion continue. Le départ caméra est
explicitement décrit comme souple ; sa course et les conditions de flexion
ne sont pas établies. Les deux chemins ne satisfont pas 48 mm si cette
condition s'applique. R48 uniforme sur la polyligne initiale est infaisable
dès le premier segment de 22,215 mm ; cela ne prouve pas l'impossibilité
d'une autre boucle 3D. Les splines historiques rejetées ne sont pas reprises.

**Bilan global avant/après.** « Après » désigne ici la copie conservée,
et non une reconstruction globale prétendument acceptée.

| Critère | Initial | Copie conservée |
|---|---|---|
| Parcours CAO / identité des routes | 53 | 53, identiques |
| Nombre de connexions électriques embarquées réconciliées | NON_VERIFIE | NON_VERIFIE |
| Nombre de faisceaux physiques | NON_VERIFIE ; 31 postes BOM ne sont pas ce nombre | inchangé, NON_VERIFIE |
| Gaines communes réellement installées | NON_VERIFIE | aucune nouvelle ; total NON_VERIFIE |
| Longueur cumulée des axes de câbles | 12 125,900339 mm | 12 125,900339 mm |
| Longueur physique mutualisée | NON_VERIFIE | NON_VERIFIE |
| Dérivations physiques et fixations montées | NON_VERIFIE ; inventaire nominal disponible | identiques, NON_VERIFIE |
| Rayon minimal analytique du périmètre CAO | 4 mm, admissibilité fournisseur non démontrée | 4 mm |
| Intersections des volumes nominaux | 6 recouvrements internes à la zone d'éclatement Airy ; 0 hors cette zone, intérieur réel NON_VERIFIE | identiques ; 159 paires interrompues résolues à la reprise |
| Dégagements minimaux / conformité | contacts à 0 mm observés ; minima manquants et critères physiques NON_VERIFIE | mêmes limites ; aucune marge dynamique démontrée |
| Solides câbles frais | 53/53 valides | équivalence volumétrique contrôlée |
| Masse complète et coût de montage | NON_VERIFIE | NON_VERIFIE |

Les longueurs sont des axes modélisés, sans libération de longueurs de coupe.
Le graphe polyligne du planificateur mesure 12 782,583 mm et ne remplace pas
ces mesures natives. Ses 423 sites ne sont pas des fixations fabriquées.
L'inventaire des occurrences, poses, obstacles et contrôles est dans
[baseline_volumes.json](../../hardware/mecanique/cartographe/verification/reconstruction_faisceaux/baseline_volumes.json) ;
les résultats consolidés et les réserves sont dans
[DOC-VAL](../VALIDATION_QUALIFICATION.md#validation-reconstruction-faisceaux).

Les [vues globales comparables](../../hardware/mecanique/cartographe/verification/reconstruction_faisceaux/vues/01_global_initial_copie_conservee.png),
les [stations et obstacles F16](../../hardware/mecanique/cartographe/verification/reconstruction_faisceaux/vues/02_f16_stations_obstacles.png)
et la [comparaison du candidat](../../hardware/mecanique/cartographe/verification/reconstruction_faisceaux/vues/03_f16_initial_candidat.png)
sont des tessellations BRep avec transparences indiquées. Aucun rendu de
gaines communes ou de dérivations nouvelles n'est fourni comme réalisation,
puisqu'elles ne sont pas construites.

**Prochaine décision.** Confirmer course et retenues du bloc caméra,
référence et longueur utile du cordon, puis essayer une boucle respectant le
rayon applicable ou revoir le cordon et les guides. Pour chaque gaine,
confirmer courants, retours, blindages, dissipation, indépendance fonctionnelle,
référence de protection et séquence de montage. Les volumes de passage des
prises, outils, hélices et mouvements restent à contrôler. Ces données
conditionnent la phase D ; aucune qualification physique, fabrication ou
modification des originaux ne découle de ce résultat partiel.

<a id="modele-gazebo-prototype"></a>
<a id="bancs-spatiaux-c3"></a>
#### Bancs synthétiques de recherche de cheminement

V3-INT.3 utilise deux fermetures C.3 et un banc Workholding P64 distinct.
La contre-mesure spatiale vérifie les arcs, les volumes et les engagements
après réouverture. Les deux supports Workholding ont des poses et des
cotes signées propres. Le statut **Qualifié** porte sur les copies privées
de ces bancs sous Windows amd64. Les cotes d’appui, le choix du porteur
P64 ou P66 et la réception du cartographe réel restent **À valider**.
[Qualification intégrée](../VALIDATION_QUALIFICATION.md#cartographe-v3-int3-cloture) ·
[Relevés nécessaires](../verification/v3/a6/physical_readiness.json)

La collecte V3-A.7 prépare deux dossiers distincts pour P64 et P66. Elle
demande les témoins d’appui et de fixation, les états TTL/USB, leurs volumes
balayés et la course complète sur gabarit de batterie inerte. Les
références XLink distinguent le porteur d’énergie du porteur d’avionique.
L’appui applicable et toutes les valeurs physiques restent **À valider**
sur le lot observé. [Guide de collecte](../verification/v3/a7/operator_guide.md)

Les deux bancs V3-C.3 relient une racine FreeCAD à des références
externes conservées en chemins relatifs. L’équipement mobile porte deux
datums de sortie indépendants. Le second banc ajoute un niveau
d’assemblage autour de l’équipement et place l’obstacle sur le trajet du
second câble. Chaque câble garde ses extrémités électriques, sa réserve
de service et sa propre géométrie de gaine. La pose étant à altitude
fixe, le corridor volumique permet de contourner un obstacle et de
revenir dans la bande d’appui nominale.

Les platines sont des options de banc scellées. Une retenue est
admissible avec mesure de l’aire d’appui sur la face porteuse, de sa
normale, de la zone d’ancrage et du contact avec les gaines prévues.
Ces choix ont le statut **Qualifié** pour les deux bancs synthétiques éprouvés.
[Contrôles et portée](../VALIDATION_QUALIFICATION.md#cartographe-v3-c3)

##### Appui plan et pose variable sur les bancs V3-C.4

Le [profil XLink principal](../electromechanical_v3/bench_c4_sixdof/profile.json)
et le [profil secondaire](../electromechanical_v3/bench_c4_sixdof_secondary/profile.json)
définissent les datums d’équipement, les deux câbles, leurs zones de
service et une face porteuse déjà modélisée. L’appui est repositionné
dans un patch XY borné de sa face. Le porteur, la visserie et les gaines
sont remesurés après ouverture de la fermeture sauvegardée. La validation
compare le contact des deux gaines, l’aire portante, l’épaisseur à l’axe
contrôlé, l’engagement autorisé et l’accès d’outil à l’appui déplacé.

Un volume balayé représente l’accès d’un gabarit inerte de banc. Ce
contrôle mesure l’inclusion du volume exigé et ses distances aux deux
gaines. La fiche de chaque profil fixe les cotes du banc. L’appui réel
P64 ou P66 et le service du prototype restent **À valider**.
[Mesures C.4](../verification/v3/c4/native_measurements.json)

### 2.3 Dérivation Gazebo du prototype — Implémenté partiellement, 24 octobre 2026

Le responsable choisit de réemployer la CAO active du §2.2, en priorité pour
étudier portance avec charge, consommation et autonomie. La source est
`manifest.json`, clé `prototype_cartographe`, ses occurrences et le natif
`Prototype_Cartographe.FCStd`. Le `x500` actuel reste un contrôle du banc
logiciel. Les études historiques avec dock ne fournissent pas les paramètres
du prototype courant. Les huit empreintes des natifs d'assemblages
(principal et sept sous-assemblages) correspondent au manifeste lors du
contrôle du 23 octobre ; aucun natif n'a été modifié ou recalculé dans cette passe.
ORCH-GZ-1 livre désormais les maillages dérivés et un SDF d'aperçu ; son
chargement Gazebo est exécuté le 24 octobre, avec carré, perte Offboard et
annulation posés sur sol plat. Le repos à z = 0,312505 m est cohérent avec
les patins. L'airframe 40000 applique l'allocation dérivée ; la masse 6 kg
et les inerties restent celles d'un scénario synthétique. Une saturation
transitoire des commandes est observée. Les preuves exactes sont dans
DOC-VAL §9.3 ; la fidélité physique reste **À valider**.

La dérivation distingue trois représentations liées aux mêmes sources :

| Représentation | Donnée à dériver ou identifier | Contrôle nécessaire |
|---|---|---|
| Visuel | maillages des occurrences actives, quatre rotors séparés, géométrie et placements des équipements conservés | résolution des liens, absence de doublon, conversion mm vers m et transformation du repère CAO vers le repère de corps explicite |
| Collisions | primitives ou enveloppes simplifiées conservant les dimensions utiles, train et dégagements | écart géométrique mesuré et acceptable pour le scénario ; maillage visuel complexe non imposé au solveur physique |
| Masse et inerties | masses sourcées et inclusions par composant, centre de masse et tenseurs transportés dans un repère commun | bilan complet sans double comptage, unités kg/m/kg·m², inerties physiquement admissibles ; incertitudes et hypothèses identifiées |

Cette séparation suit les fonctions `visual`, `collision` et `inertial`
([Gazebo Harmonic](https://gazebosim.org/api/sim/8/adding_visuals.html),
[SDFormat](https://sdformat.org/spec/?elem=link&ver=1.9)). Un corps principal
rigide agrégé et quatre rotors constituent la première représentation dynamique
proposée. Les pièces fixes restent détaillées dans la CAO ; leur présence
n'impose pas une articulation par vis dans le simulateur. Les éventuels
modèles de souplesse, d'isolation et de vibration demanderont une question
discriminante et des mesures propres.

**Données physiques ouvertes.** La BOM canonique indique
`configuration.masse_complete_g = null`. Sur ses 95 postes embarqués non
retirés, seuls sept champs de masse unitaire sont renseignés ; ce sont des
valeurs documentaires, avec bornes et inclusions à conserver. Les registres
actifs examinés ne fournissent pas encore le centre de masse et les inerties
physiques du prototype complet. Les enveloppes d'équipements, solides
simplifiés, pièces imprimées et faisceaux ne doivent pas être convertis
globalement en matière homogène. L'inertie automatique issue des collisions
et d'une densité ne reconstitue pas leurs composants internes
([calcul Gazebo](https://gazebosim.org/api/sim/8/auto_inertia_calculation.html)).
Le bilan historique du §6.1 ne remplace pas cette réconciliation.

Les placements, axes et sens documentaires des quatre rotors sont reliés à
l'ordre PX4 dans `model_checks.json`. Leur vérification matérielle reste
ouverte. Le résultat ci-dessous résout le nominal documentaire des hélices,
en conservant distinctement l'enveloppe CAO provisoire. Il décrit également
le traitement visuel de la source Basler invalide selon OCCT.

La propulsion et l'énergie seront identifiées séparément de la géométrie :
MN4014 KV330, ESC Tekko32 F4 45 A, hélices Gemfan 1555 et pack 6S 20 Ah de
la BOM courante. La courbe avec hélice 15×5CF du §6.3 reste une approximation
d'étude ; elle n'est pas une calibration du couple retenu. La campagne et
les preuves attendues sont définies dans
[DOC-VAL §9.3](../VALIDATION_QUALIFICATION.md#fidelite-gazebo-cartographe).

**Résultat ORCH-GZ-1.** Le
[manifeste de simulation](../../simulation/gazebo/models/cartographe/model_manifest.json)
référence les preuves et les commandes. L'export FreeCAD local en lecture des
BREP sauvegardés résout **339 occurrences feuilles : 335 fixes et quatre
rotors**, avec 145 dépendances contrôlées par SHA-256. Les natifs et sources
fabricant sont inchangés. Les STL, environ 100 Mo, restent hors Git.
L'enveloppe statique vaut 0,853513 × 0,505823 × 0,486320 m ; l'écart maximal
au manifeste est 0,014925 mm. Le corps est exporté en mètres, chaque rotor
dans son repère local. Le cap +X est une convention SITL, à matérialiser sur
le prototype. Le Basler reste invalide selon OCCT ; sa tessellation visuelle
réussie ne répare ni ne qualifie cette source.

Les 21 boîtes et quatre disques conservateurs servent au sol plat. Les
exports peuvent désormais être préparés depuis **Simulations → Modèle 3D**
dans la station (DOC-SW §5.2), avec sources inchangées et nouveau dossier
indépendant. Les adaptateurs lisent les BREP sauvegardés sans ouvrir,
recalculer ni sauvegarder les natifs. Cette passerelle cible le profil du
prototype ; elle ne déduit pas ses masses depuis le visuel. Les
boîtes des bras/jambes englobent du vide : les écarts échantillonnés atteignent
146,7/86,8 mm ; les huit patins conservent la hauteur de contact, avec un
écart maximal échantillonné de 4,04 mm aux coins. Obstacles, chocs et fortes
inclinaisons sont exclus de cette première représentation.

**Diamètre documentaire résolu, lot À valider.** La
[fiche Gemfan PMCF1555-T](https://gemfanhobby.en.hisupplier.com/product-2894109-1555-Carbon-Fiber-Propeller-T-Type-CW-CCW-Prop-for-FPV.html)
indique 15 × 5,5 pouces : le nominal est **381 mm**. La conversion
« 15 pouces = 393,7 mm » du constructeur historique est erronée. La CAO et
ses pales restent conservées à Ø393,7 mm comme enveloppes provisoires ;
aucune conclusion physique n'utilise cette cote comme diamètre mesuré.
Marquage, diamètre, pas et sens du lot réel restent à contrôler.

Le [bilan des masses](../../simulation/gazebo/models/cartographe/geometry/mass_ledger.json)
conserve 95 postes embarqués, sept masses documentaires et six inclusions
explicites. Masse complète, centrage et inerties physiques restent `null`.
Les totaux historiques ne sont pas repris. Le module C++17 de transport des
tenseurs et d'agrégation refuse doublons, cycles, rotations invalides et
inerties inadmissibles ; une inconnue empêche une agrégation complète.
Le SDF utilise séparément un **scénario synthétique de 6 kg**, corps boîte
équivalente et quatre disques de 22 g : ce scénario permet le développement,
sans attribuer ces propriétés au prototype. Sa provenance est dans
`dynamics_preview.json`, ses calculs et son allocation dans `model_checks.json`.
Les mesures discriminantes restent pesée complète et par lots, centrage sur
appuis et identification des inerties ; leur protocole est lié dans DOC-VAL §9.3.

## 3. Architecture mécanique du système

L'architecture active du prototype sans échange rapide est décrite au
[§2.2](#assemblage-prototype), avec son périmètre au §3.1 et sa
[nomenclature au §5.0](#nomenclature-prototype). Le schéma et les choix
ci-dessous conservent l'étude historique avec dock pour interpréter ses
preuves ; ils ne désignent pas le montage prototype actif.

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

Intégration historique avec dock à ouvrir pour relire cette étude :

- `hardware/mecanique/cartographe/assemblages/Integration_Stack_Revue_20261003.FCStd`.

Les anciennes intégrations complètes `Drone_Cartographe_20Ah` et
`Systeme_Cartographie_20Ah` sont dans l'archive du §2.1, ainsi que le candidat
système complet utilisant encore le précédent préplacement d'avionique.

Cette configuration historique adopte la batterie **6S 20 Ah**, une cassette
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

<a id="prototype-produit"></a>
### 3.1 Recentrage : prototype puis produit custom — 11 octobre 2026

**Périmètre retenu ; construction CAO Implémenté, faisabilité À valider.** Le responsable
demande la nomenclature puis la reconstruction du prototype suivant cette séparation en deux étapes.
Les composants conservés sont ceux de la sélection cible documentaire, pas
un inventaire de matériel possédé. Le registre du §5.0 est **Implémenté** ;
le prototype reconstruit est décrit au §2.2. Le catalogue historique du §2.1
conserve l'étude avec dock ; ses exigences d'échange rapide ne s'appliquent
pas au prototype simplifié.

**Problème et observations.** La priorité reste la faisabilité physique du
cartographe ([DOC-HLD](HLD.md#methodologie), [DOC-VAL §14](../VALIDATION_QUALIFICATION.md#recentrage)).
L'étude historique comporte une batterie de 67 pièces mobiles, un récepteur de 72 pièces
fixes et une rehausse totale de 45 mm (§3–4), alors que la configuration
complète et sa masse restent ouvertes (§6.1, registre
[configuration cible](../../hardware/mecanique/cartographe/configuration_cible_20261003.json)).
Ces comptages décrivent le modèle, pas une masse ni une qualification.
L'hypothèse de recentrage est que le mécanisme d'échange rapide impose des
travaux qui ne sont pas nécessaires au premier signal de faisabilité.

| Étape | Périmètre et résultat utile | Limite |
|---|---|---|
| Prototype | X650 et propulsion cible ; porteuse Holybro, modules 6X/Orin NX, Airy/Basler et GNSS cible ; supports et faisceaux nécessaires à une acquisition exploitable | une seule configuration à réconcilier ; compatibilité, masse, centrage, énergie, thermique et acquisition À valider |
| Produit custom ultérieur | mécanique conçue autour de la mission et de l'énergie ; porteuse spécifique conservant les modules 6X et Jetson ; échange rapide intégré dès la conception | périmètre, bénéfice et budget conditionnés aux mesures du prototype ; aucune obligation de tout refaire ni de tout réunir sur un seul PCB |

**Prototype retenu pour la nomenclature.** Retirer de son besoin l'échange sans outil,
la cassette coulissante et l'accouplement automatique ; étudier un maintien
simple de batterie, une retenue vérifiable et un raccordement manuel au sol,
désarmé et moteurs arrêtés. La batterie demeure remplaçable. Le responsable
choisit le 10 octobre **brancher = mettre sous tension ; débrancher = mettre
hors tension** : le JETI MainSwitch100 et sa commande magnétique sont retirés
de la nomenclature prototype. Les fonctions BMS, maîtrise de l'appel de courant,
mesure PM08-CAN et distribution restent nécessaires. Le connecteur manuel
et sa précharge, les protections contre le toucher, l'isolation, la reprise
des efforts des câbles et l'accessibilité restent **À valider**, selon
[DOC-ELEC §3](ARCHITECTURE_ELECTRIQUE_RESEAUX.md#3-chaîne-dénergie-candidate-du-cartographe).
Le BMS ne démontre pas une précharge ; les natifs avec dock/JETI restent
conservés comme étude historique distincte du prototype reconstruit.
CA01 est la carte auxiliaire, distincte de la porteuse Holybro : ses fonctions
d'alimentation/radio/synchronisation restent à couvrir ; son périmètre est à
réexaminer si sa réalisation bloque la preuve minimale.

Le pack 6S 20 Ah et le X650 servent de point de départ ; leur compatibilité
reste une hypothèse réfutable par le bilan complet. Aucun gain de masse,
d'autonomie ou de fiabilité n'est attribué au retrait du dock sans comparaison.
Conserver les références commerciales, les interfaces capteurs et les preuves
réutilisables ; reprendre les supports selon les contraintes de cette seule
configuration. La rehausse du dock n'est pas reconduite dans le prototype.

**Action minimale et arrêt.** La passe documentaire a rapproché les
inclusions/retraits et distingué les définitions des inconnues. La reprise
CAO demandée construit une seule configuration à partir de cette BOM et
des sources réutilisables. Terminer sa revue de présence, montage et
interférences, puis conclure « poursuivre les mesures », « revoir la
sélection » ou « données insuffisantes », avec l'écart discriminant. Cette
construction réversible n'engage ni achat, ni fabrication, ni essai physique.
Le budget et les critères des essais matériels restent **À valider**, suivant
DOC-VAL §14.

Le passage au produit custom se justifiera par une acquisition utile démontrée,
des mesures de masse/endurance/thermique et des limites d'intégration ou d'usage
identifiées. Mesurer aussi la manipulation et le temps de remise en service
du prototype pour dimensionner le besoin d'échange rapide. Un gain insuffisant
ou une contrainte non résolue doit pouvoir conduire à différer ou revoir cette
fonction. PX4 conserve l'autorité de vol dans les deux étapes. La construction
et les contrôles CAO restent distincts d'une validation physique, non exécutée.

## 4. Sous-assemblages et fonctionnement

Les sous-assemblages de cette section décrivent l'étude historique avec dock
et les interfaces réutilisables. Les sept sous-assemblages actifs du prototype
sont ceux du [§2.2](#assemblage-prototype).

| Sous-assemblage | Fonction | Choix de l'étude avec dock | État |
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

La maquette CAO historique montait le kit développeur Orin Nano sur P03/P04.
Deux contacts aux entretoises arrière y ont été détectés ; cette géométrie
ne peut pas valider la nouvelle cible. Celle-ci associe la **Holybro Pixhawk
Jetson Baseboard**, le **Pixhawk 6X module seul** et un **Jetson Orin NX 16 Go**
sur une même porteuse. Son implantation, sa fixation, le refroidissement, la
circulation d'air, la protection contre les projections et l'accès au SSD,
à l'XT30 et aux autres connecteurs sont **À valider** après acquisition des
révisions et géométries exactes. Le prototype reconstruit emploie P66–P68
avec la porteuse et le refroidissement du §2.2 ; P03/P04 et P20 ne sont pas
reconduits par analogie. La construction n'en qualifie pas les interfaces.


### 4.4 Porteuse cible du 24 septembre et CAO historique du 16 septembre

La nouvelle cible mécanique regroupe sur la **Holybro Pixhawk Jetson Baseboard**
le **Pixhawk 6X module seul** et le **Jetson Orin NX 16 Go**. Elle remplace
l'implantation séparée Pixhawk/base v2A dans SA03 et kit Orin Nano dans SA04.
Le support, l'isolation, la dissipation, les accès aux ports et les faisceaux
doivent être contrôlés sans présumer des perçages ou jeux de l'ancienne CAO.
La variante native CA01/Holybro du §4.4.1 constitue une étape historique
**Implémenté**. L'intégration active est désormais celle de
`SA05_Prototype_Avionique` (§2.2), construction et contrôles numériques
**Implémenté**, tenue physique **À valider**.

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

<a id="nomenclature-prototype"></a>
### 5.0 Nomenclatures du prototype et du produit custom — 22 octobre 2026

La source de définition est
[`nomenclature_prototype.json`](../../hardware/mecanique/cartographe/nomenclature_prototype.json),
référence `BOM-CARTO-PROTOTYPE`. Le
[classeur de consultation](../../hardware/mecanique/cartographe/exports/Nomenclature_Prototype_Cartographe.xlsx)
commence par une **Vue système de 24 équipements principaux**, suivie de neuf
onglets : Structure, Propulsion, Énergie, Avionique, CA01, Perception,
Navigation et radio, Faisceaux et Sol. Une annexe Options et retraits conserve
les postes hors configuration. Les liaisons sont détaillées dans Faisceaux et
les composants de carte dans CA01. Chaque poste appartient à un seul onglet
détaillé ; la synthèse reprend ses références, quantités et unités par formule
et indique l'onglet et la ligne correspondants. Le JSON possède les données ;
le classeur est un export.
Les sources fabricant, inclusions, quantités candidates, masses documentaires
et réserves sont attachées aux lignes, avec les empreintes des registres
techniques utilisés. L'ancien `configuration_cible_20261003.json` reste une
entrée historique de rapprochement, pas la nomenclature du prototype simplifié.
Le manifeste mécanique conserve l'autorité sur les occurrences et placements
des natifs ; la reconstruction active est décrite au §2.2.

Le registre conserve **134 lignes**, dont **95 embarquées**, **1 lot
d'approvisionnement**, **12 de moyens au sol**, **3 options** et **23 retraits**.
Ce sont des postes de nomenclature, parfois des jeux, pas 134 pièces physiques.
La couverture des **60 postes** de la sélection précédente est explicite ;
**43 identifiants de liaison** distinguent fonctions, cordons communs,
connexions internes, liaisons sans fil et retraits historiques. W22 (rallonge
GNSS), W39 et W-JETI-COMMANDE restent tracés mais exclus, quantité zéro ; W38 relie
le connecteur manuel au PM08-CAN IN. Le détail de CA01 compte **151 repères**, dont
**141 composants montés candidats**, **8 non montés (DNP)** et **2 points de
test sans composant**. Le PCB et les composants détaillent la carte assemblée,
ils ne s'ajoutent pas comme une seconde carte.

| Ensemble | Définition retenue pour le prototype | Réserve déterminante |
|---|---|---|
| Porteur et propulsion | kit X650 V2, structure OEM, quatre MN4014 KV330, quatre Tekko32 F4 45 A, deux hélices CW et deux CCW Gemfan 1555 | lot, masse du kit décomposée et performances à la masse réelle |
| Avionique | un module 6X réutilisé du kit, Orin NX 16 Go, porteuse Holybro, SSD Samsung MZ-V9S1T0BW 1 To, refroidissement et CA01 avec RP4TD | révision, thermique/fixation SSD, refroidissement, fabrication CA01 et synchronisation |
| Perception/navigation | Airy, Basler a2A4096-30ucBAS et objectif, H-RTK DroneCAN Helical STM32G4 | objectif, tenue thermique Airy, interfaces temporelles et intégration |
| Énergie | Tattu 6S 20 Ah, BMS JBD, un jeu QS8-S D-MAX B9310 avec anti-étincelle, PM08-CAN, PDB 18138 et protections | profils courant/charge et capacité aval, précharge, sélectivité, masse installée et maintien ; QS8-S retenu, qualification À valider |
| Mécanique d'intégration | maintien batterie simple avec sangles, supports avionique/énergie/GNSS/radio, bloc capteurs et isolateurs, visserie, retenues et protections des câbles | reprise d'implantation, références de montage et tenue réelle |
| Moyens au sol | radiocommande Pocket ELRS, base RTK, PC, alimentation, recharge, cordons et moyens de mise en service | références et inventaire physique non acquis |

Décisions d'inclusion : le lot X650 n'est jamais additionné à ses composants
embarqués ; le module 6X est conservé et seule sa base v2A est retirée au
profit de la porteuse commune. M10, SiK, PM02D et PDB OEM du kit sont retirés
de cette configuration. Le RP4TD est inclus dans CA01 ; ses antennes/coaxiaux
restent détaillés. La provision groupée d'avionique de 190 g n'est pas utilisée
comme une masse connue. La variante PM08-CAN **15029 à fils étamés** est la
candidate du prototype ; l'ancienne 15028 XT90 reste une alternative à résoudre,
pas un deuxième module à acheter.

Le dock, sa cassette, ses rails, verrou/gâche, TE d'accouplement et rehausse
spécifique ne sont pas reconduits. Le JETI, sa commande magnétique et le cordon
JETI → PM08-CAN sont également exclus depuis le 10 octobre ; ces trois postes
restent dans Options et retraits avec quantité zéro pour préserver la traçabilité.
Aucun gain massique n'est revendiqué avant bilan avec le connecteur de remplacement.
Les étages du châssis OEM sont conservés ; la reconstruction emploie les
supports P60–P80 et les interfaces réutilisées du §2.2. P65 dérive P16 en
aluminium pour le contact thermique de l'Airy ; cela ne qualifie ni
l'évacuation thermique ni la tenue vibratoire. Les deux fixations latérales
de la Basler, les ancrages communs batterie/capteurs et les fixations de
butées sont distingués dans la BOM pour éviter les doubles comptes. Les
piges Airy ont une spécification candidate mais leur implantation reste
ouverte faute de coordonnées constructeur. Les dimensions de supports,
protections et faisceaux restent assorties de leurs réserves de fabrication.

**Complétude et limites de définition.** La reprise a trouvé **50 postes
actifs initialement incomplets**, contre 49 dans le tableau de départ, puis
mis à jour **55 postes** en incluant les interfaces connexes. Tous les champs
de référence de définition et de quantité active sont renseignés. Une
spécification projet ou un jeu OEM ne constitue cependant pas toujours une
référence achetable ni un plan de fabrication complet. La nomenclature n'est
pas libérée pour une commande ou une fabrication exhaustive.

**20 postes embarqués comportent encore un complément matériel explicite** dans
`resolution_definition.details_encore_a_terminer` : trois contrôles de contenu
OEM, neuf détails de montage et qualification physiques et huit interfaces à identifier. Les deux
choix de terminal et d'alimentation au sol sont différés séparément, sans
conditionner la CAO. Ces catégories et chaque réserve sont portées par
le JSON ; remplir un champ ne clôt pas ces points. Les réservations de CAO
peuvent préciser parcours et encombrements, sans démontrer un brochage, la
présence physique du matériel ou une tenue. Les longueurs de coupe, les
masses installées et les prix inconnus ne sont pas inventés.
Le pack annoncé à 1 950 ±20 g comprend sa connectique livrée ; sa masse après
adaptation est inconnue. Les 85 g Basler sont une borne publiée « <85 g »,
pas une masse nominale. Aucun total massique ni budget complet n'est calculé
avec les données absentes.

<a id="refroidissement-prototype"></a>
**Refroidissement Jetson retenu, ligne 22 de la Vue système.**
`MEC-REFROIDISSEMENT-JETSON` couvre un jeu dissipateur, ventilateur,
interface thermique et fixations. Le responsable retient le 10 octobre 2026
**un jeu [Waveshare Orin-FAN-PWM, SKU 24076](https://www.waveshare.com/product/orin-fan-pwm.htm)**.
La référence est renseignée dans la BOM ; l'intégration reste **À valider**.
Le fabricant annonce la compatibilité module Orin NX, un dissipateur aluminium
avec ventilateur PWM 5 V/0,13 A, de la graisse thermique et une bride avec vis.
Le câble de 37 ±3 mm impose de vérifier la portée, le connecteur FAN,
le brochage et la tension sur la porteuse Holybro 11072 réelle ; aucun
branchement direct n'est acquis. Dégagement, circulation d'air et température
avec acquisition/calcul restent **À valider**. La porteuse seule ne fournit
pas ce refroidissement ; déduire l'achat séparé si le lot Jetson livré possède
déjà un ensemble identifié et adapté. La masse de provision avionique ne
doit pas être additionnée à une masse de refroidissement sans décomposition.

La [vérification du connecteur FAN](ARCHITECTURE_ELECTRIQUE_RESEAUX.md#connecteur-ventilateur-jetson)
du 10 octobre trouve un courant nominal de 0,13 A inférieur à la limite
Holybro publiée de 0,35 A. Le rapprochement STEP/photo identifie une prise
DF13 quatre contacts, pas de 1,25 mm, **candidate** côté porteuse ; la fiche
Waveshare, les brochages et la tension du port restent non établis.
Le raccordement direct et la portée du câble ne sont donc pas démontrés.
La référence de la ligne 22 est choisie ; sa qualification reste **À valider**,
sans ajout de connecteur ou d'adaptateur dans la nomenclature.

<a id="objectif-prototype"></a>
**Objectif Basler retenu, ligne 26 de la Vue système.** Le responsable choisit
le 10 octobre 2026 **un Fujinon CF8ZA-1S, 8 mm nominal, monture C** pour
`SEN-LENS`. La référence et la masse fabricant d'environ **180 g** sont
inscrites en BOM ; cette masse n'est pas une pesée et exclut le support.
Le choix limite masse et encombrement parmi les deux candidats comparés dans
[DOC-ELEC](ARCHITECTURE_ELECTRIQUE_RESEAUX.md#objectif-prototype).
La provision historique 80–150 g ne s'applique plus à cet objectif choisi.
Le scénario de **10 m au-dessus des vignes** reste une hypothèse d'étude ;
il ne fixe pas un paramètre de vol qualifié. Support, intrusion C-mount,
blocage des réglages, calibration et tenue vibratoire restent **À valider**.

<a id="pc-sol-prototype"></a>
**Terminal au sol, ligne 30 de la Vue système.** Le responsable précise le
12 octobre que le format reste ouvert : portable, tablette ou téléphone
selon ergonomie. `SOL-PC` conserve cet identifiant sans imposer un PC.
Le chargeur du terminal est provisionné à **60 W**, comme hypothèse ; modèle,
connectique et compatibilité seront choisis ultérieurement selon
[DOC-ELEC](ARCHITECTURE_ELECTRIQUE_RESEAUX.md#pc-sol-prototype).
Ces deux postes sont hors assemblage aéronef et ne conditionnent pas sa CAO.

<a id="chargeur-prototype"></a>
**Chargeur retenu, ligne 31 de la Vue système.** La recherche de
recharge à travers le BMS propose un chargeur secteur CC/CV sur B+/P−
protégés, via la prise QS8-S du pack, batterie débranchée du drone. La
référence inscrite est **SkyRC S100neo SK-100202**, quantité **1**, avec
profil 25,2 V / 3,5 A à confirmer ; DOC-ELEC porte les sources et limites.
`SOL-CHARGE-ADAPTER` / `W43` référence désormais **Logic RC O-LGL-CLQS8**,
cordon commercial **XT60 → QS8-S**, quantité **1** avec ses connecteurs
intégrés ; aucun achat séparé de ces connecteurs n'est ajouté. La paire
batterie/drone B9310 reste distincte. Masse installée, accouplement réel,
sexes des contacts, caractéristiques du cordon et protection restent à
vérifier. Chargeur et recharge
restent **À valider**, sans achat ni qualification matérielle.

**Décision de faisabilité : données insuffisantes.** La prochaine étape est
de fermer les détails encore ouverts de l'assemblage reconstruit et de relever
les masses et données de mission nécessaires au centrage et à l'endurance. La
suppression du dock ne suffit pas à démontrer que X650 et 6S 20 Ah conviennent.
Les contrôles de ce registre et du classeur sont consignés dans
[la preuve de vérification](../../hardware/mecanique/cartographe/verification/controle_nomenclature_prototype.json)
et interprétés dans [DOC-VAL §14.3](../VALIDATION_QUALIFICATION.md#nomenclature-prototype).
Le contrôle du 22 octobre des deux registres et classeurs a réussi
**108 contrôles documentaires** : références, inclusions, quantités,
sources, formules et détails ouverts. Le classeur prototype a été réexporté,
réimporté et recalculé ; les lignes modifiées ont été inspectées visuellement.
La synthèse conserve les quantités 7, 0 et « À définir » lorsque le détail
est vide, sans sauvegarder ces variations d’essai. Ces contrôles ne
qualifient ni la CAO ni le matériel (§2.2).

#### 5.0.1 Nomenclature fonctionnelle du produit custom

À la demande du responsable, le produit ultérieur dispose d'un
[classeur séparé](../../hardware/mecanique/cartographe/exports/Nomenclature_Produit_Custom_Cartographe.xlsx),
dérivé de
[`nomenclature_produit_custom.json`](../../hardware/mecanique/cartographe/nomenclature_produit_custom.json).
La vue système présente 26 équipements ou fonctions principaux ; dix onglets
détaillent **54 postes fonctionnels** : Structure, Propulsion, Batterie,
Échange batterie, Puissance, Porteuse et calcul, Acquisition, Navigation et
radio, Intégration thermique et Moyens sol.

Ce registre rend lisible la seconde étape du §3.1, sans changer la priorité
de faisabilité du prototype ni engager la conception détaillée. Seuls les
modules **Pixhawk 6X et Jetson** sont explicitement conservés. La porteuse
complète, la mécanique et l'échange rapide sont **Planifiés** ; références,
dimensionnement et réalisation restent **À valider**. Une quantité « 1 ensemble
fonctionnel » désigne un besoin à couvrir, pas une pièce ou une carte déjà
définie. Les fonctions incluses dans la porteuse ne s'ajoutent pas comme des
cartes autonomes. La répartition physique de la puissance entre cartes reste
ouverte ; aucune sous-BOM de la future porteuse n'est inventée.

Les références du X650, de sa propulsion, de la batterie, de CA01 et du dock
étudié ne sont pas reconduites automatiquement. La batterie mobile et le
système fixe d'échange ont des feuilles distinctes. L'échange rapide au sol
n'implique pas un échange sous tension. Aucun bilan massique, coût, achat,
fabrication ou qualification physique n'est acquis par cette organisation.
La passe s'arrête à deux nomenclatures lisibles et cohérentes ; la prochaine
décision technique reste fondée sur les données du prototype (§3.1).

### 5.1 Pièces fabriquées

Les quantités ci-dessous conservent la configuration historique du manifeste
FreeCAD ; elles ne constituent pas la nomenclature du prototype actif. Ses
pièces P60–P71 sont identifiées au §2.2 et leurs définitions figurent dans le
registre du §5.0. Les quantités de fabrication restent à confirmer après revue.

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

Le tableau conserve les fournitures de l'étude CAO avec dock pour relire ses
preuves. TE, Southco et JETI/commande n'appartiennent pas à la sélection du
prototype simplifié, portée uniquement par le registre du §5.0. Les supports
et placements hérités ne sont pas reconduits sans revue d'implantation.

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

**Bilan courant ORCH-CAO-MASSE-1 — 26 octobre 2026.** La
[BOM canonique](../../hardware/mecanique/cartographe/nomenclature_prototype.json)
possède les contenus physiques, sources, quantités absolues par drone,
conditions et inclusions. Le
[registre massique](../../simulation/gazebo/models/cartographe/geometry/mass_ledger.json)
et [son contrôle reproductible](../../hardware/mecanique/cartographe/verification/controle_masse_prototype.json)
en sont des dérivés C++17. Un kit d'approvisionnement n'est pas une masse
embarquée ; un composant couvert par une masse d'ensemble applicable n'est
pas ajouté. Si le parent reste inconnu, ses enfants calculables contribuent
au sous-total et le parent reste incomplet. Les maxima caméra/SSD, masses
de colis et périmètres accessoires non confirmés sont exclus de la somme
nominale. Les inconnues restent `null`, jamais zéro.

La masse complète du drone, son centrage et ses inerties restent inconnus.
Le sous-total disponible distingue ensembles documentés et pièces fabriquées
selon les recettes candidates ; il n'est ni une masse complète ni une borne
garantie. Le centrage et les inerties publiés pour le seul sous-ensemble de
pièces supposées homogènes ne sont pas ceux du drone. Une boîte commerciale
extérieure avec masse connue n'établit pas sa distribution interne.
La [couverture bidirectionnelle](../../hardware/mecanique/cartographe/verification/couverture_bom_cao_prototype.json)
recense aussi les absences, rattachements d'ensembles et occurrences sans
propriétaire résolu. Les valeurs des paragraphes suivants restent
**historiques** ; ni leurs masses de kit ni le scénario synthétique de 6 kg
ne définissent le prototype actif.

Le résultat courant est **2 892,664 g disponibles** : **1 299,808 g**
documentaires applicables et **1 592,856 g** de calculs candidats.
La masse commerciale du kit complet sans batterie est **2 000 g**, inscrite
sur sa ligne d'approvisionnement avec son périmètre et sans ajout au drone :
plusieurs pièces du kit sont retirées, remplacées ou comptées séparément.
Une soustraction des retraits et addition des équipements ne peut donner
un total complet tant que les périmètres et masses correspondants manquent.
Les quatre plateaux, quatre tubes de bras et quatre tubes du train apportent
**387,779 g candidats** depuis leurs volumes BRep et les densités de composites
analogues 1,56 et 1,61 g/cm³. Les matériaux exacts, stratifications et masses
réelles OEM restent inconnus ; le résultat ne constitue pas une borne garantie.
Les quatre plateaux restent marqués incomplets malgré leur contenu géométrique
identifié. Voir la [preuve de calcul](../../hardware/mecanique/cartographe/verification/orch_reprise_kit_densites.json).
Douze corps d'articulations et supports moteur attribués à l'aluminium ajoutent
**200,650 g candidats**, calculés avec la densité 2,70 g/cm³ d'un alliage
analogue ; la nuance exacte et les petites pièces restent inconnues. Le
[contrôle BRep en placements globaux](../../hardware/mecanique/cartographe/verification/orch_verifier_interferences_oem.json)
ne trouve pas d'intersection entre ces douze corps ni avec les quatre tubes
carbone calculés. Il relève toutefois **22 intersections positives et deux
opérations non concluantes sur 216 paires** examinées dans les groupes de bras.
Leur caractère voulu, les pièces concernées et le volume réel sont **À valider** ;
aucune masse des pièces exclues n'est ajoutée et aucune soustraction de volume
arbitraire n'est appliquée. Le précédent résultat en repères locaux est
supersédé pour l'analyse de l'assemblage.

La photo d'un ESC Holybro 31104 nu montre 5,6 g ; son nominal est 5,8 g.
Si la carte du 31230 précâblé est identique, quatre cartes seules représenteraient
23,2 g, hors fils, prises et protections. La correspondance n'étant pas établie,
ce scénario reste séparé du sous-total. De même, 22 g par hélice seraient
88 g pour quatre, sous réserve de la variante et de l'unité de masse ; aucune
de ces conditions n'est démontrée pour le SKU 520095. Les hypothèses et
divergences sont dans les preuves [moteurs/ESC](../../hardware/mecanique/cartographe/verification/orch_reprise_propulsion_moteurs_esc.json)
et [hélices](../../hardware/mecanique/cartographe/verification/orch_reprise_propulsion_helices.json).
Si ces deux hypothèses étaient retenues ensemble, le sous-total exploratoire
serait **3 003,864 g** ; il reste partiel, notamment sans batterie adaptée ni
compléments de câblage, et ne constitue ni une masse complète ni une borne.
La reprise apporte notamment les quatre corps moteur MN4014 KV330,
150 g chacun hors cordons/accessoires, la porteuse seule, le GNSS,
les masses nominales de quinze références de visserie et deux éléments
partiels sous leurs ensembles : fusible ATOF et RP4TD. Les fixations ajoutées
au PM08 sont comptées depuis leurs six occurrences réelles. Les grades,
finitions et tolérances non confirmés restent candidats ; les têtes de vis
fraisées ne reçoivent pas une masse calculée depuis leur gabarit extérieur.
Les Sorbothane sont calculés depuis plans et densité documentés, après
correction du rattachement bas/haut des références 0510030/0510010.

Les 86 contributions de géométrie/câble incluent **10,094 g** pour le seul
segment M8 implanté (296,877 mm ×34 g/m). Le faisceau complet reste inconnu :
surmoulage, PH, engagements, surlongueurs et coupe ne sont pas couverts.
Le cordon complet 63,7 g n'est pas ajouté. Les 228,6 g/72 g Waveshare sont
exclus : périmètre net non établi. La batterie adaptée, les cordons OEM
PM08 et la révision FCU restent également à résoudre ; leurs valeurs
documentaires conditionnelles ne complètent pas artificiellement la somme.

Sur les **95 postes embarqués**, dix postes sont couverts par une masse
documentaire applicable, treize par un calcul complet de leur contenu défini,
et deux par une inclusion explicite. **70 postes restent inconnus ou
incomplets**, dont onze ont une contribution partielle. Chaque manque figure
dans `probleme_massique` sur sa ligne BOM, avec information nécessaire,
sources et impact ; la masse unitaire complète reste `null`. Une masse
globale connue ne démontre pas les masses individuelles de ses composants.
Les autres inclusions prévues ne sont pas fermées par une masse globale
encore inconnue. Les sous-totaux par sous-système
et sous-assemblage figurent dans le registre ; `null` signifie qu'aucune
contribution connue n'est disponible. Aucune marge de masse n'est démontrée.

Pour le seul sous-ensemble de **47 pièces supposées homogènes**, masse
949,464 g, le barycentre calculé dans le repère CAO est
(3,826 ; −0,862 ; −24,748) mm. Son tenseur est conservé dans le registre.
Ce résultat exclut les pièces TPU tranchées, le câble, les équipements
commerciaux et les 24 nouvelles pièces OEM dont la distribution n'est pas
calculée ; il ne décrit ni le centrage ni les inerties du drone.

**Priorité de reprise du 8 octobre 2026 :** appliquer le
[cadrage système](HLD.md#methodologie) et [DOC-VAL §14](../VALIDATION_QUALIFICATION.md#recentrage).
Réconcilier une seule configuration complète, ses inclusions/retraits et les
masses mesurées, publiées, provisionnelles ou inconnues avant toute nouvelle
optimisation locale. Le bilan doit permettre une décision sur masse,
centrage, propulsion et énergie ; le total historique ci-dessous ne suffit
pas à démontrer la faisabilité de la cible. L'audit
[AUD-003/004](../VALIDATION_QUALIFICATION.md#aud-003) précise action et clôture.

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
| `MEC-MAS-001`, `MEC-ARC-001` | CAO active, dérivation et agrégation massique du prototype | `T-CARTO-GZ-01/02`, DOC-VAL §9.3 | dérivation et agrégateur **Implémentés** et testés ; propriétés physiques réelles **À valider**, aucun modèle dynamique qualifié |
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

- **28 novembre 2026** — Bancs V3-C.4 à pose variable, patch d’appui plan, seconde hiérarchie et gabarit d’accès inerte.

- **27 novembre 2026** — Dossiers de collecte d’appui V3-A.7 pour P64 et P66. [Validation](../VALIDATION_QUALIFICATION.md#cartographe-v3-a7)
- **27 novembre 2026** — Clôture des preuves synthétiques V3-INT.3, avec conservation des conditions d’appui et de réception du cartographe. [Validation](../VALIDATION_QUALIFICATION.md#cartographe-v3-int3-cloture)
- **27 novembre 2026** — V3-INT.3 rejoue la mesure des fermetures des deux bancs C.3 et du Workholding P64 synthétique. [Validation](../VALIDATION_QUALIFICATION.md#cartographe-v3-int3)
- **26 novembre 2026** — Deux bancs V3-C.3 éprouvent les couloirs volumiques, les appuis et une seconde hiérarchie XLink de ports ([bancs de cheminement](#bancs-spatiaux-c3)).

- **18 novembre 2026** — Fermeture et transfert XLink V3-A, traçabilité des appuis, ancrages et réservations F40/F41.

- **17 novembre 2026** — Suivi Git des natifs FreeCAD existants, variantes et archives comprises, avec leurs liens externes ; exclusions des sources fabricant, exports et sauvegardes conservées (§2).
- **17 novembre 2026** — Reconstruction GO3B, six variantes et une consolidée native. Défauts mesurés et réception NO_GO motivée. [Résultat](#cartographe-go3b-reconstruction).
- **17 novembre 2026** — Portefeuille GO3A V2.1 sur l’actif gelé. Trois décisions d’implantation et de service à comparer sur copies (§2.2.2).

- **15 novembre 2026** — Rattachement des poses et formes aux occurrences XLink de la fermeture active. [Validation](../VALIDATION_QUALIFICATION.md#preuve-xlink-v21).

- **15 novembre 2026** — Relecture des axes et occurrences d’interface sur copie XLink. Criblage W16/B sur géométrie fournisseur et gabarits de service (§2.2.2).

- **14 novembre 2026** — Architecture d’instruction H-01 et réserves de montage/structure (§2.2.2).

- **12 novembre 2026** — Banc L2 avec repères d’interface, terminaux et
  retrait, sauvegardé et vérifié en processus indépendant (§2.2.2).
- **12 novembre 2026** — Contrats V2 définis en L0, avec fermetures CAO
  distinctes pour l’actif et la copie consolidée (§2.2.2).
- **11 novembre 2026** — Mesures natives de portées et de poses discrètes
  sur banc. Clôture GO 1 et limites d’application au prototype (§2.2.2).
- **10 novembre 2026** — Moteur électromécanique de l’action 1, séparation
  des critères et des variantes, construction et contrôle isolés (§2.2.2).
- **9 novembre 2026** — Copie modulaire ancrée sur les interfaces existantes,
  suppression des cinq grandes retenues orange, cinq parcours redessinés
  et maintien mécanique résiduel **À valider** (§2.2).
- **9 novembre 2026** — Refonte du système de faisceaux sur copie, partition
  native, protections communes et contrôle de conservation des interfaces.

| Date | Modification |
|---|---|
| 12 novembre 2026 | Action 3 : copie consolidée F12/F16/F25/P85/F35 rouverte et criblée. |
| 11 novembre 2026 | Action 3 : nouveau trajet F35 testé sur copie et marge avec F25/P75 mesurée. |
| 11 novembre 2026 | Action 3 : correction locale de la géométrie OEM X650 sur copie et réouverture indépendante du prototype complet. |
| 11 novembre 2026 | Action 3 : exploration conditionnelle A/B/C sur le prototype sans dock et contrôles sur copies ; architecture à valider. |
| 28 octobre 2026 | Autonomie d'ingénierie de la skill existante : résolution des inconnues, contraintes héritées, variantes sur copie, mobilité, provenance et verdicts conditionnels ; aucune modification du prototype (§2.2.2). |
| 28 octobre 2026 | Reconstruction sur copie : inventaire global, huit gaines prédimensionnées, candidat F16 analytique et comparaison BRep ; sources préservées, reconstruction globale et intégration physique non validées (§2.2.3). |
| 27 octobre 2026 | Skill d'intégration électromécanique : architecture globale, planificateur de corridors et contrôles FreeCAD synthétiques, limites et réutilisation du constructeur explicites ; aucun faisceau réel reconstruit (§2.2.2). |
| 26 octobre 2026 | Masse publiée du kit, estimations de 24 pièces X650 par densités analogues, scénarios ESC/hélices séparés et intersections internes des bras à résoudre (§6.1). |
| 26 octobre 2026 | Reprise : collisions PM08/QS8/F20 supprimées, fixations PM08 et fraisures90° intégrées, huit placements de vis ajustés et trois têtes CHC corrigées ; masses documentaires et candidates étendues, problèmes explicites dans la BOM, périmètres Waveshare rectifiés ; définition complète toujours À valider (§2.2.1, §6.1). |
| 25 octobre 2026 | ORCH-CAO-MASSE-1 : sources et modèles repris en place, décomposition OEM, grades/procédés candidats, réconciliation et sous-total reproductible ; défauts d'interface et inconnues conservés, lot non clos (§2.2.1, §6.1). |
| 24 octobre 2026 | Passerelle CAO → Gazebo intégrée à Simulations : service UI/CLI commun, export isolé et contrôlé, aperçu navigable, annulation et tests ; chargement Gazebo réel, physique À valider (DOC-VAL §10.2). |
| 24 octobre 2026 | ORCH-GZ-1 : banc Docker/ROS reconstruit, airframe 40000 et capteurs synthétiques corrigés ; six essais SITL courants carré/perte Offboard/annulation finalisés, T0 et revue indépendante ; batterie forfaitaire observée, fidélité physique et autonomie couplée À valider (DOC-VAL §9.3). |
| 23 octobre 2026 | ORCH-GZ-1 : exports actifs, collisions sol plat, bilan des inconnues et SDF synthétique implémentés ; nominal hélice 381 mm distingué de l'enveloppe CAO 393,7 mm, aucune qualification physique (§2.3). |
| 23 octobre 2026 | Dérivation Gazebo du prototype décidée pour l'étude de portance/énergie ; visuel, collisions et propriétés massiques séparés (§2.3). Empreintes des huit assemblages concordantes, masses/inerties et cote des hélices à fermer ; aucun natif ni export modifié. |
| 22 octobre 2026 | Refonte finale 118 références/346 occurrences ; énergie haute et caméra conservées. Départs de bras, réserve USB, liaisons, ancrages et retenues de corps contrôlés ; BOM/classeur synchronisés, 281 colliers nominaux après déduplication. 20 réserves matérielles, aucune qualification physique (§2.2, §5.0). |
| 21 octobre 2026 | Retenues supplémentaires des bras, distribution, avionique, caméra et sondes NTC dans les recettes ; critères locaux de portée explicités dans le contrat des 53 parcours. Deux croisements entre supports corrigés ; reconstruction finale et couverture complète encore en cours (§2.2). |
| 16 octobre 2026 | Prises caméra coudées représentées, caméra maintenue ; P60/pads/sangles adaptés sous réserves. P75/P76/P77 intégrés, P78 et retenues de puissance en reconstruction après contrôles locaux. Dégagements des fixations et du Type A corrigés dans la recette ; 52 interfaces de colliers affectées, couverture globale encore en contrôle (§2.2). |
| 19 octobre 2026 | Construction complète de 111 références/314 occurrences ; P78, retenues puissance et neuf appuis locaux intégrés. P75 reconstruit avec filtre de composé natif. Les 53 câbles se recalculent sans erreur ; collision globale et couverture des retenues en cours (§2.2). |
| 13 octobre 2026 | SA03 déplacé à l’étage supérieur : P64 et quatre P74, modules à Z39, garde nominale 18 mm.53 parcours Cable Workbench 0.3.7 et guides P72/P73 en correction/contrôle, P75 en étude ; antennes côté gauche,18 compléments embarqués conservés. Résultats du12 distingués de la refonte, réexport à suivre (§2.2,§5.0). |
| 12 octobre 2026 | Précision utilisateur : terminal au sol portable/tablette/téléphone, choix selon ergonomie ; chargeur60 W hypothétiques. Deux sélections différées hors CAO,18 compléments embarqués ; aucun natif ni logiciel modifié. |
| 12 octobre 2026 | Assemblage prototype en7 sous-ensembles,76 références construites et245 liens contrôlés ; rails inutiles retirés, fixations et perçages corrigés. BOM134 postes,95 embarqués/23 exclus,20 compléments explicites ; garde énergie0,2mm et physique À valider (§2.2,§5.0). |
| 11 octobre 2026 | Prototype_Cartographe reconstruit en sept sous-assemblages, P60–P71 et réemplois tracés ; construction Implémenté, vérification finale en cours et physique À valider. BOM : 134 postes, 96 embarqués/22 exclus, 50 initialement incomplets, 54 repris, 17 détails ouverts ; 103 contrôles documentaires réussis (§2.2, §3.1, §5.0). |
| 10 octobre 2026 | Référence chargeur inscrite dans la Vue système ligne 31 et Sol ligne 17 : SkyRC S100neo SK-100202, quantité 1 ; sélection documentaire retenue, réglages et recharge À valider (§5.0). |
| 10 octobre 2026 | Référence du cordon SOL-CHARGE-ADAPTER renseignée : Logic RC O-LGL-CLQS8, quantité 1, cordon commercial complet ; connecteurs inclus et W43 synchronisée, qualification À valider (§5.0). |
| 10 octobre 2026 | Recharge prototype : adaptateur SOL-CHARGE-ADAPTER / W43 précisé en XT60 → QS8-S si S100neo retenu ; formats distincts et connecteurs supplémentaires explicités, sans sélectionner le chargeur (§5.0). |
| 10 octobre 2026 | Minimum du portable inscrit comme définition acceptée, inventaire déclaré du PC fixe distingué. Chargeur ligne 31 étudié : S100neo candidat non choisi, adaptateur supplémentaire QS8-S vers sortie BMS protégée, profil et réalisation À valider (§5.0, DOC-ELEC §3.1). |
| 10 octobre 2026 | Prototype : retrait du JETI, de sa commande et du cordon aval ; 134 postes conservés, 97 embarqués/21 retraits, 24 principaux ; QS8-S D-MAX B9310, SSD Samsung MZ-V9S1T0BW 1 To, refroidissement Waveshare Orin-FAN-PWM SKU 24076 et objectif Fujinon CF8ZA-1S 8 mm retenus ; 42 références embarquées encore vides, qualification et implantation À valider (§3.1, §5.0). |
| 10 octobre 2026 | Connecteur du refroidissement : DF13 quatre contacts au pas de 1,25 mm candidat d'après STEP/photo Holybro ; courant nominal sous limite publiée, raccordement et portée non démontrés malgré référence choisie. Objectif ligne 26 choisi après comparaison à 10 m : Fujinon CF8ZA-1S, environ 180 g fabricant hors support, intégration À valider. Poste suivant : PC ligne 30, portable de récupération distinct du PC fixe, minimum proposé et modèle à identifier (§5.0, DOC-ELEC §4.3.1 et §7.3). |
| 10 octobre 2026 | Deux classeurs avec vue système et détail par sous-système : prototype préservé à 134 postes, produit custom à 54 postes fonctionnels Planifiés ; niveaux de comptage et maturité explicités (§5.0). |
| 9 octobre 2026 | Nomenclature prototype sans dock : 134 postes, 43 liaisons et détail CA01, inclusions du kit réconciliées, classeur et réserves explicites ; natifs conservés, bilan physique incomplet (§5.0). |
| 8 octobre 2026 | Proposition prototype sur sélection cible actuelle sans fast-swap, puis produit custom conditionné aux mesures ; fonctions indispensables, action minimale et limites explicitées au §3.1, sans mutation des natifs/registres. |
| 8 octobre 2026 | Priorité à la faisabilité masse/propulsion/énergie ; limites du bilan historique, écart d'empreinte du natif courant et contraintes de configuration signalés avec actions de clôture. |
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
