# Utiliser le projet KiCad CA01

Le répertoire `.history/` contient l'historique automatique local de KiCad.
Il est ignoré par Git et ne constitue pas un sous-module à récupérer au clonage.

Le schéma complet exporté est disponible dans [CA01_Avionique.pdf](CA01_Avionique.pdf)
(six pages, à côté du projet KiCad). La copie dans `verification/CA01_schema_preliminaire.pdf`
est identique ; la provenance actuelle de l'export est dans
`verification/export_pdf_variante_lm76003_20261001.json`. Les preuves
`export_pdf_empreintes_20261001.json` et `export_pdf_20261001.json`
restent celles des étapes antérieures.

Ouvrir `CA01_Avionique.kicad_pro` avec KiCad 10.0.6. La feuille racine
donne accès aux cinq sous-feuilles : entrée et protections 6S, rails 12 V,
5 V local, radio et synchronisation. Conserver `CA01_Fonctions.kicad_sym`,
`CA01_Design.kicad_sym`, `CA01_Radio.kicad_sym` et `sym-lib-table` à côté du projet. Pour les éditions, appliquer
[la skill HW Design schématique](../../../../.agents/skills/hw-design-schematique/SKILL.md) : regrouper les
circuits et utiliser des fils directs pour leurs connexions locales.
Les labels servent aux rails et aux interfaces identifiables.
Placer autant que possible les entrées à gauche et les sorties à droite ;
agrandir les symboles d'IC lorsque les broches ou leurs textes sont trop serrés.
Utiliser le symbole `CA01_Fonctions:Alimentation_Barre` orienté vers le haut
pour les rails et `power:GND` pour les masses ; les labels identifient les signaux.

Le [PCB CA01](CA01_Avionique.kicad_pcb) contient le routage complet
quatre couches, avec plans GND/batterie protégée et vias thermiques. Les
choix de cuivre sont dans `routage.json` ; les coordonnées sont dans
`placement_mecanique.json` ; les
choix et correspondances des connecteurs dans `empreintes_connecteurs.json`,
les autres affectations dans `empreintes_composants.json`. Conserver
`CA01_Mecanique.pretty/` et `fp-lib-table` à côté du projet. Les aperçus courants sont dans
[verification/routage_complet_apercus/](verification/routage_complet_apercus/).
L’ancien aperçu de placement sans cuivre reste historique.
MOD401 utilise le symbole `CA01_Radio:RadioMaster_RP4TD` et l’empreinte
`CA01_Mecanique:RadioMaster_RP4TD_Broches_THT_Candidat`, avec quatre pads THT.
Leurs centres sont estimés sur la photo RadioMaster TOP : X11,85mm,
Y±3,9/±1,3mm, pas2,6mm. Trous0,8mm et pads1,6mm correspondent à une
broche ronde0,5mm candidate, sans référence sélectionnée ni hauteur définie.
Ces valeurs sont **À valider sur le module reçu avant fabrication**.
La provenance et la transformation sont dans `empreinte_rp4td.json`.
J401/W11 restent retirés. Conserver le modèle de corps `RP4TD.step` dans
`hardware/mecanique/cartographe/exports/ca01_placement_20261001/` : ce module
reste une enveloppe, faute de modèle détaillé fiable pour la variante standard.
Les autres modèles sont référencés dans `modeles_3d.json`. Conserver les
arborescences `sources_fabricants/` et `exports/ca01_modeles3d_20261001/` du
répertoire mécanique. Les modèles issus de bibliothèques, d'auteurs ou de plans
restent nominaux et **À valider** avec les composants reçus.

Pour éditer, ouvrir le PCB courant dans KiCad et remplir les zones après
modification. Vérifier depuis ce répertoire :

```powershell
./verification/verify_ca01.ps1
& 'C:/Program Files/KiCad/10.0/bin/kicad-cli.exe' pcb drc --refill-zones --save-board --format json --all-track-errors --schematic-parity --severity-all -o verification/drc_routage_complet_20261002.json CA01_Avionique.kicad_pcb
./verification/verify_all_drc_checks.ps1
& 'C:/Program Files/KiCad/10.0/bin/python.exe' verification/verify_completed_routing_review.py
& 'C:/Program Files/KiCad/10.0/bin/python.exe' verification/verify_completed_routing.py
```

