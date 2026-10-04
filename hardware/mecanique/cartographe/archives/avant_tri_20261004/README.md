# Cartographe — assemblages FreeCAD

Pour revoir la stack sur le plan coté Holybro, ouvrir
`assemblages/Integration_Stack_Revue_20261003.FCStd`, ou
`sous_assemblages/SA03_CA01_Holybro_Revue_20261003.FCStd` seule, avec
toute l'arborescence liée. La galerie native est
`exports/stack_avionique_revue_20261003/index.html`.
La variante représente une fixation commune à P17 ; montage/maintenance
avec le bloccapteursSA05A déposé, qualifications selon DOC-MEC§4.4.1.1.
Les autres assemblages et leurs routes ne sont pas remplacés.

Regénérer avec PythonKiCad `verification/extract_stack_drills_20261003.py`,
puis `kicad-cli pcb export step --user-origin 50x50mm --no-dnp` vers
`exports/stack_avionique_revue_20261003/CA01_placement_courant.step`.
Avec PythonFreeCAD, exécuter `verification/build_stack_revue_20261003.py`,
puis `verification/verify_stack_revue_20261003.py` dans un processus neuf.
Exporter les vues dans une sessionFreeCAD dédiée avec
`verification/rendus_stack_revue_20261003.FCMacro`, puis exécuter
`verification/update_stack_registry_20261003.py` pour le manifeste,
la sous-BOM et la galerie. Ne pas modifier seulement `EcartPCB` ou la
poseZ dans l'interface : ces valeurs ne pilotent pas toute la quincaillerie.
Pour une autre géométrie, reprendre la recette et vérifier toute la chaîne
d'appui. Les éditions manuelles de ces candidats sont remplacées à la
régénération ; les reporter dans la recette auparavant.

La description d'architecture et la BOM sont consolidées dans
[DOC-MEC](../../../docs/architecture/ARCHITECTURE_MECANIQUE.md) ; l'énergie et
les réseaux dans [DOC-ELEC](../../../docs/architecture/ARCHITECTURE_ELECTRIQUE_RESEAUX.md).
Ce fichier reste le guide local d'ouverture et de maintenance des assemblages.

Configuration de travail : `SA02A_Dock20Ah`, cassette 6S 20 Ah, châssis
`SA01_Chassis_Rehausse20`, avionique `SA03_Avionique_Rehausse20` et capteurs
`SA05_Capteurs_Isoles`. Les anciens assemblages restent des archives de conception.
Les limites de vérification sont décrites dans DOC-MEC, DOC-ELEC et DOC-VAL.

Référence de travail CAO : ouvrir `assemblages/Systeme_Cartographie_20Ah.FCStd`
pour le drone et la station au sol, ou `assemblages/Drone_Cartographe_20Ah.FCStd`
pour le drone seul. Conserver toute l'arborescence de fichiers liés.

Chaque sous-système est un document séparé utilisant `App::Link`. Les pièces fabriquées conservent leurs arbres CSG et expressions. Les feuilles de paramètres copiées sont propres à chaque référence : elles ne pilotent pas globalement toutes les cotes.

Les repères des pièces conservent ceux de l'intégration initiale et ne sont pas systématiquement centrés. Les liens répétés portent les décalages. Le châssis X650 reste un ensemble acheté avec son arbre fabricant. Les enveloppes provisoires restent **À valider**.

`manifest.json` décrit les références et occurrences. Sources et exports initiaux sont copiés ici. Les anciens documents dans `results/freecad/cartographe_v0_1/` restent une archive. Régénérer les exports après modification.

Les [sources, dimensions et réserves](../../cad/cartographe_v0_1/README.md) restent applicables : deux contacts aux entretoises Jetson, fixations PX4/antenne et qualification physique **À valider**.

Traçabilité : `MEC-ARC-001` → manifeste des pièces et assemblages →
`verification/hierarchie.json`. Les contrôles historiques copiés concernent la
géométrie initiale ; aucun essai physique n'est impliqué.

Les exports historiques sont dans `exports/iteration_20260915/` (P16) et
`exports/iteration_20260916/` (P06, P20–P22). Pour examiner la pile seule,
ouvrir `sous_assemblages/SA03_Avionique.FCStd`. Conserver toute l'arborescence
avec les pièces liées. Les fichiers de `verification/sauvegardes_20260915/`
servent à retrouver l'état précédent ; ne pas les ouvrir comme configuration active.

Pour examiner le préplacement CA01 sous la baseboard Holybro, ouvrir
`sous_assemblages/SA03_CA01_Holybro_candidat.FCStd`. Conserver les deux
fichiers liés `pieces/commerce/EQ_Holybro_Pixhawk_Jetson_Baseboard_candidat.FCStd`
et `pieces/fabriquees/CA01_PCB_Preplacement.FCStd`. L'écart candidat entre
PCB est éditable dans `ParametresStack.EcartPCB` ; contrôler les liens après
réouverture. La variante n'est pas insérée dans le drone actif.

