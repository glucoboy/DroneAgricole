# Copie FreeCAD des faisceaux modulaires

Ouvrir [Prototype_Cartographe.FCStd](assemblages/Prototype_Cartographe.FCStd)
avec FreeCAD 1.1.3 et Cables Workbench 0.3.7. Conserver les répertoires
`assemblages`, `sous_assemblages`, `pieces` et `verification/candidats`
dans la même arborescence pour les liens natifs. Dans SA07, chaque module
est un groupe distinct et les retenues ont leur propre groupe. Éditer un
trajet dans le document du câble lié. Le profil et le chemin sont des
objets de construction masqués par défaut.

| Pour consulter | Fichier |
|---|---|
| Châssis, faisceaux, retenues ou montage | [Vues séparées et index](verification/vues/index_vues.json) |
| Connexions, nomenclature et ordre de montage | [Registre des modules](verification/modules_electriques.json) |
| Gaines et pièces de retenue | [Définition des pièces et interfaces](verification/integration.json) |
| Supports P70, retenue du départ F41 et variante F06 | [Définition de reprise](verification/integration_radio.json) |
| Contrôles et limites | [Validation](verification/validation.json) |
| Décisions et contexte | [DOC-MEC](../../../docs/architecture/ARCHITECTURE_MECANIQUE.md#faisceaux-modulaires) et [DOC-VAL](../../../docs/VALIDATION_QUALIFICATION.md#validation-faisceaux-modulaires) |

## Vérifier la copie sauvegardée

Depuis la racine du dépôt, exécuter le contrôle ciblé avec le Python de
FreeCAD. La commande ouvre les BRep en lecture et écrit le nouveau rapport
hors des fichiers de preuve livrés.

```powershell
$copie = 'hardware/mecanique/cartographe_faisceaux_modulaires'
$verif = "$copie/verification"
$freecadPython = 'C:/Program Files/FreeCAD 1.1/bin/python.exe'
$sortie = '.runtime/controle-copie-modulaire'
New-Item -ItemType Directory -Force $sortie | Out-Null
& $freecadPython -X utf8 -B "$verif/valider_modules.py" $copie "$sortie/retenues.json" --metadata "$sortie/roles.json"
```

Pour régénérer, créer une nouvelle copie de
`hardware/mecanique/cartographe_faisceaux_refonte` avec `workspace_guard.py stage`.
Ajouter explicitement `manifest.json`, `nomenclature_prototype.json` et les
fichiers `construction_prototype.json`, `routes_prototype.json`,
`cable_workbench_prototype.py` et `read_brep_prototype.py` de `verification`.
Passer la nouvelle racine à `essayer_routes.py` avec l'option
`--integrated verification/integration.json` du dossier de livraison, puis
à `assembler_modules.py` avec `--modules` vers le registre électrique et
`--trials` vers le résultat de l'essai intégré. La recette exige une copie
vierge et vérifie les empreintes de la source.

Pour reproduire la reprise P70, F41 et F06, isoler une copie de cette
première génération. Ajouter à la fermeture native les registres
`manifest.json`, `construction_prototype.json`, `routes_prototype.json`,
`generation.json` et `roles_controle.json` selon leurs chemins existants.
Exécuter `installer_radio.py` sur cette copie avec `integration_radio.json`,
`essais_blocage_rf.json` et `--route-trials variantes_haut.json`, tous fournis
sous `verification`. Les champs `baseline_*` du registre électrique
documentent le candidat initial. Les longueurs des axes de la copie se
lisent dans `routes_prototype.json` ou dans la preuve de validation.
