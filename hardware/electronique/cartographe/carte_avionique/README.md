# Utiliser le projet KiCad CA01

Le schéma complet exporté est disponible dans [CA01_Avionique.pdf](CA01_Avionique.pdf)
(six pages, à côté du projet KiCad). La copie dans `verification/CA01_schema_preliminaire.pdf`
est identique ; la provenance de l'export est dans `verification/export_pdf_20261001.json`.

Ouvrir `CA01_Avionique.kicad_pro` avec KiCad 10.0.6. La feuille racine
donne accès aux cinq sous-feuilles : entrée et protections 6S, rails 12 V,
5 V local, radio et synchronisation. Conserver `CA01_Fonctions.kicad_sym`,
`CA01_Design.kicad_sym` et `sym-lib-table` à côté du projet. Pour les éditions, appliquer
[la skill HW Design schématique](../../../../.agents/skills/hw-design-schematique/SKILL.md) : regrouper les
circuits et utiliser des fils directs pour leurs connexions locales.
Les labels servent aux rails et aux interfaces identifiables.
Placer autant que possible les entrées à gauche et les sorties à droite ;
agrandir les symboles d'IC lorsque les broches ou leurs textes sont trop serrés.
Utiliser le symbole `CA01_Fonctions:Alimentation_Barre` orienté vers le haut
pour les rails et `power:GND` pour les masses ; les labels identifient les signaux.

Le schéma représente une migration **préliminaire** vers le câblage cible
V0.5. Il n'est pas raccordable ni fabricable : les valeurs de puissance,
les protections, les empreintes et les niveaux de certaines interfaces
restent à justifier. Lire `manifest.json` pour l'état exact de l'artefact
et `../../../../docs/architecture/ARCHITECTURE_ELECTRIQUE_RESEAUX.md`
pour les exigences.

Lancer le contrôle statique depuis ce répertoire :

```powershell
./verification/verify_ca01.ps1
```

La commande régénère la netlist, l'ERC et `verification/controle_statique.json`.
Un contrôle de connectivité réussi ne signifie pas que l'ERC est sans erreur,
que les composants sont dimensionnés ou que la carte est qualifiée. Examiner
les champs `erc`, `manufacturing_ready` et les points ouverts du manifeste.

Le câblage fonctionnel est dans `../cablage_global.json` et son schéma dans
`../cablage_global.mmd`. POWER1/POWER2, CAN1/2, TELEM2, Ethernet LiDAR
et USB3 caméra contournent CA01. Le +5 V du connecteur UART2 GNSS ne doit pas
être relié à CA01 ; le GNSS est alimenté par CAN2. Les sorties de
synchronisation R530–R533 restent DNP avant caractérisation des interfaces
et autorisation de leur montage sur banc.

La BOM candidate est dans [bom_candidate.json](bom_candidate.json), les
calculs dans [dimensionnement.json](dimensionnement.json) (`time_design`)
et les sources dans [manifest_sources.json](../sources_fabricants/manifest_sources.json).
Reproduire les 44 contrôles arithmétiques avec
`python verification/verify_dimensionnement.py`.
Contrôler aussi la conservation de netlist avec
`python verification/verify_sync_preservation.py` ; examiner les trois
contrôles dans `verification/conservation_sync_20260930.json`.
Pour la reprise graphique radio (page 3 du PDF), exécuter également
`python verification/verify_radio_layout.py` ; la netlist de référence
`verification/netlist_avant_reprise_radio_20260930.xml` sert à vérifier
la conservation électrique des six feuilles.
Pour la page 2 et les symboles d'alimentation, lancer
`python verification/verify_power_layout.py` après régénération de la netlist.
Les voies GNSS sont
désormais des circuits physiques candidats ; consulter
[DOC-ELEC §4.2.6](../../../../docs/architecture/ARCHITECTURE_ELECTRIQUE_RESEAUX.md)
et la recette [DOC-VAL §12.7.2](../../../../docs/VALIDATION_QUALIFICATION.md).
R530–R533 demeurent DNP et `manufacturing_ready=false`.
J509 exige la référence3,3 V Camera0 ou1 pin22/pin1GND, dont la relation
avec les domainesGPIO/UART Orin reste à vérifier ; ne pas employer le +5 V
des portsGPIO/Debug. J301 reste une réserve sans charge affectée et
partage le budget 5 V de 3 A.
