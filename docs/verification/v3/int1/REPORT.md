# Rejouer V3-INT.1

[Résultat et conditions de passage](../../../VALIDATION_QUALIFICATION.md#cartographe-v3-int1) ·
[Fusion et empreintes](merge_manifest.json) · [Commandes et sorties](regressions.json) ·
[Refus](adversarial.json) · [Acceptation](acceptance.json)

Utiliser Windows amd64 avec MSYS2 UCRT64, Qt 6, Ninja et FreeCAD 1.1.3
avec OCCT 7.8.1 et Cables 0.3.7. Le manifeste identifie les deux parents et
le reçu d'acceptation désigne la révision à compiler. Créer une copie de
travail sous `.runtime` de la racine historique V3-D. Les recettes A.2,
A.3 et D utilisent cette racine et ses données scellées. Consulter
[la recette A.4](../a4/REPORT.md) pour les quatre fermetures et Q2.

Depuis la copie intégrée, créer des répertoires neufs pour les quatre builds.
Les réglages CMake exacts et les empreintes des binaires figurent dans
`regressions.json`. Renseigner `L5_L1_EXECUTABLE`, `L5_L3_EXECUTABLE`,
`L5_L4_EXECUTABLE`, `L5_T0_VALIDATOR` et `L5_FREECAD_PYTHON` pour enregistrer
`l5_cli` et les contrôles natifs.

```powershell
$env:Path = 'C:/msys64/ucrt64/bin;' + $env:Path
$env:QT_QPA_PLATFORM = 'offscreen'
$fc = 'C:/Program Files/FreeCAD 1.1/bin/python.exe'
$python = 'C:/msys64/ucrt64/bin/python.exe'
$history = (Resolve-Path '../..').Path
$run = ".runtime/rejeu-int1-$([guid]::NewGuid().ToString('N'))"
$common = @('--core', "$run/l5/convergence_core.exe", '--l3', "$run/l3/architecture_decision_core.exe",
            '--freecad', $fc, '--python', $python, '--t0', "$run/t0/cartographe-evidence.exe")
# Configurer et compiler les quatre builds dans $run comme indiqué dans regressions.json.
& $python -B convergence_manager/tests/replay_v3_c1.py @common --output "$run/campaign"
& $python -B convergence_manager/tests/replay_v3_c1_regressions.py @common `
  --ctest C:/msys64/ucrt64/bin/ctest.exe --build-l3 "$run/l3" --build-l5 "$run/l5" `
  --historical-root $history --output "$run/regressions"
$winner = (Get-Content -Raw "$run/campaign/t1/T1/campaign.json" | ConvertFrom-Json).retained.candidate_id
& $python -B convergence_manager/tests/test_v3_c1_native_faults.py --freecad $fc `
  --transaction "$run/campaign/t1/T1/candidates/$winner/construction/transaction" --output "$run/native-faults"
```

Garder `HEAD`, les entrées, les programmes et les réglages fixes pendant
la campagne C.1. Le rejeu gèle les sources et relit le gel après chaque
phase. Une interruption exige une nouvelle destination. Le collecteur
historique C.1 écrit dans son dossier versionné. Utiliser les reçus
produits dans le nouveau dossier de résultats pour la décision INT.1.

Lancer aussi le CTest L3 complet. Pour `l2_reconcile` et
`technical_research_engine`, les recettes scellées emploient les octets
conservés par V3-D et le nouveau binaire. Conserver les deux résultats
du checkout neuf et de la référence scellée.

Rejouer ensuite [l'import et les régressions A.4](../a4/REPORT.md) avec
`cartographe_material_evidence`, `convergence_core`, le validateur T0 et
le binaire L2 issus de ces builds. Enchaîner A.3 avant la vérification de
transaction A.4, sur une fermeture privée. Utiliser le [criblage A.3](../a3/REPORT.md#rejouer-les-mesures)
pour comparer les sondes et routes en lecture seule. Conserver les
archives locales et les sorties natives en dehors de Git.

La décision enregistrée se recalcule à partir des trois reçus structurés.
Le fichier de sortie doit être nouveau.

```powershell
& $python -B convergence_manager/tests/evaluate_v3_int1.py `
  --receipts docs/verification/v3/int1 --output "$run/acceptance-recalculated.json"
```
