# Preuves reproductibles de l’admission V3-A.1

La base est `742a5ac4f167bba0ef03b65053412bddbde0ecc9`. Le témoin
V3-B est le reçu `docs/verification/v3/b/acceptance.json` du commit
`e0906927c53e7079e65ca1027d46702e6d3a3a17`. Il consigne
`V3_B_NO_GO` à `V3_A_ADMISSION` et zéro transaction.

## Périmètre des décisions

| Contrôle | Autorité et résultat |
|---|---|
| Validité du modèle V3-A | Le gel couvre l’inventaire, la migration et l’impact virtuel dans son périmètre. [Acceptation V3-A](../a/acceptance.json) |
| Essai d’opérateurs sur banc | `ALLOW / BENCH_TEST_ONLY` pour quatre opérations sur une copie du banc scellé. `NOT_IMPLEMENTED` au dispatch natif. [Reçu V3-A.1](admission.json) |
| CAO exploratoire sur copie cartographe | Les trois analyses d’impact sont admises sur des copies en lecture seule. Toute mutation reste bloquée en attente des préconditions locales. Un futur essai conditionnel devra lier explicitement son hypothèse, les garanties vérifiées et les contrôles de la copie. |
| Admission de conception du cartographe | `DENY`. V3-A.2 doit établir les connecteurs du lot retenu, J2/J3, les repères indépendants, le brochage, les ancrages, le rayon dynamique et les gestes de service. Les huit issues UART et les défauts hérités restent dans les preuves. |
| Réception physique | `NOT_RUN`. Exige essais du matériel et protocole GO4. |

## Transition vers B.1

La demande suit le [schéma `v3.admission_scope/1`](../../../electromechanical_v3/admission_scope.schema.json)
et reprend les valeurs exactes de chaque opérateur dans le
[sceau](../../../electromechanical_v3/bench_a1/seal.json). Une demande
porte une opération et une occurrence. Les valeurs numériques sont exprimées
en millimètres, degrés ou millimètres cubes selon la contrainte.
L5 vérifie l’empreinte du reçu natif du banc et son rattachement au sceau.

| Opération | Occurrence | Effet soumis à la porte | Contrôle supplémentaire |
|---|---|---|---|
| `REPOSITION_DEVICE` | `bench:device` | `{"placement_mm":[24,20,4]}` | `L4_DYNAMIC_BEND_RADIUS` |
| `REROUTE_HARNESS` | `bench:harness` | `{"corridor":"BENCH_CORRIDOR_B"}` | `L4_DYNAMIC_BEND_RADIUS` |
| `RELOCATE_SUPPORT` | `bench:support` | `{"anchor":"bench:anchor-relocate"}` | `L4_SUPPORT_ANCHOR` |
| `CREATE_SUPPORT` | `bench:anchor-new` | `{"support":"bench:support-new","design":"BENCH_CLIP"}` | `L4_SUPPORT_ANCHOR` |

Les onze identifiants de contrainte sont
`BMS_USB_STRUCTURE_ISOLATION`, `NC`, `TX_RX`, `PROTECTIONS`,
`PINOUT`, `INDEPENDENT_FRAMES`, `GEOMETRY`, `SUPPORT_ANCHOR`,
`SERVICE`, `IMMUTABLE_SOURCES` et `DYNAMIC_BEND_RADIUS`.
La liste ordonnée des validations est scellée par opération. Le tronc
commun comprend `REOPEN_XLINK`, `L2_TOPOLOGY`, `L4_GEOMETRY`,
`L4_SERVICE`, `VERIFY_IMMUTABLE_SOURCES` et `VALIDATE_T0`.

B.1 devra vérifier de nouveau les octets et les chemins au point
d’exécution, préparer sa propre copie transactionnelle sans liens physiques
partagés, limiter l’opérateur à la fermeture et à l’effet autorisés, puis
revérifier les sources. Une expérience admise peut produire une géométrie
non conforme. Le résultat doit alors enregistrer le défaut observé avant
rejet et abandon de la copie privée.

## Rejeu de l’admission

Depuis la racine, avec Windows amd64, GNU MinGW UCRT 16.2.0, Qt 6.11.2,
CMake 4.4.2 et Ninja 1.13.2. Les essais natifs utilisent FreeCAD 1.1.3,
OCCT 7.8.1 et Cables 0.3.7. Le banc se prépare à partir du
[rejeu natif](../../../electromechanical_v3/bench_a1/README.md).

```powershell
$env:PATH = "C:/msys64/ucrt64/bin;$env:PATH"
cmake -S convergence_manager -B .runtime/v3-a1/build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_STANDARD=17 -DCMAKE_CXX_STANDARD_REQUIRED=ON
cmake --build .runtime/v3-a1/build --parallel 4
ctest --test-dir .runtime/v3-a1/build -R 'l5_' --output-on-failure --output-junit l5-tests.xml
```

Les tests produisent `trace-policy.json` et `trace-entry.json` dans
le répertoire de compilation. Avec les artefacts V3-A scellés disponibles,
ils couvrent aussi les trois demandes virtuelles sur le cartographe.
Les tests liés au banc utilisent uniquement les fixtures versionnées.
Le contrôle de jonction Windows et celui de lien physique exigent la
permission de créer ces entrées dans le répertoire temporaire du test.
Ils se rejouent avec le filtre CTest `^l5_v3_admission_(entry|policy)$`.
Les oracles du cartographe sont rejoués sur une nouvelle copie byte-exacte
en lecture seule, préparée par les tests à partir du témoin V3-A.

