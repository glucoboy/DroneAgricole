# GO3A — comparaison des variantes d’architecture

Périmètre commun `prototype_cartographe` sans dock, dossiers GO2bis et Action 3.
Ce tableau accompagne la définition gelée. **À valider**, cible conditionnelle
`H-01`. [Critères GO3A](GO3A_REQUIREMENTS.yaml) ·
[Preuves de comparaison et rejeu](GO3A_VARIANT_EVIDENCE.json)

## Critères de comparaison

- **G3A-01 et G3A-02** — Couvrir les 71 lignes, 53 axes et 56 associations documentaires. Conserver la continuité fonctionnelle, les retours, les protections 6S, la chaîne PM08–PX4 et les commandes de propulsion. Vérifier les débits, tensions, courants continus et crêtes dans leur domaine réel.
- **G3A-03 à G3A-05** — Vérifier les ports, l’identité des fiches, les niveaux et le brochage. Contrôler les débattements caméra/M8, les champs optiques, l’enveloppe de service CAN1 et l’accès simultané USB/TTL du diagnostic. Évaluer le geste complet, la réserve, l’outil et les obstacles dans la même pose.
- **G3A-06 et G3A-07** — Préserver les chemins d’efforts, retenues et fixations, les zones GNSS/RF et de propulsion, le flux d’air, l’accès SSD/CSI et l’isolant de la branche brute. Maintenir des corridors dédiés là où courant, chaleur, blindage, retours ou maintenabilité laissent la cohabitation ouverte.
- **G3A-08** — Comparer au même périmètre de natifs et de liaisons, avec une tolérance issue des références réelles. Mesurer les axes en baie, au-dessus et sous les plateaux, la cote haute et `L × l × H` avec les fiches en service. Mesurer séparément volumes de manœuvre, distance minimale par paire, rayon, réserves utiles, nombre de supports et d’interfaces, masse et coût. Une inconnue critique empêche l’admission. Une géométrie tangentielle exige l’examen de la paire, de la tolérance et du contact fonctionnel. [Exigences et critères de réception](GO3A_REQUIREMENTS.yaml)

## Variantes étudiées