Les modèles courants sont décrits par
`../../electronique/cartographe/carte_avionique/modeles_3d.json`.
Les nouveaux natifs sont `pieces/commerce/CA01_Modele_*.FCStd`,
les exports courants dans `exports/ca01_modeles3d_20261001/`.
Conserver les copies originales sous `sources_fabricants/` et l'arborescence.
Les anciennes `Enveloppe_CA01_*.FCStd` servent d'historique, sauf RP4TD.

Pour régénérer les modèles nominaux, exécuter avec le Python FreeCAD les
recettes `verification/build_ca01_ti_models.py`,
`build_ca01_component_models.py` et `build_ca01_connector_models.py`.
Après export KiCad avec origine `50x50mm` et sans DNP, utiliser
`verification/update_ca01_models_native.py`, puis dans un nouveau processus
`verification/verify_ca01_models_native.py`. Actualiser les hashes du mapping
après toute régénération. Les positions et sources de modèle sont dans
`verification/positions_modeles_ca01_20261001.json`.
Voir DOC-MEC §4.4.1 et DOC-VAL §12.7.9. Les binaires lourds restent hors Git.

Le préplacement courant représente MOD401 RP4TD en montage direct sur CA01,
avec J401/W11 supprimés. Ouvrir la variante candidate avec ses fichiers liés.
Le corps radio est nominal et sa pose Z illustrative. Le PCB comporte quatre
trous candidats Ø0,8 mm, aux axes estimés sur la photo TOP. Les broches réelles,
leur hauteur, le profil sous-face et le jeu module/PCB restent à mesurer.
Cette géométrie ne démontre pas le brasage possible. Les308solides composants courants correspondent
au STEP courant ; la révision filaire est conservée dans l’historique de
`verification/revue_stack_ca01_20261001.json`.

Pour examiner la reprise de batterie 6S, ouvrir
`sous_assemblages/SA02_BerceauFixe_Candidat.FCStd` (enveloppe 16 Ah) ou
`SA02_BerceauFixe_Candidat_20Ah.FCStd` (enveloppe 20 Ah avec cale).
Ces variantes restent séparées du drone actif. Dans la feuille `Parametres`
de chaque sous-assemblage, modifier `AngleOuvertureCandidat` (cellule B50)
entre 0 et 110° puis recalculer pour examiner le capot. La position sauvegardée
est fermée à 0° ; l'angle est une valeur d'étude, pas une butée physique qualifiée.
Conserver tous les fichiers liés P23–P26 et `EQ_*_Candidat` de cette variante.
Les vues fermé/ouvert sont `verification/berceau_fixe_16Ah_candidat_20261002.png`
et `berceau_fixe_20Ah_candidat_20261002.png`.

La recette `verification/build_berceau_fixe_candidat.py` régénère uniquement
les nouveaux natifs et les exports `exports/berceau_fixe_candidat_20261002/`.
Elle remplace les éditions manuelles de ces candidats : les reporter dans
la recette avant une régénération. Lancer avec le Python de FreeCAD 1.1,
puis `verify_berceau_fixe_integration.py` pour chaque assemblage,
`render_berceau_fixe_candidat.py` et `verify_berceau_fixe_manifest.py`.
Le contrôle d'intégration sans argument remplace la preuve par la variante
16 Ah ; ajouter ensuite la 20 Ah avec
`--candidate sous_assemblages/SA02_BerceauFixe_Candidat_20Ah.FCStd --variant 20Ah --append`.
La preuve du manifeste compare aussi les empreintes de la configuration active.
Voir DOC-MEC §4.1.1 et DOC-VAL §12.1.1 pour le périmètre des contrôles.

Pour examiner le dock complet, ouvrir `sous_assemblages/SA02A_Dock20Ah.FCStd`.
La feuille `Parametres`, cellule B60 alias `ExtractionX`, commande la
translation de toute la partie mobile vers `+X`, de0à300mm. L'état sauvegardé
est fermé à0mm. Aucun cliquet interne ni remise sous tension n'est animé.
`SA02_Cassette20Ah_Coulissante` et `SA02_Contacts20Ah` sont les montages de
construction séparés ; le dock complet reprend leurs fixations substituées.
Ne pas les ajouter en plus de `SA02A_Dock20Ah` dans le drone final.