Pour soumettre une demande exacte au point d’entrée L5, utiliser un nouveau
dossier de travail et préparer une copie XLink d’entrée en lecture seule.

```powershell
$source = 'docs/electromechanical_v3/bench_a1'
$sealPath = Join-Path $source 'seal.json'
$seal = Get-Content -Raw -Encoding utf8 $sealPath | ConvertFrom-Json -AsHashtable
$caseDir = ".runtime/v3-a1/replay-$([Guid]::NewGuid().ToString('N'))"
$sandbox = Join-Path $caseDir 'input'
foreach ($name in $seal.xlink_dependencies.Keys) {
    $to = Join-Path $sandbox $name
    New-Item -ItemType Directory -Force -Path (Split-Path $to) | Out-Null
    Copy-Item -LiteralPath (Join-Path $source $name) -Destination $to
    (Get-Item -LiteralPath $to).IsReadOnly = $true
}
$operation = 'REPOSITION_DEVICE'
$request = @{
    schema = 'v3.admission_scope/1'
    domain = 'SYNTHETIC_BENCH'
    model_id = $seal.model_id
    model_version = $seal.model_version
    freeze_sha256 = (Get-FileHash -LiteralPath $sealPath).Hash.ToLowerInvariant()
    geometry_sha256 = $seal.geometry_sha256
    xlink_dependencies = $seal.xlink_dependencies
    operation = $operation
    objective = 'Vérifier la porte de B.1 sur banc fermé'
    context = 'B1_CLOSED_BENCH'
    output = 'PRIVATE_CANDIDATE'
    source_mode = 'IMMUTABLE'
    rollback = 'DISCARD_PRIVATE_COPY'
    assumptions = @()
    risks = @('GEOMETRY_FAILURE')
}
foreach ($key in $seal.operations[$operation].Keys) {
    $request[$key] = $seal.operations[$operation][$key]
}
$request | ConvertTo-Json -Depth 20 | Set-Content -Encoding utf8 "$caseDir/request.json"
& .runtime/v3-a1/build/convergence_core.exe v3-admission --root . --request "$caseDir/request.json" --sandbox $sandbox --output "$caseDir/output"
$LASTEXITCODE
```

Le code 3 indique `ALLOW / NOT_IMPLEMENTED` avec zéro transaction et
`construction_result: NOT_RUN`. Le code 2 couvre les décisions
`DENY` ou `UNSUPPORTED`, le code 0 une admission de lecture seule et le
code 1 une erreur d’entrée ou de publication. Les demandes contenant
des clés JSON dupliquées sont rejetées avant la création de la sortie.
La preuve de porte est dans `$caseDir/output/admission.json`. L’analyse
virtuelle se calcule via les outils V3-A. Toute construction et sa
validation T0 relèvent de B.1.

## Rejeu des gardes historiques

Les commandes et les empreintes du graphe, de L2/L4, du banc C4, de Q2
et Q3 sont dans [regressions.json](regressions.json). Pour Q1, utiliser
le répertoire privé byte-exact de la recette V3-A avec les outils courants.

```powershell
$repo = (Get-Location).Path
Push-Location .runtime/v3-a-regressions/q1-private
python -B "$repo/convergence_manager/tests/test_admission.py" "$repo/.runtime/v3-a1/build/convergence_core.exe" -v
Pop-Location
```

La réconciliation L2 historique refuse les octets LF de l’actif et
réussit sur une copie privée correspondant au SHA-256 CRLF du gel
historique. Q1 sur l’actif refuse aussi les écarts de son gel historique.
Les onze scénarios passent sur la copie Q1 byte-exacte. La campagne B.2
de 1 609 paires et sept interférences demeure historique. Le banc C4
existe à son empreinte et a été rejoué séparément.

Pour intégrer `l5_cli` avec réouverture FreeCAD et validation indépendante
T0, reconfigurer le même build avec les binaires de l’environnement V3-A.

```powershell
$repo = (Get-Location).Path
cmake -S convergence_manager -B .runtime/v3-a1/build `
  "-DL5_L1_EXECUTABLE=$repo/.runtime/v3-a-regressions/build-l1-l3/research/technical_research_core.exe" `
  "-DL5_L3_EXECUTABLE=$repo/.runtime/v3-a-regressions/build-l1-l3/architecture_decision_core.exe" `
  "-DL5_L4_EXECUTABLE=$repo/.runtime/v3-a-regressions/build-l4/validation_core.exe" `
  "-DL5_FREECAD_PYTHON=C:/Program Files/FreeCAD 1.1/bin/python.exe" `
  "-DL5_T0_VALIDATOR=$repo/.runtime/v3-a-regressions/build-t0/cartographe-evidence.exe"
ctest --test-dir .runtime/v3-a1/build -R '^l5_cli$' --output-on-failure --output-junit l5-cli.xml
```

Les [traces adversariales](adversarial.json) détaillent les décisions,
les gardes exécutées et leurs limites. Les simulations Gazebo/PX4 SITL,
la construction V3-B.1 et la réception physique restent `NOT_RUN`.
