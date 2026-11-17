# Utilisation de la copie de faisceaux

Ouvrir [Prototype_Cartographe.FCStd](../../../cartographe_faisceaux_refonte/assemblages/Prototype_Cartographe.FCStd)
avec FreeCAD 1.1.3 et Cables Workbench 0.3.7. Déplacer la copie entière pour
conserver les liens. Dans l'arbre, ouvrir `SA07_Prototype_Faisceaux` pour
afficher les 21 groupes. Les occurrences de gaine indiquent leurs câbles et
guides associés. Les dérivations portent les points de changement de section.
Les volumes d'outillage et les fenêtres de contrôle restent masqués.

Les diamètres des câbles et les courbes natives restent éditables dans les
documents de référence. Les capsules sont construites avec des primitives
natives et une soustraction de la cavité. Les paramètres de rayon, de paroi
et de longueur sont liés au parcours ou au profil. Régénérer les capsules et
les ouvertures de guide après un changement d'entraxe, d'origine ou de direction.
Rejouer les contrôles de chemin, d'inclusion et de collision après édition.

Le [graphe physique](graphe_physique.json) contient les tronçons, les
dérivations et les offsets des câbles par rapport aux sections communes. Le
[registre de connectivité](inventaire.json) et son
[export tabulaire](inventaire_couverture.csv) associent les chemins aux
équipements, fonctions et statuts.

## Recette

Depuis la racine du projet, avec le Python embarqué de FreeCAD, copier la
fermeture XLink de `hardware/mecanique/cartographe_faisceaux_autonome` avec
`workspace_guard.py stage` vers une destination neuve. Pour les commandes
ci-dessous, utiliser `hardware/mecanique/cartographe_faisceaux_refonte` et
inclure `manifest.json`, `nomenclature_prototype.json`,
`verification/routes_prototype.json`, `verification/construction_prototype.json`,
`verification/cable_workbench_prototype.py` et
`verification/read_brep_prototype.py` comme extras. Si une copie existe déjà,
la conserver ailleurs dans le workspace avant de rejouer la construction.

```powershell
$python = 'C:/Program Files/FreeCAD 1.1/bin/python.exe'
$proof = 'hardware/mecanique/cartographe/verification/refonte_faisceaux'
& $python -B -X utf8 "$proof/adapter_freecad.py"
& $python -B -X utf8 "$proof/installer.py" NTC_Y35_44 MAIN_4_RELIEF_L8 SIGNAL_NORD_RELIEF_L30 F38_RELIEF_Xm40_65
& $python -B -X utf8 "$proof/controles_mobilite.py"
& $python -B -X utf8 "$proof/controles_mobilite_variantes.py"
& $python -B -X utf8 "$proof/inventaire_extract.py"
& $python -B -X utf8 "$proof/synthese.py"
```

Pour reproduire le [rapport géométrique](validation_geometrique.json), la
recette `controles_geometrie.py --help` décrit le contrôle intégral de la
référence, le delta et la réouverture avec cache vidé. Le rapport compare
les preuves `controles_geometrie_delta.json` et `controles_reouverture.json`
à `.runtime/refonte-controles/baseline-opt.json`. Exécuter ensuite
`controles_reprise_paires.py`, les deux recettes de revue et
`validation_geometrique.py`. Le graphe Mermaid est dans
[`graphe_physique.mmd`](graphe_physique.mmd) et les planches dans
[`controles_vues/`](controles_vues/).

Les statuts, mesures et choix de conception se lisent dans
[DOC-MEC](../../../../../docs/architecture/ARCHITECTURE_MECANIQUE.md#refonte-faisceaux-globale)
et [DOC-VAL](../../../../../docs/VALIDATION_QUALIFICATION.md#validation-refonte-faisceaux).
