# Recette de validation XLink V2.1

Cette recette contrôle les preuves numériques de `CAB-CARTO-001`,
`MEC-ARC-001`, `MEC-INT-001`, `G3A-01` et `G3A-08`. Le résultat,
la maturité et les conditions de reprise sont dans
[DOC-VAL](../VALIDATION_QUALIFICATION.md#preuve-xlink-v21).

## Prototype cartographe actif

Exécuter depuis la racine sur Windows AMD64 avec Qt 6, un compilateur C++17,
FreeCAD 1.1.3 et Cables Workbench 0.3.7. La
[configuration](../../validation_engine/fixtures/xlink_cartographe.json)
désigne le prototype actif sans dock. Le graphe L2 est calculé avant toute
mesure native. Utiliser des FCStd de confiance, car FreeCAD charge leurs proxies.

```powershell
$build = '.runtime/v21-xlink-build'
$work = '.runtime/v21-xlink-rejeu'
$freecad = 'C:/Program Files/FreeCAD 1.1/bin/python.exe'
$env:Path = 'C:/msys64/ucrt64/bin;' + $env:Path
$env:ELECTROMECHANICAL_FREECAD_PYTHON = $freecad
cmake -S validation_engine -B $build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH=C:/msys64/ucrt64
cmake --build $build --parallel 4
ctest --test-dir $build --output-on-failure
New-Item -ItemType Directory -Force $work | Out-Null
& "$build/interconnection/interconnection_core.exe" inspect-cartographe --root . --output "$work/electrical.json"
& "$build/validation_core.exe" xlink --configuration validation_engine/fixtures/xlink_cartographe.json `
  --freecad-python $freecad --electrical "$work/electrical.json" --output "$work/validation"
```

Le dossier `copy` contient la fermeture privée. Sélectionner le
`run-…/campaign.json` affiché par la CLI. `inventory.result.json` détaille
les chemins natifs, documents, empreintes, noms internes, labels et matrices
par occurrence. Un nom de document et d’objet ambigu nécessite un chemin
d’occurrence explicite. Le rapprochement conserve le sens du chemin électrique,
les catégories hors faisceau et les liens inverses. Une pose d’équipement
résolue laisse les contacts et leurs repères à instruire.

Un autre témoin peut fournir `equipment_mapping` dans sa configuration.
Ce JSON indexe `equipment` et `contacts` par côté du graphe L2. Un
sélecteur porte `object` au format `document.FCStd#Name` et, si nécessaire,
`occurrence` avec le chemin complet. Un contact ajoute `id` et `port`.
L’identifiant et le port doivent correspondre aux propriétés natives et à
la chaîne d’attachement du terminal. Les critères de rayon, de pose des
extrémités et de tangente sont associés aux câbles par chemin d’occurrence
dans `criteria.route_criteria`. Les tolérances et repères sont ceux du
référentiel du témoin.

La sauvegarde est limitée à la racine de copie. Le processus suivant ouvre
la fermeture sauvegardée, recalcule et contrôle les documents et occurrences.
Les processus de mesure relisent cette même fermeture. Le rapport donne le
nombre de paires entre câbles et solides visibles, le nombre éliminé par les
boîtes englobantes et la couverture BRep. Les volumes positifs relevés avec une
tolérance de criblage à zéro sont des constats numériques à examiner avec les
relations fonctionnelles et la provenance des solides.

`--native-timeout-ms` borne l’ouverture et la sauvegarde.
`--batch-timeout-ms` et `--max-native-tasks` bornent un lot. Relancer la même
commande et le même dossier pour reprendre après interruption. Le cache
associe chaque mesure au contenu de la racine, de toutes les dépendances et
des entrées de calcul. Les entrées modifiées exigent un nouveau dossier de
copie. Les résultats détaillés et les journaux restent sous `.runtime/`.
Les codes 0, 2 et 3 désignent respectivement `V21_XLINK_PASS`,
`V21_XLINK_BLOCKED` et `V21_XLINK_CONDITIONAL`. Le code 1 signale un
arrêt d’exécution. Consulter le manifeste T0 pour vérifier la finalisation.

La copie Action 3 est identifiée séparément dans le manifeste L0.
Elle compte 138 natifs et possède ses propres sources et résultats.
Le rapport du prototype actif se rapporte à sa fermeture de 137 natifs.

## Banc L4 XLink

Le [référentiel XLink](../../validation_engine/fixtures/xlink_l5/reference.json)
exerce les méthodes historiques L4 sur un banc de deux FCStd et déclare
l’obstacle lié dans l’inventaire des paires ainsi que des retraits. Le
[protocole L4](../../validation_engine/README.md) décrit `seal` et
`validate`. Geler la recette XLink puis passer la racine du témoin à
`--candidate` et la projection électrique du même banc à `--electrical`.
Rejouer le témoin historique et le banc reconstruit dans des dossiers de
sortie distincts. Le contrôle exige que les câbles du banc soient régénérés
dans le processus de validation après réouverture.
Le test `test_frozen_xlink_obstacle_enlarges_pair_scope_on_both_reopens`
reconstruit le banc et exerce le déplacement de la géométrie liée avec
l’empreinte de la racine conservée.

La [preuve structurée](../verification/v21_xlink_coverage.json) identifie
les entrées mesurées, les résultats des bancs et les causes des contrôles
encore ouverts sur le prototype.
