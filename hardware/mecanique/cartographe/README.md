# Cartographe — dernières implémentations FreeCAD

Ouvrir [Integration_Stack_Revue_20261003.FCStd](assemblages/Integration_Stack_Revue_20261003.FCStd)
pour la dernière intégration mécanique locale : châssis, batterie mobile,
récepteur fixe, stack, bloc capteurs et faisceau SA08. JETI, PM08-CAN, PDB,
P57, commande et isolateurUART sont directement liés au principal. Le GNSS reste un sous-assemblage
séparé ; cette étude locale n'est pas un drone complet qualifié.

Le catalogue courant est `manifest.json`, clé `catalogue_courant_20261004`.
Conserver toute l'arborescence pour résoudre les liens externes. Les références
de pièces achetées/fabriquées restent dans `pieces/`.
Les dernières vues natives de la stack sont dans
[la galerie FreeCAD](exports/stack_avionique_revue_20261003/index.html).

## Sous-assemblages à ouvrir

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

## Archives et maintenance

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
natifs et leurs dépendances sont suivis par Git. La sauvegarde `94d04d0`
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
