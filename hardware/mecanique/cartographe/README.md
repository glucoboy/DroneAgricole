# Cartographe — dernières implémentations FreeCAD

Ouvrir [Integration_Stack_Revue_20261003.FCStd](assemblages/Integration_Stack_Revue_20261003.FCStd)
pour la dernière intégration mécanique locale : châssis, dock20Ah, stack,
bloc capteurs, distribution et faisceau SA08 recoté. Le GNSS reste un sous-assemblage
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
| Dock batterie20Ah complet | [SA02A_Dock20Ah.FCStd](sous_assemblages/SA02A_Dock20Ah.FCStd) |
| Stack Holybro/CA01 revue | [SA03_CA01_Holybro_Revue_20261003.FCStd](sous_assemblages/SA03_CA01_Holybro_Revue_20261003.FCStd) |
| Capteurs avec appuis | [SA05_Capteurs_Isoles.FCStd](sous_assemblages/SA05_Capteurs_Isoles.FCStd) |
| Bloc optique/LiDAR | [SA05A_Bloc_capteurs.FCStd](sous_assemblages/SA05A_Bloc_capteurs.FCStd) |
| Appui Sorbothane réutilisé quatre fois | [SA05B_Appui_Sorbothane.FCStd](sous_assemblages/SA05B_Appui_Sorbothane.FCStd) |
| GNSS Helical G4 candidat | [SA06_RTK_Helical_Systeme_Candidat.FCStd](sous_assemblages/SA06_RTK_Helical_Systeme_Candidat.FCStd) |
| Étage inférieur : JETI, PM08-CAN et PDB candidats | [SA07_Distribution_Systeme_Candidat.FCStd](sous_assemblages/SA07_Distribution_Systeme_Candidat.FCStd) |
| Station sol, dernière représentation disponible | [SA07_Station_sol.FCStd](sous_assemblages/SA07_Station_sol.FCStd) |
| Réservations de faisceau, passages À valider | [SA08_Faisceau_Systeme_Candidat.FCStd](sous_assemblages/SA08_Faisceau_Systeme_Candidat.FCStd) |
| Construction : cassette coulissante | [SA02_Cassette20Ah_Coulissante.FCStd](sous_assemblages/SA02_Cassette20Ah_Coulissante.FCStd) |
| Construction : contacts dock | [SA02_Contacts20Ah.FCStd](sous_assemblages/SA02_Contacts20Ah.FCStd) |

L'antenne GNSS sur le plateau supérieur et le récepteur sous la batterie
restent une option étudiée ; les fichiers conservés gardent leur pose précédente.
Le faisceau système n'est pas recalé sur la stack revue. Les limites physiques,
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

Le dock dépend encore des montages de construction `SA02_Cassette20Ah_Coulissante`
et `SA02_Contacts20Ah`, conservés dans le dossier courant.
Conserver les noms des fichiers et les faire évoluer en place. Les petits
natifs du dock et leurs dépendances sont suivis par Git ; état avant déplacement
de l'énergie sur `codex/batterie-avant-etage-inferieur`. Le contrôle courant est
`verification/verify_etage_batterie.py`. Les contrôles de compacité antérieurs
portent sur une définition historique.
L'état de conception courant est sauvegardé sur la branche locale
`codex/batterie-etage-inferieur`, sans changer l'index de travail utilisateur.
Les contrôles de tri ci-dessous portent les empreintes historiques du tri.
Pour réappliquer la visibilité et les couleurs courantes, utiliser
`verification/persist_etage_batterie.py`. Pour contrôler et afficher les natifs
courants, utiliser les commandes ci-dessous ; les rendus sont produits depuis
les sources enregistrées, sans les modifier. Les recettes de migration
`update_raccordement_direct_batterie.py`, `canonical_positions_etage_batterie.py`,
`update_faisceau_etage_batterie.py` et `finalize_etage_batterie.py` documentent
les étapes de construction ; elles ne remplacent pas l'ouverture des natifs
courants et ne doivent pas être lancées isolément pour restaurer un état.

```powershell
& 'C:/Program Files/FreeCAD 1.1/bin/python.exe' verification/verify_etage_batterie.py
& 'C:/Program Files/FreeCAD 1.1/bin/python.exe' verification/verify_registres_etage_batterie.py
& 'C:/Program Files/FreeCAD 1.1/bin/python.exe' verification/render_etage_batterie.py
```

La nomenclature actuelle est `verification/nomenclature_etage_batterie.json` ;
les fichiers BOM et faisceau existants sont actualisés en place. Le raccordement
aval JETI/PM08/PDB et les fixations physiques restent à définir.
La recette de stack `verification/build_stack_revue_20261003.py` reprend
le châssis rehaussé archivé et rétablit ses liens vers les pièces courantes
avec `sources_cao_archivees_20261004.py`. La reprise de source a été vérifiée ;
la stack n'a pas été régénérée à l'occasion du tri.

Vérifier le rangement et les liens, dans des processus PythonFreeCAD séparés :

```powershell
& 'C:/Program Files/FreeCAD 1.1/bin/python.exe' verification/verify_tri_sous_assemblages_20261004.py courant
& 'C:/Program Files/FreeCAD 1.1/bin/python.exe' verification/verify_tri_sous_assemblages_20261004.py archive
& 'C:/Program Files/FreeCAD 1.1/bin/python.exe' verification/verify_tri_sous_assemblages_20261004.py source_stack
```

Ces commandes s'exécutent depuis le répertoire cartographe. Le tri et les
contrôles ne modifient aucun placement ni géométrie native.

Pour faire évoluer la configuration BMS en place, exécuter avec Python FreeCAD
`verification/update_bms_cassette.py`, puis la recette SA08 courante,
`verification/verify_bms_cassette.py` et `verification/update_registres_bms.py`.
Les anciennes recettes sans BMS refusent cette configuration ; retours par Git.
Le BMS et les contacts de signal restent des enveloppes candidates ;
utiliser le manifeste et DOC-ELEC§6.2 pour les limites et le contrat UART.