| Variante | Implantation et changement de BOM | Résultat et décision |
|---|---|---|
| **A — corridors à équipements fixes** | Énergie sous P66 là où l’espace réel le permet, retournements aux chants, dérivations courtes par face de sortie, branches de bras en parallèle sur supports existants. Tronc Airy OEM complet, portions mobiles caméra/M8 libres, zones RF et commandes distinctes. Aucune nouvelle carte. Retenues, protections et câbles susceptibles d’évoluer. | La copie historique par faces réduit l’axe en baie de 361,237 mm et au-dessus de la porteuse de 249,170 mm. Le besoin de descendre au chant se confirme par le criblage des jeux intercartes. Reprendre ces principes et le trajet F12 corrigé. Écarter A seule avec fiches droites aux positions testées, faute de service simultané F40/F41 et de preuve complète de gestuelle CAN1. |
| **B — connectique et implantation** | Comparer les orientations de départ, le retrait de CAN1 avec F35 au sud, les deux côtés du PM08, l’isolateur et une fiche USB-B coudée. Reprendre F25 sur le chant est avec P85 comme support candidat. Préférer les interfaces OEM traçables. | Retenir F35 sud et le témoin droit GH4 pour CAN1. La fiche seule obtient 4,10 mm face à F35 dans l’essai, l’outil candidat seulement 0,120 mm face à F31. Conserver PM08 en pose ORCH. Les déplacements +Y8 et rotations d’isolateur n’ont donné aucun accès simultané des deux ports dans le domaine testé. Le Delock 84809 est un cordon candidat dont les encombrements et la réserve restent ouverts. [Essai CAN1](../cartographe_action3_can1_integre.json) · [Essai diagnostic](../cartographe_action3_f41.json) · [Fiche Delock](https://www.delock.com/produkt/84809/pdf.html?sprache=en) |
| **C — redistribution ciblée** | Déporter passivement la connexion de service TTL prévue par le graphe et l’accès USB de part et d’autre de l’isolateur existant. Examiner la redistribution CA01 J505/J506/J509 et une PDB latérale comme alternatives. | Poursuivre uniquement l’architecture passive de diagnostic. La PDB 18139 latérale a recoupé F02_2 à la pose de repli historique. Une rotation ou reprise de CA01 accroît les liaisons et accès à revalider et garde F24A/CSI ouverts. Le passif de synchronisation pourrait modifier retours, fronts et référence 3,3 V. Une interface active introduirait alimentation, modes de panne et validation supplémentaires. Reporter ces options, sans besoin de service supplémentaire démontré. [Comparaisons historiques C](../cartographe_action3_architectures.json) |
| **H-01 — combinaison proposée** | Corridors A et conservation des équipements et circuits de base, avec corrections F12, F35, F25/P85 et F16 instruites sur copie. Reprise des accès de B à ports électriques constants. Déport limité au diagnostic F40/F41, sans modification électrique de la distribution de puissance ou de CA01. | Architecture de référence pour l’instruction. Les jeux, la réserve, la tenue et les interfaces doivent converger dans un seul référentiel. L’arbre de fichiers de la copie Action 3 fournit un témoin pour les changements déjà testés ensemble. Le déport et les autres décisions encore ouvertes restent à démontrer. |

Molex `5024390600` fournit un boîtier à six voies au pas de 2 mm avec
verrou et détrompage. Holybro donne la famille CLIK-Mate 6 voies pour le
PM08-CAN. Le plan et la révision exacts de l’embase, les contacts et le
brochage du cordon restent nécessaires pour établir la compatibilité. Les
185 g annoncés par Holybro incluent des câbles. Le poids net installé reste
ouvert en présence de coupes et d’allongements. [Molex](https://www.molex.com/en-us/products/part-detail/5024390600) ·
[Holybro](https://docs.holybro.com/power-module-and-pdb/power-module-comparison)

## Mesures comparables

Les deux couples de mesure ont chacun 53 axes. Les colonnes utilisent le
même calcul de zone au sein de chaque couple, les configurations diffèrent
entre couples. Les zones se recouvrent. Une longueur en zone décrit une
occupation par les axes. Les connecteurs, les câbles en place et leur
enveloppe de service restent à sommer et à mesurer séparément. [A et par faces](../cartographe_action3_architectures.json) ·
[Actif et copie intégrée](../cartographe_action3_integre.json)

| Couple et état | Axe total (mm) | En baie (mm) | Au-dessus (mm) | Sous P66 emprise stricte (mm) | Cote haute (mm) |
|---|---:|---:|---:|---:|---:|
| A historique | 10 885,079 | 4 221,879 | 2 051,213 | 451,202 | 170,278 |
| Par faces historique | 10 788,378 | 3 860,643 | 1 802,043 | 451,202 | 170,278 |
| Écart par faces | −96,701 | −361,237 | −249,170 | 0 | 0 |
| Actif mesuré avant consolidation | 12 125,900 | 4 341,486 | 2 421,421 | 451,202 | 173,278 |
| Copie F12/F16/F25/P85/F35 | 12 213,156 | 4 257,244 | 2 316,430 | 451,202 | 173,278 |
| Écart de consolidation | +87,256 | −84,242 | −104,991 | 0 | 0 |

Le volume englobant de la baie connectée, les réserves de montage, la masse
complète, l’écart de centrage, le nombre effectif de supports communs, la
capacité thermique et CEM et le coût restent indéterminés pour B, C et
H-01. Le coût de développement relatif augmente avec l’incertitude de
référence et avec l’impact de l’intervention, de A (réemploi et routage) à
B (interfaces, ancrages, réévaluation des voisins) puis à C avec
modifications de cartes (schéma, layout, ERC/DRC, fabrication et
qualification). Le coût et le délai du cordon passif restent inconnus.

### Front conditionnel

Le front admissible du cartographe est vide. H-01 préserve le graphe et les
composants coûteux à requalifier, sous réserve de résolution des fonctions
de service. B avec changement de pose présente un compromis différent
entre nombre de raccordements, masse et dégagement si le volume disponible
est confirmé. C passive présente l’autre compromis entre dépose des
modules et ajout éventuel de jonctions. Ces possibilités conditionnelles
restent incomparables sur les objectifs physiques communs. La seule
comparaison Pareto chiffrée du déport à ce stade est le banc synthétique, où
`diag-compact`, `diag-passive` et `diag-placement` sont non dominées, et
`diag-placement-braced` dominée par `diag-placement`. Le coût manque également
au banc. Le témoin `f31-shift` y obtient 8,4 mm après une translation
hypothétique de −10 mm du PM08. La mutation qui déplace F35 rétablit
l’échec. La combinaison de deux décisions diagnostic isolément favorables
échoue à −3 mm de marge commune. Ces seuils et marges appartiennent au banc
L3. [Rejeu et oracles](GO3A_VARIANT_EVIDENCE.json)

### Criblage du pied de connectique F40/F41

Dans une copie privée de la consolidation Action 3, 138 fichiers natifs
ont été contrôlés par empreinte avant et après lecture. Les 12 gabarits
ont généré 36 084 paires, dont 64 contrôles BRep et aucune paire indéterminée.
À la pose de référence, le gabarit USB-B de 50 × 11,8 × 10,2 mm recoupe P72
sur 131,274 mm³. Les profondeurs de 5 et 15 mm sont libres avec les
exclusions du criblage. La translation virtuelle +Y8 libère ce volume USB-B,
mais la PDB recoupe le gabarit TTL dès 3 × 12 × 8 mm à la pose de
référence et à +Y8, respectivement de 6,848 et 8,491 mm³. Le déport reste
conditionné à la mesure de la sortie TTL réelle et à un ordre de
préconnexion démontré. Le criblage exclut les câbles en cours de reprise
F40/F41 et le corps de leur isolateur. Ses boîtes sont des sondes nominales
de l’espace de sortie en pose, sans simulation de connecteur ni d’outil.
[Résultats du criblage](GO3A_VARIANT_EVIDENCE.json)

## Compatibilité des changements H-01

| Zone et décision | Interactions à instruire au même gel |
|---|---|
| **Puissance et CAN1** | Garder la reprise ORCH du PM08, son BEC et la chaîne d’énergie. Relire F01/F05/F06, F31/F32/F35/F38, les départs propulsion au voisinage, l’isolateur, P75 et les outils. Le test CAN1 relie une fiche candidate et des courses déterminées à 4,10 mm de jeu face à F35, et le gabarit MPT1RSV repose sur un appui hypothétique. Un cumul défavorable de 0,120 mm consommerait toute la borne nominale de la manœuvre près de F31. Le passage bas F31 historique conserve une paire indéterminée avec l’avionique. [F35](../cartographe_action3_f35.json) · [CAN1](../cartographe_action3_can1_integre.json) · [Préfiltrage F31](../cartographe_action3_rejeu.json) |
| **Temps, F24A et RF** | F12 se termine sur TELEM1 dans la copie. Préserver F24B/DEBUG, la référence F24C/CSI et le tronc Airy. Le gabarit GPIO latéral présumé de F24A rencontre F13A et P75 dans la copie intégrée. Les encoches P75 et la tangente F13A ont été testées sur une branche distincte avec une preuve locale. Conserver P75 sans nouvelle entaille jusqu’à preuve d’identité de l’embase, de tenue des ancrages P70/P72/P73 et de conservation RF. En cas de regroupement physique, garder les retours distincts et confirmer référence IO, CEM et accessibilité. [F12](../cartographe_action3_reprise_f12.json) · [F24A/GPIO](../cartographe_action3_f24a.json) |
| **Dépose F25 et structure** | Le trajet est/P85 réduit la cote haute de F25 de 12,5 mm. Les jeux nominaux de 0,05 mm au chant et de 0,307 mm vers F25 demandent une chaîne de tolérances, la prise en compte du geste de montage et le contrôle de retenue. Garder l’effort sur le porteur en dehors de la fiche GPS1, confirmer support et abrasion. Le X650 corrigé sur copie emploie quatre enveloppes simplifiées Ø5 × 90 mm avec alésage simplifié Ø2,5 mm. Les géométries OEM des verrouillages, détails de bras et appuis imposent confirmation avant qualification. [F25/P85](../cartographe_action3_f25.json) · [Substitutions X650](../cartographe_action3_x650.json) |
| **F16 USB3, M8 et optique** | Étudier le témoin `F16_R50_X200_Z10` comme ligne de base de criblage distincte du cordon final. La cote 493,459 mm correspond à un axe, les rayons R50/R24 et la portion droite de 15 mm côté V75 sont des hypothèses testées. Le témoin P17/P65 passe 27 translations discrètes à ±0,50 mm, avec ligaments nominaux de 2,80 et 2,295 mm. Les quatre poses de câble ont leur propre périmètre. Garder M8/trigger/strobe mobile et vérifier ensemble les deux cordons, butées, poses et rotations continues. Le 508 mm de catalogue manque de longueur sur le témoin et la variante de fiche Type A n’est pas établie. [F16](../cartographe_action3_f16.json) · [Recherche de longueur L1](../../electromechanical_v2/L1_CARTOGRAPHE.json) |
| **F40/F41 et service déporté** | Instruire une zone au chant ouest, hors volumes de retrait CAN1 et des départs de bras. Maintenir le raccord de coupure manuelle `J-UART-DECONNEXION` dans la branche TTL RX/TX/GND brut, côté BMS de l’isolateur. Respecter le confinement du retour brut, VDD et sortie 5 V TTL NC, chaîne UART en lecture seule et blindage USB borné au côté hôte. L’accès de service déporté pourrait multiplier les jonctions et augmenter la susceptibilité CEM, les efforts sur les prises et le temps de montage. Même avec accès extérieur, les deux connexions locales de l’isolateur et leur ordre de pose doivent être démontrés. [Contrat UART BMS](../../../hardware/electronique/cartographe/contrat_uart_bms.json) · [Diagnostic géométrique](../cartographe_action3_f41.json) |
| **Périphérie, puissance et refroidissement** | Vérifier les quatre groupes PDB–ESC–moteur et MAIN sans cohabitation non justifiée, garde rotor, rayon, fixations et bilan des protections. Conserver l’accès QS8, batterie, équilibrage, NTC et armement. Garder la maintenance FAN/SSD/CSI dans leur volume utile et laisser le débit de ventilation vérifiable. F20 est conditionnée au courant de démarrage et au raccord du ventilateur. Maintenir l’absence d’affectation des quatre LED WS2812 tant que l’attribution AUX, dont AUX1 utilisée par F33, l’alimentation et le firmware ne sont pas établis. Maintenir champs Airy/caméra et GNSS, liaison directe GNSS–antenne, impédance et rayon des RF. [Matrice des liaisons](GO3A_INTERCONNECTION_MATRIX.csv) · [DOC-ELEC](../../architecture/ARCHITECTURE_ELECTRIQUE_RESEAUX.md) |

### Ordre de reprise

1. Lever les inconnues de lot et d’interface qui commandent les réservations
   et le graphe. Vérifier simultanément CAN1/F35 et l’accès F40/F41, avec
   PM08, isolateur, PDB, supports et toutes les branches voisines présents.
2. Soumettre ensemble F12, F25/P85, F35, F16/M8 et le chantier GPIO à contrôle
   de géométrie, de service et de BOM sur une seule copie. Les résultats des
   branches Action 3 sont des observations séparées. Leurs marges, offsets
   et états de supports ne s’additionnent pas.
3. Lever l’écart de validation électrique indépendante rattachée aux natifs
   et la fermeture XLink sur périmètre complet. Enregistrer les critères du
   prochain niveau, puis réserver à GO4 les mesures de montage, d’effort,
   de fatigue, de vibration, de thermique/CEM et de fonctionnement matériel.
   [Passage GO3B](GO3A_HANDOFF.md) · [Périmètre autorisé GO2bis](../../VALIDATION_QUALIFICATION.md#qualification-moteur-go2bis)
