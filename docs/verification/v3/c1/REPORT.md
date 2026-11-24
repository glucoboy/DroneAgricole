# Rejouer V3-C.1

[DOC-VAL](../../../VALIDATION_QUALIFICATION.md#cartographe-v3-c1) ·
[Verdict](acceptance.json) · [Commandes et temps](regressions.json) ·
[Inventaire des artefacts](artifacts.json)

Préparer Windows amd64 avec FreeCAD 1.1.3, Cables 0.3.7, MSYS2 UCRT64,
C++17, Qt 6 et Ninja. La campagne utilise les fichiers FCStd versionnés des
deux bancs et fonctionne hors réseau. Les liaisons XLink doivent conserver
l’arborescence de chaque répertoire `model`. La reproduction des mesures
utilise de nouveaux processus, donc les identifiants, dates et empreintes des
reçus produits varient.

Depuis le dossier de travail C.1, compiler le commit indiqué dans
[le gel](perturbation_freeze.json). Préparer aussi le dossier historique avec
les entrées A.2 aux empreintes de son registre et la fermeture locale V3-A
selon la [recette V3-I](../i/REPORT.md).

```powershell
$env:Path = 'C:/msys64/ucrt64/bin;' + $env:Path
$freecad = 'C:/Program Files/FreeCAD 1.1/bin/python.exe'
$ucrtPython = 'C:/msys64/ucrt64/bin/python.exe'
$work = ".runtime/v3-c1/rejeu-$([Guid]::NewGuid().ToString('N'))"
$history = (Resolve-Path '../..').Path
cmake -S architecture_decision_engine -B "$work/l3" -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake -S convergence_manager -B "$work/l5" -G Ninja -DCMAKE_BUILD_TYPE=Release "-DL5_FREECAD_PYTHON=$freecad"
cmake -S simulation -B "$work/t0" -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build "$work/l3" --parallel 4
cmake --build "$work/l5" --parallel 4
cmake --build "$work/t0" --parallel 4 --target cartographe-evidence
$argsC1 = @('--core', "$work/l5/convergence_core.exe", '--l3', "$work/l3/architecture_decision_core.exe",
            '--freecad', $freecad, '--python', $ucrtPython, '--t0', "$work/t0/cartographe-evidence.exe")
& $ucrtPython -B convergence_manager/tests/replay_v3_c1.py @argsC1 --output "$work/campaign"
& $ucrtPython -B convergence_manager/tests/replay_v3_c1_regressions.py @argsC1 --ctest C:/msys64/ucrt64/bin/ctest.exe `
  --build-l3 "$work/l3" --build-l5 "$work/l5" --historical-root $history --output "$work/regressions"
```

Le rejeu exécute au plus 30 propositions et six constructions par phase.
La graine 2026 et l’ordre des objectifs sont indiqués dans le gel. Le code
0 atteste la finalisation et les trois sélections attendues. Le code 4
renvoie aux écarts de `generalization.json`. Consulter le reçu T0 de chaque
phase, puis les réouvertures B.2 et la fermeture du candidat retenu.

Pour rejouer les injections sur le candidat retenu de T1 et recalculer
l’acceptation depuis les sorties locales :

```powershell
$winner = (Get-Content "$work/campaign/t1/T1/campaign.json" -Raw | ConvertFrom-Json).retained.candidate_id
$transaction = "$work/campaign/t1/T1/candidates/$winner/construction/transaction"
& $ucrtPython -B convergence_manager/tests/test_v3_c1_native_faults.py --freecad $freecad `
  --transaction $transaction --output "$work/native-faults"
& $ucrtPython -B convergence_manager/tests/collect_v3_c1_evidence.py --campaign "$work/campaign" `
  --regressions "$work/regressions/regressions.json" --native-faults "$work/native-faults/adversarial.json"
```

Les preuves brutes sous `.runtime` comprennent les copies privées, les
journaux et les résultats natifs. Les métriques et la portée de la
qualification sont référencées depuis DOC-VAL.
