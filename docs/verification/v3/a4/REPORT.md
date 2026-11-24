# Rejouer V3-A.4

[DOC-VAL](../../../VALIDATION_QUALIFICATION.md#cartographe-v3-a4) ·
[Commandes et reçus](regressions.json) · [Inventaire SHA-256](artifacts.json)

## Compiler et vérifier l'import

Windows amd64, C++17, Qt 6 et Ninja. Depuis la branche A.4, compiler dans un
dossier isolé. Les commandes utilisent les installations locales de MSYS2 et
FreeCAD 1.1.3. Le dossier et le [dépôt des preuves](measurement_packet.md)
peuvent rester hors réseau.

```powershell
$env:Path = 'C:/msys64/ucrt64/bin;' + $env:Path
$work = '.runtime/v3-a4'
$paper = 'docs/verification/v3/a4'
$freecad = 'C:/Program Files/FreeCAD 1.1/bin/python.exe'
cmake -S convergence_manager -B "$work/build" -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build "$work/build" --parallel 4
ctest --test-dir "$work/build" -R '^l5_v3_a4_material_evidence$' --output-on-failure
New-Item -ItemType Directory -Path "$work/releves" -Force | Out-Null
$blankPolicyHash = (Get-FileHash "$paper/review_policy.json").Hash.ToLowerInvariant()
$validator = "$work/build/cartographe_material_evidence.exe"
& $validator --raw-root "$work/releves" --packet "$paper/measurement_form.json" `
  --policy "$paper/review_policy.json" --policy-sha256 $blankPolicyHash
& $validator --raw-root "$work/releves" --packet "$paper/example_not_authority.json" `
  --policy "$paper/review_policy.json" --policy-sha256 $blankPolicyHash
```

Le paquet vide rend `NOT_RUN` (code 0). L'exemple rend
`EXAMPLE_NOT_AUTHORITY` (code 2). Un paquet réel et une politique de
revue éventuelle sont distincts. Obtenir l'empreinte de la politique réelle
directement du responsable par le canal de revue convenu. Le calcul couvre
l'identité et les versions, l'intégrité et les chemins d'artefacts, les
repères orientés dans les deux sens, les comparaisons `LE`/`GE`, et
l'intervalle d'incertitude. La lisibilité d'une photo, l'applicabilité de la
tolérance en atelier et l'authentification d'une signature relèvent de la
revue habilitée. Une entrée compatible est `PENDING_AUTHORIZED_REVIEW`
et la sortie d'import conserve `authority=DENY`. Le reviewer est configuré
en dehors des données soumises. Une politique vierge accompagne cette
campagne. Une configuration de revue ultérieure doit suivre la procédure
du responsable matériel et l'historique de preuves doit être conservé.

## Rejouer les régressions en lecture seule

Utiliser comme racine de travail V3-D `551db0d9c9cda8a7717aa4aa99b407b2861417b8`
avec les dépendances scellées utilisées par A.2/A.3 et les archives GO3B.
Travailler depuis ce checkout pour conserver les octets des reçus historiques.
Préparer un dossier de sortie neuf sous son `.runtime`. Affecter `$a4` à
la racine A.4 et `$t0` au validateur T0 construit selon la recette V3-I.

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
$env:PYTHONPATH = (Get-Location).Path
$private = ".runtime/a4-rejeu-$([Guid]::NewGuid().ToString('N'))"
$core = "$a4/.runtime/v3-a4/build/convergence_core.exe"
$validator = "$a4/.runtime/v3-a4/build/cartographe_material_evidence.exe"
New-Item -ItemType Directory -Path $private | Out-Null
python -B convergence_manager/tests/verify_v3_a2_evidence.py --core $core --out "$private/a2-integrity"
python -B convergence_manager/tests/test_v3_a3_authorities.py --core $core `
  --source hardware/mecanique/cartographe --out "$private/admission"
python -B -m electromechanical_engine.v3_a2_native --freecad-python $freecad --work "$private/native"
python -B convergence_manager/tests/recheck_v3_d_legacy.py --freecad $freecad --output "$private/legacy"
python -B interconnection_engine/tests/replay_fix_a_q2.py --original .runtime/v3-a1/regressions/q2-history `
  --binary .runtime/v3-a1/regressions/build-l4/interconnection/interconnection_core.exe `
  --freecad $freecad --output "$private/q2"
python -B "$a4/convergence_manager/tests/test_v3_a4_evidence.py" --validator $validator --core $core `
  --reference-root (Get-Location).Path --transaction-out "$private/a4-private-transaction" `
  --freecad $freecad --t0 $t0 --out "$private/adversarial.json"
```

Utiliser le [criblage V3-A.3](../a3/REPORT.md#rejouer-les-mesures) avec la
même racine historique et ses sources privées. Les résultats FreeCAD
comparables concernent les quatre fermetures et les sept paires ciblées.
Les mesures de gabarits de service servent au diagnostic de la CAO.
Les régressions CTest L5 complètes utilisent aussi les exécutables L1, L3,
L4 et T0 indiqués dans [les commandes](regressions.json). Les fichiers bruts
des relectures restent sous `.runtime`. Les chemins sont relatifs au
checkout d'A.4 sauf mention explicite de la référence historique.

Depuis A.4, vérifier le dossier publié et recalculer son verdict avec
`python -B convergence_manager/tests/test_v3_a4_evidence.py --dossier docs/verification/v3/a4`.
