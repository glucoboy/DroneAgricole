# Rejouer V3-C.2 sur banc multi-faisceaux

Utiliser Windows amd64, C++17/Qt 6 avec MSYS2 UCRT64, Ninja et FreeCAD
1.1.3 avec OCCT 7.8.1 et Cables 0.3.7. Compiler L3, L5 et le validateur
indépendant `cartographe-evidence` dans des dossiers neufs. La recette
de [V3-INT.1](../int1/REPORT.md) donne les paramètres communs. La
campagne conserve le commit, les dépendances XLink, le profil et le
domaine de chacun des deux bancs.

```powershell
$env:Path = 'C:/msys64/ucrt64/bin;' + $env:Path
$python = 'C:/msys64/ucrt64/bin/python.exe'
$fc = 'C:/Program Files/FreeCAD 1.1/bin/python.exe'
$run = ".runtime/c2-rejeu-$([guid]::NewGuid().ToString('N'))"
$commands = @('--core', '<L5>/convergence_core.exe', '--l3', '<L3>/architecture_decision_core.exe',
              '--t0', '<T0>/cartographe-evidence.exe', '--freecad', $fc, '--python', $python, '--output', $run)
& $python -B convergence_manager/tests/replay_v3_c2.py @commands --phase T1
```

Après finalisation de T1, transmettre son `summary.json`, le problème
typé et le `freeze.json` à l’évaluateur. L’évaluateur prépare une
perturbation sous `.runtime` dans une entrée distincte du moteur. Inclure
la version `v3.c2.external_perturbation/1`, `freeze_sha256`,
`base_problem_sha256`, `evaluated_candidate_sha256`, `issued_at_utc` et
`narrowing`. Le SHA du candidat est `retained.result_sha256` dans le
résultat T1. La restriction réduit les bornes `translation_mm` ou la
liste `support_zones` et exclut le candidat T1. Garder le fichier et son
empreinte. Rejouer le même commit, les mêmes binaires et les mêmes règles.

```powershell
$restriction = '<restriction-externe.json>'
$sha = (Get-FileHash $restriction -Algorithm SHA256).Hash.ToLowerInvariant()
& $python -B convergence_manager/tests/replay_v3_c2.py @commands --phase T2 `
  --perturbation $restriction --perturbation-sha256 $sha
& $python -B convergence_manager/tests/replay_v3_c2.py @commands --phase T3
```

Un code 0 requiert un candidat contre-validé. Le code 4 indique une
campagne finalisée sans candidat admissible. Lire la trace, le rapport
T0, les mesures B.2 et le journal de rollback avant toute interprétation.
Comparer les câbles et supports par occurrence et repère dans le natif
sauvegardé. La portée est `SYNTHETIC_BENCH`.

Les vérifications et leurs empreintes figurent dans les
[régressions](regressions.json) et les [refus](adversarial.json). Utiliser
une destination neuve pour la revue indépendante et pour le recalcul du
[verdict](acceptance.json).

```powershell
& $python -B convergence_manager/tests/collect_v3_c2_evidence.py --campaign $run `
  --t0 '<T0>/cartographe-evidence.exe' --output "${run}-review"
& $python -B convergence_manager/tests/evaluate_v3_c2.py --receipts docs/verification/v3/c2 `
  --output "$run/acceptance-recalculated.json"
```
