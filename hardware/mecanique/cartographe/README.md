# Cartographe — prototype actif et études FreeCAD

Dernière mise à jour : 22 octobre 2026.

Ouvrir [Prototype_Cartographe.FCStd](assemblages/Prototype_Cartographe.FCStd)
pour le prototype actif sans dock. Conserver l'arborescence du répertoire
pour résoudre ses liens externes. La construction est **Implémenté** ;
les contrôles numériques portent sur les fichiers finaux reconstruits,
qualification physique **À valider**.
Les choix et limites sont dans
[DOC-MEC §2.2](../../../docs/architecture/ARCHITECTURE_MECANIQUE.md#assemblage-prototype).

## Ouvrir le prototype

| Fonction | Sous-assemblage |
|---|---|
| Structure et propulsion | [SA01_Prototype_Structure.FCStd](sous_assemblages/SA01_Prototype_Structure.FCStd) |
| Batterie et BMS | [SA02_Prototype_Batterie.FCStd](sous_assemblages/SA02_Prototype_Batterie.FCStd) |
| Énergie et isolation UART | [SA03_Prototype_Energie.FCStd](sous_assemblages/SA03_Prototype_Energie.FCStd) |
| Perception isolée | [SA04_Prototype_Perception.FCStd](sous_assemblages/SA04_Prototype_Perception.FCStd) |
| Avionique et refroidissement | [SA05_Prototype_Avionique.FCStd](sous_assemblages/SA05_Prototype_Avionique.FCStd) |
| Navigation, radio et sécurité | [SA06_Prototype_Navigation.FCStd](sous_assemblages/SA06_Prototype_Navigation.FCStd) |
| Faisceaux Cable Workbench | [SA07_Prototype_Faisceaux.FCStd](sous_assemblages/SA07_Prototype_Faisceaux.FCStd) |

Les pièces P60–P80 se trouvent dans `pieces/fabriquees/`.
Pour connaître les références réemployées et les objets inclus,
consulter [`verification/construction_prototype.json`](verification/construction_prototype.json).
L’énergie SA03 occupe désormais le plateau central supérieur.

L’extension **Cables Workbench 0.3.7** est requise pour modifier et recalculer
les câbles du prototype. Conserver son installation dans le profil FreeCAD
actif. Les 53 parcours de
[`verification/routes_prototype.json`](verification/routes_prototype.json)
possèdent des objets Cable et WireFlex ; leurs contrôles numériques
ne constituent pas des longueurs de coupe libérées. Ouvrir une pièce
de faisceau liée pour éditer sa courbe ou son diamètre, puis recalculer les
sous-assemblages et l’assemblage principal.

Le contrôle de réouverture s'exécute dans un processus FreeCAD distinct,
depuis ce répertoire, après finalisation de la construction :

```powershell
& 'C:/Program Files/FreeCAD 1.1/bin/python.exe' verification/verify_prototype.py
& 'C:/Program Files/FreeCAD 1.1/bin/python.exe' verification/verify_fixations_prototype.py
& 'C:/Program Files/FreeCAD 1.1/bin/python.exe' verification/verify_faisceaux_prototype.py --geometrie-seule
& 'C:/Program Files/FreeCAD 1.1/bin/python.exe' verification/verify_faisceaux_brep_prototype.py
& 'C:/Program Files/FreeCAD 1.1/bin/python.exe' verification/verify_fixations_guides_prototype.py
& 'C:/Program Files/FreeCAD 1.1/bin/python.exe' verification/verify_pieces_prototype.py
& 'C:/Program Files/FreeCAD 1.1/bin/python.exe' verification/verify_departs_bras_prototype.py
& 'C:/Program Files/FreeCAD 1.1/bin/python.exe' verification/verify_colliers_prototype.py
& 'C:/Program Files/FreeCAD 1.1/bin/python.exe' verification/verify_retenues_faisceaux_prototype.py
& 'C:/Program Files/FreeCAD 1.1/bin/python.exe' verification/verify_fixations_equipements_prototype.py
```

Lire le périmètre et la conclusion de
[`verification/controle_assemblage_prototype.json`](verification/controle_assemblage_prototype.json)
avant d'utiliser son résultat. Consulter également les preuves de pièces, guides, départs, colliers,
retenues et équipements. La recette `verification/build_prototype.py`
réécrit les natifs du prototype : elle sert à reprendre leur construction,
pas à les ouvrir. Toute modification nécessite un nouveau contrôle des
fichiers sauvegardés puis une synchronisation des registres.

Après réussite de tous les contrôles et mise à jour de la BOM,
`verification/sync_prototype.py`
actualise la section active `prototype_cartographe` du manifeste et la
couverture BOM/CAO. Les autres sections du manifeste décrivent les études
historiques conservées. Les aperçus courants sont dans `exports/prototype/`.

La [galerie des prises de vue](exports/prototype/prises_de_vue/galerie.html)
réunit six angles d'ensemble et neuf détails en PNG. Les vues de détail
signalent leurs masquages et transparences. Pour régénérer cet export sans
modifier les natifs, lancer `verification/export_prises_de_vue_prototype.py`
avec le Python de FreeCAD.

## Consulter et contrôler la nomenclature

Pour consulter la définition du **prototype sans échange rapide**, ouvrir
[le classeur de nomenclature](exports/Nomenclature_Prototype_Cartographe.xlsx).
Le [produit custom](exports/Nomenclature_Produit_Custom_Cartographe.xlsx)
possède un fichier distinct, issu de
[nomenclature_produit_custom.json](nomenclature_produit_custom.json).
Dans chaque classeur, commencer par **Vue système**, puis ouvrir l'onglet
et la ligne indiqués pour consulter le détail du sous-système. Les références
et quantités de synthèse sont liées par formule aux détails ; ne pas les
additionner comme des composants supplémentaires. Pour le prototype, le détail
électronique est dans CA01 et la table des liaisons dans Faisceaux.
Les données sources sont dans [nomenclature_prototype.json](nomenclature_prototype.json) ;
modifier ce registre puis actualiser l'export, sans traiter le classeur comme
une source indépendante. Le classeur synchronisé a été contrôlé le
22 octobre : 108 contrôles documentaires, relecture/recalcul des formules
et inspection des lignes modifiées. Lire les réserves et les inclusions avant de sommer
des quantités ou des masses. La portée et les décisions sont dans
[DOC-MEC §5.0](../../../docs/architecture/ARCHITECTURE_MECANIQUE.md#nomenclature-prototype).
Les natifs historiques ci-dessous conservent l'étude avec dock ; ils ne sont
pas les sous-assemblages du prototype actif présenté plus haut.

Depuis la racine du dépôt, contrôler les deux registres et classeurs sauvegardés avec
`pwsh -NoProfile -File hardware/mecanique/cartographe/verification/verify_nomenclature_prototype.ps1`.
L'option `-WriteEvidence` actualise la preuve JSON voisine après réussite.
Ce contrôle documentaire ne lance ni Excel, ni FreeCAD, ni essai matériel.

## Consulter l'étude historique avec dock

Ouvrir [Integration_Stack_Revue_20261003.FCStd](assemblages/Integration_Stack_Revue_20261003.FCStd)
pour l'intégration mécanique historique : châssis, batterie mobile,
récepteur fixe, stack, bloc capteurs et faisceau SA08. JETI, PM08-CAN, PDB,
P57, commande et isolateurUART sont directement liés au principal. Le GNSS reste un sous-assemblage
séparé ; cette étude locale n'est pas un drone complet qualifié.

Le catalogue de ce rangement historique est `manifest.json`, clé `catalogue_courant_20261004`.
Conserver toute l'arborescence pour résoudre les liens externes. Les références
de pièces achetées/fabriquées restent dans `pieces/`.
Les dernières vues natives de la stack sont dans
[la galerie FreeCAD](exports/stack_avionique_revue_20261003/index.html).

### Sous-assemblages de l'étude avec dock

| Fonction | Fichier courant |
|---|---|
| Châssis et plaque basse reprise | [SA01_Chassis_Stack_Revue_20261003.FCStd](sous_assemblages/SA01_Chassis_Stack_Revue_20261003.FCStd) |
| Récepteur fixe20Ah,72 pièces | [SA02A_Dock20Ah.FCStd](sous_assemblages/SA02A_Dock20Ah.FCStd) |
| Stack Holybro/CA01 revue | [SA03_CA01_Holybro_Revue_20261003.FCStd](sous_assemblages/SA03_CA01_Holybro_Revue_20261003.FCStd) |
| Capteurs avec appuis | [SA05_Capteurs_Isoles.FCStd](sous_assemblages/SA05_Capteurs_Isoles.FCStd) |
| Bloc optique/LiDAR | [SA05A_Bloc_capteurs.FCStd](sous_assemblages/SA05A_Bloc_capteurs.FCStd) |
| Appui Sorbothane réutilisé quatre fois | [SA05B_Appui_Sorbothane.FCStd](sous_assemblages/SA05B_Appui_Sorbothane.FCStd) |
| GNSS Helical G4 candidat | [SA06_RTK_Helical_Systeme_Candidat.FCStd](sous_assemblages/SA06_RTK_Helical_Systeme_Candidat.FCStd) |
| Montage historique énergie, non installé | [SA07_Distribution_Systeme_Candidat.FCStd](sous_assemblages/SA07_Distribution_Systeme_Candidat.FCStd) |
| Station sol, dernière représentation disponible | [SA07_Station_sol.FCStd](sous_assemblages/SA07_Station_sol.FCStd) |
| Réservations de faisceau, passages À valider | [SA08_Faisceau_Systeme_Candidat.FCStd](sous_assemblages/SA08_Faisceau_Systeme_Candidat.FCStd) |
| Batterie20Ah mobile avec BMS,67 pièces | [SA02_Cassette20Ah_Coulissante.FCStd](sous_assemblages/SA02_Cassette20Ah_Coulissante.FCStd) |
| Montage historique contacts, non installé | [SA02_Contacts20Ah.FCStd](sous_assemblages/SA02_Contacts20Ah.FCStd) |

L'antenne GNSS sur le plateau supérieur et le récepteur GNSS sous la batterie
restent une option étudiée ; les fichiers conservés gardent leur pose précédente.
Le faisceau SA08 est lié à la stack revue ; son recalage suit le BMS au-dessus
du pack et le TE rapproché. Après le dernier rapprochement et remplacement
de la chambre de fils par des protections locales, le contrôle complet des37
routes et leur relecture native finale sont réussis, avec identité géométrique
et empreintes concordantes. Relancer les contrôles après
toute modification des sources et rattacher leurs empreintes finales.
Les limites physiques,
la BOM et les validations sont dans [DOC-MEC](../../../docs/architecture/ARCHITECTURE_MECANIQUE.md),
[DOC-ELEC](../../../docs/architecture/ARCHITECTURE_ELECTRIQUE_RESEAUX.md)
et [DOC-VAL](../../../docs/VALIDATION_QUALIFICATION.md).

## Archives et maintenance historique

Les instructions ci-dessous concernent uniquement l'étude avec dock. Elles
ne reconstruisent pas `Prototype_Cartographe` et ne doivent pas être utilisées
pour maintenir ses sept sous-assemblages.

Les anciens sous-assemblages, assemblages globaux et sauvegardes sont dans
`archives/avant_tri_20261004/`. Cette archive contient une copie des pièces
et des montages liés sous les mêmes chemins relatifs : ouvrir les natifs
depuis cette arborescence entière. `manifest.json` et `README.md` archivés
sont des instantanés antérieurs au tri ; leur contexte de commandes est historique.
Les recettes historiques du 6 septembre au 3 octobre restent des preuves de
construction ; elles ne constituent pas une commande générale de régénération
du catalogue courant et peuvent recréer des variantes retirées.

Ouvrir séparément la batterie `SA02_Cassette20Ah_Coulissante` et son récepteur
`SA02A_Dock20Ah`, ou le principal pour voir leur montage. `SA02_Contacts20Ah`
et `SA07_Distribution_Systeme_Candidat` sont conservés comme montages historiques
non installés ; ne pas les ajouter au principal ni à la nomenclature installée.
Conserver les noms des fichiers et les faire évoluer en place. Les petits
natifs explicitement autorisés sont suivis par Git. Les modèles fabricant
`EQ_Chassis_X650.FCStd`, `EQ_Holybro_Pixhawk_Jetson_Baseboard_candidat.FCStd`,
`EQ_Airy.FCStd` et `EQ_Basler.FCStd` restent des dépendances locales ignorées :
un clone seul ne permet pas de rouvrir tous les assemblages. Restaurer ces
sources depuis les références du manifeste avant utilisation. La sauvegarde `94d04d0`
conserve l'implantation BMS arrière ; la conception courante place le BMS
au-dessus du pack, avec le plateau rehaussé et le raccordement TE compact.
La sauvegarde `1ccbad81` conserve le premier étage supérieur avant ce dernier
compactage. Lire `verification/compactage_raccord_bms_te.json` pour les
mesures après recalcul, et non le cache auteur immédiatement enregistré.
Les noms historiques des pièces
et assemblages, dont P37 «70», ne décrivent pas nécessairement leurs cotes
courantes : consulter les paramètres natifs et le manifeste.

Les recettes sans BMS et les contrôles de compacité/étage énergie antérieurs
sont historiques ; ne pas les rejouer pour maintenir cette implantation.
`persist_etage_batterie.py` et les anciennes finalisations ne remplacent pas
la recette BMS courante. Les scripts ci-dessous s'exécutent depuis ce
répertoire, avec le Python fourni par FreeCAD1.1.

Contrôler le découpage enregistré, ses placements et ses liens :

```powershell
& 'C:/Program Files/FreeCAD 1.1/bin/python.exe' verification/verify_hierarchie_batterie.py
```

Pour appliquer ou reprendre le découpage fonctionnel en place :

```powershell
& 'C:/Program Files/FreeCAD 1.1/bin/python.exe' verification/update_hierarchie_batterie.py
& 'C:/Program Files/FreeCAD 1.1/bin/python.exe' verification/verify_hierarchie_batterie.py
& 'C:/Program Files/FreeCAD 1.1/bin/python.exe' verification/update_registres_hierarchie_batterie.py
```

Pour vérifier les registres sans les réécrire, puis générer les vues :

```powershell
& 'C:/Program Files/FreeCAD 1.1/bin/python.exe' verification/update_registres_hierarchie_batterie.py --check
& 'C:/Program Files/FreeCAD 1.1/bin/python.exe' verification/render_hierarchie_batterie.py
```

Lire les preuves distinctes : `verification/decoupage_sous_assemblages_batterie.json`
pour la migration et la conservation géométrique après réouverture,
`verification/controle_hierarchie_batterie.json` pour les contrôles frais,
`verification/hierarchie_batterie_recepteur.json` pour les registres/BOM, et
`verification/rendu_hierarchie_batterie.json` pour les vues. Vérifier leur
finalisation après sauvegarde. Le contrôle frais du découpage et des registres est réussi :12 liens directs,
67 mobiles/72 fixes/six pièces directes, références/poses/apparences
conservées et extraction unique aux translations0/50/500 mm. Les sources
de pièces et de faisceau sont inchangées ; les résultats du compactage
sont transférés par cette identité, sans nouveaux booléens de collision. Ces commandes réorganisent
les liens existants ; elles ne redessinent pas les modules ou les câbles.

Les anciennes recettes `update_bms_cassette.py`, `update_bms_dessus.py`,
`integrate_faisceau_bms.py` et `update_registres_bms.py` ne sont plus des
commandes de maintenance de ce découpage. Les anciennes constructions de stack,
dock et rehausse doivent le refuser avant toute mutation. Ne pas contourner
ces gardes ni reconstruire l’ancien dock complet ou SA07 installé.
Toute nouvelle modification géométrique requiert des contrôles et recettes
adaptés aux deux parents batterie/récepteur, puis une mise en concordance des
registres. Les passages restent des réservations **À valider** ; une commande
réussie ne libère pas un faisceau pour fabrication.
La nomenclature est `verification/nomenclature_etage_batterie.json` ; BOM,
faisceau et sources évoluent en place. Le branchement JBD/TE/UART isolé et ses
limites sont décrits dans DOC-ELEC§6.2, les contrôles dans DOC-VAL§12.1.9.

La recette historique de stack `verification/build_stack_revue_20261003.py`
reprend le châssis rehaussé archivé via `sources_cao_archivees_20261004.py`.
Elle n'est pas la commande de maintenance de la rehausse BMS courante.
Les contrôles de tri ci-dessous conservent le périmètre historique du rangement.

Vérifier le rangement et les liens, dans des processus PythonFreeCAD séparés :

```powershell
& 'C:/Program Files/FreeCAD 1.1/bin/python.exe' verification/verify_tri_sous_assemblages_20261004.py courant
& 'C:/Program Files/FreeCAD 1.1/bin/python.exe' verification/verify_tri_sous_assemblages_20261004.py archive
& 'C:/Program Files/FreeCAD 1.1/bin/python.exe' verification/verify_tri_sous_assemblages_20261004.py source_stack
```

Ces commandes s'exécutent depuis le répertoire cartographe. Leurs assertions
de catalogue précèdent le découpage batterie/récepteur ; elles vérifient
le rangement historique, pas la nouvelle hiérarchie installée.

Les BMS, contacts de signal et ports accouplés restent des enveloppes
candidates. Conserver les sources fabricant inchangées et vérifier les limites
du manifeste et de DOC-ELEC avant toute fabrication ou connexion réelle.
