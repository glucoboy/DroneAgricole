# Recette de vérification V3‑A.3

Le verdict et la prochaine décision figurent dans [DOC-VAL](../../../VALIDATION_QUALIFICATION.md#cartographe-v3-a3). Le point de départ est le commit d’intégration `9c72169d6148b12862026031aa3d55e43bd37b3c`. [Manifestes et entrées](source_manifest.json) · [Résultats des commandes](regressions.json) · [Matrice par occurrence](operation_admission.json)

## Préparer les entrées

Utiliser l’environnement Windows amd64 de V3‑I et un nouveau dossier privé. Reprendre du [reçu natif A](../a/native_receipt.json) la fermeture complète de la référence, et du [manifeste GO3B](../../v21_go3b_manifest.json) celles de H03-A, H03-B et de la consolidée. Copier les fichiers avec leurs chemins relatifs, vérifier leurs SHA-256 et garder leurs sources immuables. Conserver le graphe scellé d’A sous `.runtime/v3-a/sealed/cartographe-graph.json` pour le témoin L5.

La première ouverture A.3 depuis le checkout neuf s’est arrêtée sur trois auxiliaires JSON au format de fins de ligne différent. Pour le rejeu, une réplique de travail privée a repris les octets scellés de la référence et les fermetures des témoins, sans normaliser la source Git ni les reçus. Y copier les scripts, les imports et leurs autorités depuis le checkout. Les emplacements sources et les écarts d’octets sont dans le [manifeste](source_manifest.json).

## Rejouer les mesures

Depuis la racine de la réplique privée, réutiliser la recette A.2. Le worker de mesure ouvre des copies en lecture seule. Lancer le criblage historique sur une seconde copie privée, rendre ses entrées en lecture seule et conserver son reçu. Le criblage des routes reconstruit une géométrie temporaire en mémoire. [V3-A.2](../a2/REPORT.md)

```powershell
$freecad = 'C:/Program Files/FreeCAD 1.1/bin/python.exe'
$env:PYTHONPATH = (Get-Location).Path
$env:QT_QPA_PLATFORM = 'offscreen'
python -B -m electromechanical_engine.v3_a2_native --freecad-python $freecad --work .runtime/rejeu-a3
python -B .agents/skills/electromechanical-integration/scripts/workspace_guard.py stage --root hardware/mecanique/cartographe --entry assemblages/Prototype_Cartographe.FCStd --extra verification/construction_prototype.json --extra verification/routes_prototype.json --target .runtime/criblage-a3
$receipt = Get-Content -Raw -Encoding UTF8 .runtime/criblage-a3/experiment.json | ConvertFrom-Json -AsHashtable
foreach ($file in $receipt.inputs_sha256.Keys) {
    (Get-Item -LiteralPath (Join-Path '.runtime/criblage-a3' $file)).IsReadOnly = $true
}
& $freecad -B hardware/mecanique/cartographe/verification/go3b/interfaces_screen.py .runtime/criblage-a3 .runtime/criblage-a3.json --routes
```

Comparer les mesures avec la tolérance numérique absolue de `1e-6` de la recette A.2, par occurrence et type de grandeur. Les contrôles de transformation ont leur propre tolérance de `1e-7`. Les gabarits TTL/USB restent des hypothèses de criblage. Les surfaces et perçages des natifs ne constituent pas une réception d’ancrage. [Observations](native_observations.json)

## Rejouer les gardes

Depuis le checkout A.3, passer la racine de la référence scellée copiée et le binaire intégré V3‑I. Le témoin de lecture doit sortir avec `READ_ONLY_IMPACT`. Les occurrences et les dossiers directs ou forgés doivent produire des refus sans transaction. Contrôler séparément l’intégration A.1/B.1 avec les bancs et conditions de V3‑I. [Détails L5](../../../../convergence_manager/README.md#autorites-cartographe-v3-a3)

```powershell
python -B convergence_manager/tests/test_v3_a3_authorities.py --core <convergence_core.exe-V3-I> --source <replique>/hardware/mecanique/cartographe --out .runtime/v3-a3/scope
```

Les JSON synthétiques et les formulaires sont publiables dans Git. Les copies FreeCAD, les archives GO3B et les rapports bruts sont inventoriés par chemin et SHA sous le répertoire privé. Les notices lourdes déjà mises en cache restent désignées par leur chemin, URL et empreinte. Les relevés à transmettre à l’opérateur se trouvent dans [la fiche de collecte](measurements_required.md).
