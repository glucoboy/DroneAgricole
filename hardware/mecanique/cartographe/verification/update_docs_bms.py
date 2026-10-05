"""Synchronisation des documents vivants avec la conception BMS candidate."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[4]
def change(path,fn):
 p=ROOT/path;t=p.read_text(encoding='utf-8');p.write_text(fn(t),encoding='utf-8')

elec='''### 6.2 BMS dans la cassette et évolution du connecteur — 5 octobre 2026

`ELEC-BMS-001` / `SAFE-REQ-011` : le BMS commercial **JBD-SP22S003 Li-ion
A01, variante 100 A**, est sélectionné pour le prototype. CAO et schéma
**Implémentés**, lot, montage, performances et protection **À valider**.
Il couvre 6–22S NMC et utilise un port commun charge/décharge : B+ reste
continu, B− brut entre dans le BMS et P−/C− protégé va au contact TE40.
Le TE39 porte B+. Tous les consommateurs sont ensuite derrière le JETI,
qui commute le négatif, puis PM08-CAN et PDB. Aucune charge ni masse avionique
ne rejoint B− brut. Le chargeur hors drone passe aussi par B+/P− protégé ;
l'adaptateur de charge et sa protection restent **Planifiés**.

La [spécification JBD A01](https://cdn-files.myshopline.com/file/store/1720492677212/JBD-SP22S003-Li-ion-A01-2.pdf)
donne un PCB de 130±0,5 ×65±0,5 ×10±2 mm. Cela n'inclut pas une enveloppe
installée de prises, câbles ou dissipation. Le courant «100 A» n'est pas
qualifié dans le coffret : les pertes, températures, courant mission,
pointes et seuils doivent être mesurés sur le lot. Le module n'est pas un
chargeur. JETI et PM08-CAN sont conservés ; aucun module PM08D I²C substitué.

**Connecteur retenu pour ce montage : TE Middle Drawer existant**,
1648156-1 mobile /1648151-1 fixe, contacts #4 M5 6648335-1 /1766283-1.
Son boîtier comporte 32 logements de signal et huit de puissance ; seuls
deux de puissance sont utilisés. La [famille TE](https://www.te.com/en/products/brands/elcon/elcon-drawer-connectors.html)
est documentée blind-mate, flottante et hot-plug. Cela ne qualifie pas
l'interruption des contacts #4 à 100 A. Échange au sol, désarmé, **JETI OFF
et courant puissance nul** avant extraction ; ON seulement après insertion
et verrouillage. L'état ON mémorisé impose de commander OFF avant déconnexion.
Les instructions TE114-13206, notamment dressage, rayon, liberté et distance
au premier collier, restent à valider dans cette application.

| Alternative vérifiée | Motif de non-sélection pour ce prototype |
|---|---|
| DuraSwap Concentric 2+6, 100A/4AWG, 10000cycles | [GS20-0895 §6.7](https://cdn.amphenol-cs.com/media/wysiwyg/files/documentation/gs-20-0895.pdf) interdit tout contact puissance ou signal sous potentiel pendant l'accouplement. Le TX JBD peut rester alimenté, même avec DSG OFF ; JETI OFF ne résout pas cette condition. AWG8 et terminaisons resteraient aussi à confirmer. |
| Floating Mate2+12 | 100cycles catalogue ; déclassement et durée de vie mission non démontrés. |
| BSC BSC1A1C-000/001, 2+8 | AWG8 couvert par contacts usinés USCP000-203/-206 ; permission de raccordement sous potentiel et cotes complètes du cadre non établies dans le [catalogue](https://www.amphenol.co.jp/military/catalog/BSC.pdf). |
| PwrMAX G2 | PCB/busbar ; exigerait une carte et sa reprise mécanique plutôt qu'un raccordement direct au BMS commercial. |
| Anderson SBS75X | Raccordement sous potentiel possible ; courant IEC en AWG8 60–65A selon charge des auxiliaires, donc pas une chaîne100A qualifiée. |
| Anderson MARC / TE Mini Drawer1648111-1 | Calibre principal insuffisant ; Mini n'accepte pas les contacts #4. |

**Données via cinq contacts de signal TE**, sans prises cellules brutes :

| Fonction logique | Contact fixe candidat /douille mobile | Raccordement |
|---|---|---|
| S_GND | 1650161-1 prémate /1648325-1 | B− brut vers GND du côté TTL isolé seulement |
| S_TX | 1650155-1 /1648325-1 | TX JBD vers RX isolateur |
| S_RX | 1650155-1 /1648325-1 | RX JBD vers TX isolateur |
| S_PRESENT_A/B | 2×1650162-2 postmate /1648325-1 | Boucle mobile passive, indépendante de B− ; côté fixe NC |

Les axes CAO proviennent des cavités #20 du STEP TE ; **numéros de cavités,
vues de sertissage, dimensions complètes et séquence réelle restent à valider**.
Le registre laisse les numéros `null`. Les longueurs prémate/postmate ne
prouvent pas l'ordre relatif avec les contacts de puissance. Aucun interlock
ni précharge locale automatique n'est implémenté. Les contacts commerciaux
nouveaux sont représentés par des enveloppes provisoires, pas des plans d'usinage.

L'UART JBD est non isolé, 9600 bauds,8N1. Le connecteur indiqué J2 HY2.0-4P
porte 1=B− brut,2=RX,3=TX,4=VDD. La mention J3 ailleurs dans la notice et
le niveau logique doivent être contrôlés sur le lot. L'interface **Waveshare
USB TO RS232/485/TTL, SKU15817** est placée à l'étage fixe ; son manuel décrit
l'isolation des données et l'alimentation DC/DC isolée. Son USB rejoint le
Jetson alimenté en aval JETI. **VDD JBD et sortie5V TTL isolée restent NC**.
GND TTL=B− brut ; aucune liaison au GND USB, châssis ou blindage aval.
La variante USB TO TTL(B) non isolée ne convient pas. La réservation CAO
90×80×26mm n'est pas une cote fabricant confirmée.

Les lectures JBD03/04/05 préparent tension, courant signé, SOC, capacités,
cycles, tensions des six groupes, températures NTC accessibles, défauts et
états MOS. Les affectations NTC de la notice sont contradictoires : aucun
nombre de sondes externes ni mesure interne des cellules n'est garanti.
Les sept prises JST-XHR-7P du [Tattu](https://gensace.de/collections/semi-solid-state/products/tattu-nmc-20000mah-22-2v-5c-6s1p-lipo-battery-pack-with-xt90-s-plug)
restent dans la cassette. L'adaptation 6S au faisceau22S suit la notice et
les contrôles d'ordre/continuité/fil ouvert ; jamais supposer que les sept
premières cavités suffisent, ni intervenir sur les cellules scellées.

Le transport diagnostic est prévu en lecture seule. Le décodeur C++17,
l'identification batterie, fraîcheur des mesures et publication sont
**Planifiés**, sans compatibilité DroneCAN supposée. **PM08 reste le producteur
batterie PX4 actuel** : pas de seconde batterie fictive créée à partir du même
pack. Contrat : [UART BMS](../../hardware/electronique/cartographe/contrat_uart_bms.json).

Une protection BMS peut couper propulsion et les deux BEC du PM08 : aucune
garantie d'atterrissage après coupure brusque. Les alertes de dérive progressive
et marges PX4 se règlent au banc sur le profil mission ; ne pas inhiber ni
retarder les protections sévères. Précharge, isolement, contacts accessibles,
charge, sertissage, vibration et thermique restent **À valider**.

Schéma et registre courants : §4.3. Implantation : DOC-MEC§4.1.3.3.
Validation : DOC-VAL§12.1.9. La définition sans BMS du §6.1 est historique.

'''
def electrical(t):
 a=t.index('### 6.2 BMS');b=t.index('## 7. Architecture',a);t=t[:a]+elec+t[b:]
 diagram=(ROOT/'hardware/electronique/cartographe/cablage_global.mmd').read_text(encoding='utf-8').strip()
 t,n=re.subn(r'```mermaid\s*flowchart TB.*?```','```mermaid\n'+diagram+'\n```',t,count=1,flags=re.S);assert n==1
 t=t.replace('Batterie 6S amovible → BMS embarqué (Planifié)','Batterie 6S amovible → BMS JBD (CAO candidate Implémentée)')
 t=t.replace('### 6.1 Dock 20 Ah : raccordement direct et coupure, 4 octobre 2026','### 6.1 Définition historique sans BMS : raccordement direct, 4 octobre 2026')
 t=t.replace('| 5 octobre 2026 | BMS embarqué requis', '| 5 octobre 2026 | BMS JBD A01 commercial sélectionné, TE conservé avec5signaux/UART isolé ; CAO/schéma candidats Implémentés, courant/lot/thermiqueÀvalider (§6.2) |\n| 5 octobre 2026 | Préparation initiale BMS embarqué requis')
 return t
change('docs/architecture/ARCHITECTURE_ELECTRIQUE_RESEAUX.md',electrical)

mec='''##### 4.1.3.3 BMS embarqué et compartiment d'interface — 5 octobre 2026

`ELEC-BMS-001` / `SAFE-REQ-011` : BMS **JBD-SP22S003 Li-ion A01 100A**
solidaire de la cassette. Réalisation CAO **Implémentée**, dimensions équipées,
fixation, masse, courant et physique **À valider**. Le TE Middle Drawer
1648156-1/1648151-1 est conservé et reçoit cinq signaux ; raisons et
références de contacts dans DOC-ELEC§6.2. Aucun effort d'accouplement ne doit
passer par les cellules ou le PCB.

Sur le dessus du pack, le plateau àZ103 ne laisse que5mm nominaux ou3mm
avec l'enveloppe d'étude : insuffisant pour ce PCB. L'ancien P43 offrait
94×42mm de cavité utile, déjà occupée. La carte est donc horizontale dans
le compartiment arrière, avec enveloppe maximale documentée **130,5×65,5×12mm**
à X−239…−108,5, Y±32,75, Z50…62. Les prises, bornes et dissipateur ne sont
pas inclus dans ces cotes ; leurs passages sont explicitement réservés,
sans position fabricant inventée.

P43/P44 évoluent en place : emprise **142×76mm**, fondZ47, capotZ100,5…102,5.
Le TE recule de44mm supplémentaires, soit126mm depuis l'implantation
frontale historique ; P39/P40 gardent leurs ancrages et rallongent leurs bras.
Cela ajoute44mm en longueur à l'étude sans BMS, **sans augmenter la hauteur**
du coffret. La largeur suit celle du pack nominal ; aucune comparaison
de volume dock seul/distribution complète ni gain de masse n'est revendiqué.
Le cantilever et le jeu nominal capot/plateau0,5mm restent à qualifier.

Un appui isolant P58 de1mm est représenté sous le PCB. La retenue positive,
visserie, procédé, rigidité et thermique restent à définir ; aucun trou
fabricant ni taraudage n'est ajouté au BMS. P51/P52 et leur visserie sont
retirés de la configuration active ; JST et B0…B6 restent dans P43. Le
fil négatif du pack arrive au BMS, et une nouvelle liaison P− protégée
va au TE. Le positif reste commun. XT90-S et barresP42 restent retirés.

À l'étage inférieur, JETI/PM08/PDB conservent leurs positions. L'interface
Waveshare15817 isolée est une **réservation90×80×26mm**, pas une cote OEM
confirmée ; ports, fixation et accès USB doivent être relevés sur le lot.
Les contacts #20 sont provisoires ; axes de cavités issus du STEP TE,
numérotation réelle et sertissage non libérés pour fabrication.

SA08 et ses références de câbles sont recotés sur les sorties courantes et
liés à **Integration_Stack_Revue_20261003.FCStd**, conservé en place. Les
points de passage réservés n'attestent pas une prise accouplée. GNSS et
plusieurs équipements de mission restent candidats ; l'intégration locale
ne constitue pas un drone final qualifié.

Sources et placements dans le manifeste, BOM et nomenclature courants.
Preuve BMS : `verification/controle_bms_cassette.json` ; faisceau : registre
SA08 courant. Les preuves de l'étape sans BMS sont historiques et ne
certifient pas les nouvelles empreintes. Les recettes anciennes refusent
la configuration BMS afin de ne pas rétablir leurs anciens placements.
Validation et limites : DOC-VAL§12.1.9.

'''
def mechanical(t):
 a=t.index('##### 4.1.3.3 BMS');b=t.index('### 4.2 Isolation',a);t=t[:a]+mec+t[b:]
 return t.replace('| 5 octobre 2026 | BMS solidaire de la cassette Planifié', '| 5 octobre 2026 | BMS commercial etappuiP58 implémentés encassette ; P43/P44 élargis142×76, TEreculadditionnel44mm et5signaux, interfaceisoléeétagefixe, SA08recoté intégré ; physiqueÀvalider (§4.1.3.3) |\n| 5 octobre 2026 | Préparationinitiale BMS solidaire de la cassette Planifié')
change('docs/architecture/ARCHITECTURE_MECANIQUE.md',mechanical)

def hld(t):
 t=t.replace('**Planifié**, choix et intégration **À valider**. Le BMS surveille/protège','CAO et schéma candidats **Implémentés**, réception et qualification\n+  **À valider** : JBD-SP22S003 A01 100A, TE existant avec UART isolé. Le BMS surveille/protège'.replace('\n+','\n'))
 t=t.replace('**Planifié / À valider** ; DOC-ELEC `ELEC-BMS-001`, DOC-VAL §12.1.9.','CAO/schéma **Implémentés**, protection physique **À valider** ; DOC-ELEC `ELEC-BMS-001`, DOC-VAL §12.1.9.')
 return t.replace('| 5 octobre 2026 | BMS embarqué dans chaque cassette', '| 5 octobre 2026 | BMScommercialJBD/TE/UARTisolé intégrés enCAO etschéma ; diagnosticlogicielPlanifié, PM08 conservé sourcePX4, physiqueÀvalider |\n| 5 octobre 2026 | Besoininitial BMS embarqué dans chaque cassette')
change('docs/architecture/HLD.md',hld)

sw='''#### 7.1.2 Diagnostic BMS de cassette — Planifié / À valider, 5 octobre 2026

La conception électrique représente JBD-SP22S003 A01 via TE, UART isolé
Waveshare15817 et USB Jetson. Le décodeur et son intégration restent
**Planifiés** : aucune nouvelle logique embarquée n'est implémentée par
la modification CAO. Contrat déclaratif :
[UART BMS](../../hardware/electronique/cartographe/contrat_uart_bms.json).

Un futur adaptateur C++17 devra vérifier longueur, checksum JBD, unités,
courant signé, nombre de cellules, délais et fraîcheur. Les lectures03/04/05
préparent tension, SOC, capacité, cycles, cellules, NTC, protections et MOS ;
commandes d'écriture et modification des seuils interdites dans le diagnostic.
PM08 conserve la mesure batterie utilisée par PX4. Identifier et arbitrer
les producteurs avant publication, sans compter deux batteries pour un
seul pack. Aucun protocole DroneCAN n'est supposé et aucun moteur commandé.
Jeux de trames, corruption, perte de port, retard et identité seront testés
hors ligne puis au banc avant intégration PX4. DOC-ELEC§6.2, DOC-VAL§12.1.9.

'''
change('docs/architecture/ARCHITECTURE_LOGICIELLE.md',lambda t:t if '#### 7.1.2 Diagnostic BMS' in t else t.replace('### 7.2 Allocation algorithmique',sw+'### 7.2 Allocation algorithmique'))

val='''### 12.1.9 BMS de cassette et connecteur d'échange — 5 octobre 2026

`SAFE-REQ-011` / `ELEC-BMS-001` → JBD-SP22S003 A01, TE5signaux,
isolationUART et SA08 → contrôles natifs et schéma courants. CAO et schéma
**Implémentés**, qualification matérielle **À valider**. Les preuves
de l'étape sans BMS (§12.1.8) et leurs anciennes empreintes sont historiques.

Preuves : [CAO BMS](../hardware/mecanique/cartographe/verification/controle_bms_cassette.json),
[câblage](../hardware/electronique/cartographe/verification/cablage_global_bms.json),
nomenclature et manifeste courants ; revue indépendante finale dans
`hardware/mecanique/cartographe/verification/revue_bms_cassette.json`.
Relecture dans un processus FreeCAD neuf : liens, recalcul, enveloppe PCB,
collisions et extraction échantillonnée0/10/25/50/100/200/350/500mm. Les
recouvrements intentionnels aux terminaisons sont énumérés avec leur motif,
séparément des collisions non résolues. Cela ne valide pas les prises de
lot, les tolérances ni une course continue. SA08 est contrôlé séparément.

Le vérificateur électrique couvre27modules,40liaisons,28brochesCA01 et
trois trames de requête JBD03/04/05 avec checksum. Le diagramme Mermaid
est synchronisé avec DOC-ELEC. Aucun test de décodeur exécutable, de
communication réelle ni de courant n'est confondu avec ces contrôles.

| Essai | Critères restant à fermer | État |
|---|---|---|
| T-CARTO-BMS-01 réception/interface pack | lotA01, chimie6S, ordreB0…B6/JST, adaptation22S, fil ouvert, NTC, J2/J3, niveauTTL | Planifié, pas de matériel |
| T-CARTO-BMS-02 implantation/extraction | PCBtolérancé représenté ; modèle équipé, bornes, dissipateur, fixations, jeux, extractioncontinue, rigidité et masse à accepter | CAO Implémentée, physique À valider |
| T-CARTO-BMS-03 puissance/charge/thermique | courantmission, pertes, pointes, chargeprotégée, précharge et températures selonOEM | Planifié ;100A système non qualifié |
| T-CARTO-BMS-04 coupures/communication | aucunevoieB−brut versavionique, isolationsdata+DC/DC, VDD/5VNC, mappingTE etportsréels, parser/identité/fraîcheur | Topologiedéclarativecontrôlée ; banc etlogiciel Planifiés |
| T-CARTO-BMS-05 alerte/protection coordonnée | margesPX4pour dérivesprogressives, défauts sévères immédiats, perte de mesure ; aucuneinhibitionprotections | Planifié, pas d'essai nouveau |
| T-CARTO-BMS-06 cycles/environnement | nombreéchangesmission, retenue, guidage/flottement, touchsafe, intrusion etvibration | Planifié, objectifs à fermer |

Une coupure BMS supprime propulsion et les deux BEC du PM08 ; POWER1/2 ne
constituent pas un secours à cette cause commune. Les lectures BMS sont
diagnostiques ; PM08 reste source PX4 actuelle. Non exécutés : réception,
sertissage, isolation physique, dissipation100A, charge, vibration, cycles,
matériel embarqué et vol, faute de lot/banc. Aucun résultat **Qualifié**.

'''
def validation(t):
 a=t.index('### 12.1.9 BMS');b=t.index('### 12.2 ',a);t=t[:a]+val+t[b:]
 t=t.replace('implantation, charge, protections, communication et cycles à valider ; aucun BMS ajouté en CAO ni nouvel essai matériel | **Planifié / À valider**','CAO JBD/TE et schéma40liaisons implémentés ; charge/thermique/isolation/logiciel/cycles à valider, aucun essai matériel | CAO/schéma **Implémentés**, physique **À valider**')
 return t.replace('| 5 octobre 2026 | Plan de validation BMS', '| 5 octobre 2026 | ContrôlesCAOBMS/UART/TE etschéma40liaisons, revueindépendante etempreintescourantes ; limitesphysiquesnonqualifiées (§12.1.9) |\n| 5 octobre 2026 | Préparationinitiale Plan de validation BMS')
change('docs/VALIDATION_QUALIFICATION.md',validation)
print('Cinq documents vivants actualisés')
