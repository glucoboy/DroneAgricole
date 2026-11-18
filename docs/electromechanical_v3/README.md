# Rejouer le référentiel XLink V3-A

Exécuter les commandes à la racine du dépôt. Le
[reçu natif](../verification/v3/a/native_receipt.json) donne les entrées
exactes, leurs empreintes, les versions FreeCAD et les commandes du banc.
Les copies et les résultats volumineux sont conservés sous `.runtime/v3-a`.
Le [gel](../verification/v3/a/freeze.json) donne les chemins de la campagne
exécutée. Utiliser un répertoire de sortie indépendant à chaque rejeu.

```powershell
$freecad = 'C:/Program Files/FreeCAD 1.1/bin/python.exe'
$run = ".runtime/v3-a/replay-$([Guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Path $run | Out-Null
$source = 'hardware/mecanique/cartographe'
python -B -m electromechanical_engine.v3_native --freecad-python $freecad --source $source --entry assemblages/Prototype_Cartographe.FCStd --work "$run/native" --output "$run/native.json" --extra manifest.json --extra nomenclature_prototype.json --extra verification/construction_prototype.json --extra verification/refonte_faisceaux/inventaire.json --extra verification/routes_prototype.json
& $freecad -B -m validation_engine.tests.test_xlink_native --worker create "$run/bench-source"
python -B -m electromechanical_engine.v3_native --freecad-python $freecad --source "$run/bench-source" --entry assemblies/Root.FCStd --work "$run/bench" --output "$run/bench.json"
cmake -S electromechanical_graph -B "$run/build" -G Ninja -DCMAKE_BUILD_TYPE=Release -DQt6_DIR=C:/msys64/ucrt64/lib/cmake/Qt6
cmake --build "$run/build" --parallel 4
ctest --test-dir "$run/build" -R 'v3_graph_contract|^l2_interconnection$' --output-on-failure
cmake -S simulation -B "$run/t0" -G Ninja -DCMAKE_BUILD_TYPE=Release -DQt6_DIR=C:/msys64/ucrt64/lib/cmake/Qt6
cmake --build "$run/t0" --target cartographe-evidence --parallel 4
```

Avec le validateur T0 `cartographe-evidence.exe` compilé depuis
`simulation`, exécuter le contrôle d’acceptation et les oracles.

```powershell
$core = "$run/build/electromechanical_graph_core.exe"
$validator = "$run/t0/cartographe-evidence.exe"
python -B electromechanical_graph/tests/verify_reference.py --core $core --native "$run/native.json" --transfer-report "$run/native/transfer.json" --bench-native "$run/bench.json" --t0-validator $validator --out "$run/qualified"
$graph = "$run/qualified/cartographe-graph.json"
$sha = (Get-FileHash -Algorithm SHA256 $graph).Hash.ToLowerInvariant()
& $core impact $graph MOVE iso --root . --graph-sha256 $sha --output "$run/impact-iso.json"
```

Pour rouvrir le modèle transféré, lancer FreeCAD sur le fichier
`transfer/cad/assemblages/Prototype_Cartographe.FCStd` de la copie
indiquée dans le reçu. Conserver la hiérarchie relative complète et comparer
les empreintes de la copie au reçu avant ouverture. Les rapports natifs de
`staged` et `transfer` portent les dépendances chargées, les définitions,
les occurrences et les contrôles de transformation.

## Contrat et migration

Le [schéma](graph.schema.json) décrit `v3.graph/1`. L’API C++ vérifie aussi
les références croisées, l’ordre et le sens des parcours, les
empreintes et les contraintes d’autorité. Le pont produit `v3.native/1`
depuis les placements FreeCAD et une composition indépendante de la
chaîne. Le JSON natif est épinglé par son empreinte à l’import.

`import --cartographe-l2` migre le rapprochement
`drone-agricole.l2.cartographe-interfaces.v1`, le modèle système version 1
et l’inventaire V2.1. Il conserve les parcours et motifs sans axe, ajoute
les occurrences vérifiées et applique les [autorités F40/F41](cartographe.json).
L’écart LF/CRLF du manifeste mécanique est contrôlé par reconstruction des
octets historiques et consigné avec les deux empreintes. Une modification
de contenu échoue au contrôle. Les points d’entrée L2 historiques
conservent la vérification exacte de leurs empreintes.

Les repères équipement, embase, accouplement, fiche et sortie fil sont
distincts. Les réservations d’axe restent des mesures CAO. Les mesures
avec origine et direction signées utilisent le repère cartésien de
l’assemblage, mm et degrés. `compare-frames` effectue le calcul relatif
sur les preuves fournies par l’appelant. Au rejeu de qualification,
`--graph-sha256` vient du reçu publié.

La CLI accepte uniquement les versions prises en charge et les nouvelles
destinations JSON. Les arêtes documentaires peuvent conserver une
dépendance prudente à revoir. Les requêtes d’impact rendent explicites
les contrôles et observations à reprendre. Les dépendances CAO complètes
restent consultables dans le rapport natif. La couverture d’impact
qualifiée porte sur les trois scénarios du
[reçu d’acceptation](../verification/v3/a/acceptance.json).