Pour régénérer, utiliser le Python de FreeCAD1.1 sur les recettes dans
`verification/`, dans cet ordre : `build_latching20Ah_20261002.py`,
`build_rehausse20_avionique_20261002.py`, `build_cassette20Ah_20261002.py`,
`build_support_jeti20Ah_20261002.py`, `build_contacts20Ah_20261002.py`,
`build_conducteurs20Ah_20261002.py`, `build_accessoires20Ah_20261003.py`,
`build_dock20Ah_20261003.py`, puis
`build_assemblage20Ah_20261002.py`. Les recettes remplacent les éditions
manuelles de ces nouvelles références ; y reporter toute modification.
Les sources commerciales originales restent inchangées.

Dans un nouveau processus, lancer `verify_rehausse20_avionique_20261002.py`
puis `verify_integration20Ah_20261002.py`. Après la dernière régénération,
exécuter `sync_faisceau20Ah_20261003.py`, `build_bom_dock20Ah_20261002.py`,
`update_manifest_dock20Ah_20261002.py` et `render_dock20Ah_20261002.py`.
Contrôler ensuite `verify_bom_dock20Ah_20261003.py`,
`verify_manifest_dock20Ah_20261003.py` et `verify_preservation_dock20Ah_20261002.py`.
Les vues sont `verification/dock20Ah_20261002.png` et
`verification/drone20Ah_20261002.png`. La BOM technique est
`verification/bom_dock20Ah_20261002.json` ; les commandes de regeneration
du classeur Excel sont portées par `verification/export_bom_dock20Ah_20261002.mjs`.
Cette recette utilise le runtime Node et `@oai/artifact-tool` ; le classeur
est produit sous `outputs/dock20Ah_20261002/`. Sa relecture se fait avec
`verify_classeur_bom20Ah_20261003.py`, Python et openpyxl en lecture seule.
Les STEP des nouvelles références sont sous `exports/cassette20Ah_20261002/`
et `exports/rehausse20_candidat_20261002/`.

Pour examiner la configuration système candidate, ouvrir
`assemblages/Drone_Cartographe_Systeme_Candidat.FCStd` en conservant son
arborescence de fichiers liés. `SA08_Faisceau_Systeme_Candidat` contient les
35 réservations de cordons ; sélectionner un cordon puis son chemin et son
balayage dans le fichier de référence pour inspecter sa géométrie.
L'assemblage actif reste `Drone_Cartographe_20Ah.FCStd`.

La BOM cible est `configuration_cible_20261003.json`. Pour modifier les routes,
éditer `verification/routes_systeme_candidat_20261003.json` : points en mm dans
le repère global, diamètre d'enveloppe et rayon de réservation. Les longueurs
mesurées ne sont pas des longueurs de coupe. Les éditions manuelles des natifs
candidats sont remplacées par leur recette ; les reporter avant régénération.

Avec le Python de FreeCAD 1.1, lancer dans cet ordre :
`verification/build_systeme_faisceau_candidat_20261003.py`, puis dans un nouveau
processus `verification/verify_systeme_faisceau_candidat_20261003.py`,
`verification/render_systeme_faisceau_candidat_20261003.py` et
`verification/update_manifest_systeme_candidat_20261003.py`.
Le rendu est `verification/systeme_faisceau_candidat_20261003.png`.
Les limites d'intégration et les résultats sont dans DOC-MEC §4.5 et
DOC-VAL §12.1.4 ; la variante ne constitue pas un faisceau de fabrication.
`verification/archive_systeme_initial_20261003/` conserve les entrées et preuves
de l'itération initiale ; son script archivé doit être remis à son emplacement
d'origine pour une reproduction isolée avec les natifs correspondants.

Pour consulter les visuels de tous les sous-assemblages, ouvrir
`exports/rendus_freecad_sous_assemblages_20261003/index.html` dans un navigateur.
Chaque sous-assemblage possède une capture isométrique et une capture de
dessous, produites directement par la vue 3D de FreeCAD. Les deux planches séparent les
modèles courants/candidats des versions historiques et alternatives ; les
états sont indiqués sur les images. Les montages de construction du dock et
des capteurs sont aussi présentés, sans les ajouter au drone assemblé.
Régénérer les captures en exécutant dans FreeCAD la macro
`verification/rendus_sous_assemblages_freecad_20261003.FCMacro`, avec la
sélection `verification/visuels_sous_assemblages_20261003.json`. Utiliser une
session séparée : la macro affiche les objets en mémoire, exporte les vues,
puis ferme cette session sans sauvegarder les natifs. Les anciens liens OEM
non résolus sont retrouvés par leur nom exact dans les sauvegardes locales,
uniquement pour l'affichage ; les restaurations sont consignées dans la preuve.
La preuve d'export et de préservation est
`verification/rendus_sous_assemblages_freecad_20261003.json`. Générer ensuite
les planches, la galerie et l'archive ZIP avec le Python de FreeCAD sur
`verification/galerie_rendus_freecad_20261003.py` ; il ne s'agit pas d'un
contrôle de montage ou de passage des câbles.