Le contrôle principal et la revue lisent les sources et consignent leurs SHA.
La revue Kelvin désactive les jumpers R116 et coupe la jonction terminale
uniquement en mémoire ; les contrôles de force retirent les pistes fines
uniquement en mémoire. Ils ne sauvegardent pas le PCB. L'audit DRC réactive
les catégories ignorées dans une copie isolée, sans changer les préférences
du projet courant. Consulter les JSON de preuve pour le périmètre exact.

Après vérification, régénérer les fichiers candidats avec
`./verification/export_fabrication_candidate.ps1`, puis consulter
[fabrication/README.md](fabrication/README.md) et
[fabrication/export_manifest.json](fabrication/export_manifest.json).
Le [plan de validation](validation_electrique_thermique_cem.json) contient
les protocoles à préparer au banc ; les exports restent provisoires.

`start_routing.py`, `verify_routing.py`, `verify_routing_reproduction.py`
et les preuves01/10 concernent le démarrage historique. Leur configuration
initiale est archivée dans `verification/routage_initial_configuration_20261001.json` ;
elles ne vérifient pas le routage complet ni les nouvelles positions.
`build_placement.py` et `start_routing.py` refusent un PCB déjà routé :
ne pas employer les anciennes procédures pour reconstruire le PCB courant.
Après une édition, synchroniser `placement_mecanique.json`, `routage.json`
et les preuves de la cible réellement vérifiée. Garder les sources sous Git.

Les variantes U201/U301 conservent15trous Ø0,3/padsØ0,5 par composant ;
procédé de brasage et tolérances à valider. R116 représente les connexions
internes I/E par des pads dupliqués jumpers ; conserver cette propriété lors
d'une mise à jour depuis le schéma. Elle ne remplace pas la séparation PCB
des chemins de force et de mesure.

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
Reproduire séparément l'enveloppe thermique du shunt avec
`python verification/verify_shunt_thermique.py` ; le résultat est dans
`verification/shunt_thermique_20261001.json`. La cible acceptée est
10 mΩ ±0,1 % et ≤25 ppm/K ; R116 est un CSM3637 Y14880R01000B9R
±0,1 % /15 ppm/K /3 W. Son empreinte a quatre pads sur deux réseaux
logiques ; séparer les chemins de force et de mesure jusqu'aux bornes.
Le plan thermique de `dimensionnement.json` et `routage.json` décrivent
les cuivres/vias candidats présents dans le PCB. Les chemins Kelvin sont
présents et exclus localement du remplissage. La carte courante n’a aucune
connexion restante ; ce résultat ne qualifie pas la thermique ou la CEM.
Les recettes `verify_sync_preservation.py`, `verify_radio_layout.py` et
`verify_power_layout.py` reproduisent des étapes antérieures ; leurs références
de netlist précèdent le changement J401→MOD401 et les dernières sélections.
Elles ne constituent pas les contrôles de la cible actuelle. Utiliser
`verify_ca01.ps1`, `verify_completed_routing.py` et les preuves de DOC-VAL§12.7.13.
Les voies GNSS sont
désormais des circuits physiques candidats ; consulter
[DOC-ELEC §4.2.6](../../../../docs/architecture/ARCHITECTURE_ELECTRIQUE_RESEAUX.md)
et la recette [DOC-VAL §12.7.2](../../../../docs/VALIDATION_QUALIFICATION.md).
R530–R533 demeurent DNP et `manufacturing_ready=false`.
J509 exige la référence3,3 V Camera0 ou1 pin22/pin1GND, dont la relation
avec les domainesGPIO/UART Orin reste à vérifier ; ne pas employer le +5 V
des portsGPIO/Debug. J301 reste une réserve sans charge affectée et
partage le budget 5 V de 3 A.

Les modèles3D courants sont affectés par `modeles_3d.json` : copies locales
KiCad et exports détaillés sous `hardware/mecanique/cartographe/`.
Le PCB courant conserve ce mapping ; les preuves de placement antérieures
contrôlent ses chemins et SHA, et `verify_completed_routing.py` contrôle leurs associations.
Les exports FreeCAD/STEP du01/10 représentent les positions précédentes
des48composants déplacés ; les actualiser avant validation de SA03.
RP4TD reste une enveloppe nominale.
Après régénération d'un modèle, actualiser ses SHA dans le mapping et
réexporter le STEP puis synchroniser le natif (README mécanique).
