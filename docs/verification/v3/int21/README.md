# Rejouer V3-INT.2.1

Les [commandes exécutées et leurs résultats](regressions.json), le
[diagnostic](diagnostic.json) et les [critères d’acceptation](acceptance.json)
identifient les entrées et la portée du rejeu. Le commit correctif testé est
`f8c5922c0fe2a4c5975d792edafd4d8221ad1ce4`. Utiliser Windows amd64,
MSYS2 UCRT64, Ninja, Qt 6, OpenSSL et FreeCAD 1.1.3 avec OCCT 7.8.1 et
Cables 0.3.7. Les scripts attendent PowerShell 7 et les chemins indiqués
dans les commandes exécutées.

## Préparer trois checkouts

Depuis le dépôt qui contient le checkout et les copies scellées de V3-D,
positionner `$recipes` sur le chemin absolu de ce répertoire `recipes`.
Utiliser des dossiers neufs sous `.runtime`.

```powershell
$root = (Get-Location).Path
$base = '07a65330360f58104d8cf3ffc1161017eac908b8'
$fix = 'f8c5922c0fe2a4c5975d792edafd4d8221ad1ce4'
git worktree add --detach .runtime/i21-base $base
git worktree add --detach .runtime/i21a $fix
git worktree add --detach .runtime/i21b $fix

& "$recipes/build.ps1" -Checkout "$root/.runtime/i21-base" `
  -Run "$root/.runtime/i21-base/.runtime/base" -Phase Baseline
foreach ($name in 'i21a', 'i21b') {
    $checkout = "$root/.runtime/$name"
    & "$recipes/build.ps1" -Checkout $checkout -Run "$checkout/.runtime/run" -Phase Recovery
}
```

Le mode `Baseline` exige le code de retour 8 du CTest ciblé. Les journaux
doivent montrer les deux échecs historiques. Le mode `Recovery` exige que
chaque suite complète passe et conserve les commandes de compilation.
Contrôler la présence de `-std=c++17` dans chaque `compile_commands.json`.

## Rejouer les protections et les références

Utiliser A et sa sortie `$run` pour les contrôles C.2 et A.5. C.2 T1
doit finaliser avant l’émission de la perturbation indépendante T2. Le
fichier publié dans `c2-t2-perturbation.json` concerne le gel de ce rejeu.
Pour une nouvelle exécution, demander à l’évaluateur de produire une
nouvelle entrée associée au gel, au problème et au candidat effectivement
retenu. Le [protocole C.2](../c2/REPORT.md) spécifie les champs, les
conditions temporelles et la réduction du domaine.

Exécuter `check_proofs.py before` depuis la racine comme indiqué
ci-dessous avant de lancer les protections.

```powershell
$a = "$root/.runtime/i21a"
$run = "$a/.runtime/run"
& "$recipes/build.ps1" -Checkout $a -Run $run -Phase NoCrypto
& "$recipes/guards.ps1" -Checkout $a -Run $run -Phase T1
# L'évaluateur fournit $perturbation sous .runtime dans le checkout A.
& "$recipes/guards.ps1" -Checkout $a -Run $run -Phase T2 -Perturbation $perturbation
& "$recipes/guards.ps1" -Checkout $a -Run $run -Phase T3
foreach ($phase in 'Boundaries', 'Collect', 'A5', 'T0') {
    & "$recipes/guards.ps1" -Checkout $a -Run $run -Phase $phase
}
```

La recette V3-D attend la racine historique `551db0d`, le cache L2
`.runtime/v3-b2/historical/l2-sealed` et la fermeture V3-A
`.runtime/v3-a/native-20261118-065605213/staged`. Ces copies sont
nécessaires à la comparaison indépendante avec les scellés historiques.

```powershell
$env:Path = 'C:/msys64/ucrt64/bin;' + $env:Path
$env:QT_QPA_PLATFORM = 'offscreen'
$env:PYTHONUTF8 = '1'
$python = 'C:/msys64/ucrt64/bin/python.exe'
Set-Location -LiteralPath $root
& $python -B "$recipes/check_proofs.py" before
& $python -B "$recipes/check_l1_input.py"
& $python -B "$recipes/check_proofs.py" sealed
& $python -B convergence_manager/tests/recheck_v3_d_legacy.py `
  --freecad 'C:/Program Files/FreeCAD 1.1/bin/python.exe' --output "$run/d-historical"
& $python -B "$recipes/check_proofs.py" after
```

Effectuer la mesure `before` avant les protections et la mesure `after`
après toutes les exécutions. Les natifs et résultats de campagnes restent
sous `.runtime`. La comparaison des sorties L2 porte sur leurs octets
produits avec le même binaire. Le rapprochement conserve aussi les
assertions documentaires historiques, dont le refus d’une topologie
modifiée même si son empreinte a été recalculée.
