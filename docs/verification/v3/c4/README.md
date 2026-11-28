# Rejouer V3-C.4 sur les bancs synthétiques

Utiliser Windows amd64, GCC/Qt 6 MSYS2 UCRT64, C++17 sans extensions,
FreeCAD 1.1.3 avec OCCT 7.8.1 et Cables 0.3.7. Partir d’un checkout propre
du commit testé dans [l’acceptation](acceptance.json). Les deux profils et
leurs fermetures XLink sont versionnés. Le générateur de bancs
`convergence_manager/tests/make_v3_c4_fixtures.py` dérive les scènes sur
copies. Une régénération des archives FCStd nécessite un nouveau gel.

Construire L3, L4, L5 et T0 dans des dossiers neufs selon la
[recette de compilation INT.3](../int3/integration/recipes/replay_builds.py).
Fournir les chemins FreeCAD et T0 à CMake pour le L5 nominal. Le runner
utilise trois processus FreeCAD distincts pour la construction, la
réouverture et la contre-mesure. Il épingle les outils, domaines, profils,
graphes et natifs avec SHA-256. Le T0 est contrôlé au niveau de chaque
transaction et à la finalisation de la campagne.

```powershell
$env:PATH = "C:/msys64/ucrt64/bin;$env:PATH"
$env:QT_QPA_PLATFORM = 'offscreen'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$py = 'C:/msys64/ucrt64/bin/python.exe'
$fc = 'C:/Program Files/FreeCAD 1.1/bin/python.exe'
$build = '.runtime/b'
$run = '.runtime/c4-rejeu'
$runner = 'convergence_manager/tests/replay_v3_c4.py'
$common = @('--output', $run, '--core', "$build/l5/convergence_core.exe",
  '--l3', "$build/l3/architecture_decision_core.exe",
  '--t0', "$build/t0/cartographe-evidence.exe", '--freecad', $fc, '--python', $py)
& $py -B $runner @common --phase T1
& $py -B $runner @common --phase T3
& $py -B $runner @common --phase T4
```

Après T1, transmettre `T2-HANDOFF.json` à l’évaluateur. Dans un répertoire
privé distinct, l’évaluateur émet un reçu UTC après le gel, renseigne
les trois empreintes et mesure l’intersection du solide avec la fermeture
T1 en FreeCAD. Le témoin porte sur le câble impacté. Le constructeur
reçoit l’empreinte du fichier par un canal indépendant.

```powershell
& $py -B docs/verification/v3/c4/evaluate_t2.py --handoff "$run/T2-HANDOFF.json" `
  --output '.runtime/c4-evaluation' --profile 'docs/electromechanical_v3/bench_c4_sixdof/profile.json' `
  --freecad $fc
```

```powershell
$entry = (Resolve-Path -LiteralPath '.runtime/c4-evaluation/perturbation.json').Path
$externalSha = '<SHA-256 communiqué par l’évaluateur>'
& $py -B $runner @common --phase T2 --perturbation $entry --perturbation-sha256 $externalSha
& $py -B convergence_manager/tests/test_v3_c4_adversarial.py --campaign $run `
  --core "$build/l5/convergence_core.exe" --t0 "$build/t0/cartographe-evidence.exe" `
  --freecad $fc --openssl 'C:/msys64/ucrt64/bin/openssl.exe' --output '.runtime/c4-refus'
```

Pour les régressions d’autorité et les protections, appliquer la
[recette de clôture INT.3](../int3/REPORT.md#reproduction) au même
checkout, dans des dossiers privés distincts. Le témoin négatif de chemin
redirigé demande le droit Windows de créer une jonction de test. Lancer
les tests T0 hors concurrence et conserver les sorties du premier passage.

Le code 0 du runner signifie que le critère de phase est vérifié,
y compris l’arrêt T4 avec zéro admission. Le code 4 correspond à une phase
finalisée sans satisfaction du critère. Consulter la trace L5, le T0,
les matrices de ports et les gardes dans les résultats natifs. Les
candidats FreeCAD et les journaux détaillés restent sous `.runtime`.
