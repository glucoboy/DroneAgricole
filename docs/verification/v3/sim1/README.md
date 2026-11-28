# Rejouer V3-SIM.1

Depuis la racine du worktree SIM.1, utiliser Qt 6 et un compilateur C++17.
Le rejeu de référence utilise Windows amd64, MSYS2 UCRT64, CMake/Ninja,
Python 3.14.7 et le Python livré avec FreeCAD 1.1.3 (OCCT 7.8.1).
Le chargement Gazebo et l'exécution PX4 ne font pas partie de ces commandes.

## Préparer et vérifier une copie privée

La copie porte les sources listées par le manifeste CAO et les entrées de
l'exporteur. Dans un worktree neuf, `--manufacturer-root` indique la racine
locale autorisée qui détient les originaux fabricant hors Git. La recette
refuse l'absence d'un original et tout écart d'empreinte. Le modèle
historique et les gros STL restent à leur emplacement d'origine.

```powershell
$env:Path = 'C:/msys64/ucrt64/bin;' + $env:Path
$env:QT_QPA_PLATFORM = 'offscreen'
$env:PYTHONDONTWRITEBYTECODE = '1'
$py = 'C:/msys64/ucrt64/bin/python.exe'
$fc = 'C:/Program Files/FreeCAD 1.1/bin/python.exe'
$manufacturer = (Resolve-Path ../..).Path # À adapter à la copie locale des originaux
$private = '.runtime/sim1/rejeu'
$build = '.runtime/sim1-build-modele'
$null = New-Item -ItemType Directory -Force .runtime/sim1/tmp
$env:TEMP = $env:TMP = (Resolve-Path .runtime/sim1/tmp).Path
& $py -B simulation/gazebo/tools/stage_sim1_snapshot.py --destination $private --manufacturer-root $manufacturer
if ($LASTEXITCODE) { throw 'Copie des sources incomplète' }
$snapshot = (Resolve-Path $private).Path
cmake -S simulation -B $build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH=C:/msys64/ucrt64 `
  "-DPython3_EXECUTABLE=$py" "-DCARTOGRAPHE_SIM1_PRIVATE_ROOT=$snapshot" "-DCARTOGRAPHE_SIM1_FREECAD_PYTHON=$fc"
cmake --build $build --parallel 2
& "$build/cartographe-model.exe" diagnose . $fc > .runtime/sim1/diagnostic-rejeu.json
& "$build/cartographe-model.exe" verify . simulation/gazebo/models/cartographe
# Refus attendu « stale CAD manifest » sur les dérivés historiques.
ctest --test-dir $build --no-tests=error --output-on-failure -R '^cartographe_model_' -V
ctest --test-dir $build --no-tests=error --output-on-failure -R '^cartographe_(sitl_)?t0_contracts$' -V
```

Séparer le rejeu T0 des compilations et campagnes concurrentes. Si le
contrat SITL atteint le plafond de 30 s, rejouer avec les paramètres
de lecture Git du reçu de qualification. Ces paramètres s'appliquent
uniquement à la session de rejeu.

```powershell
$env:Path = 'C:/msys64/ucrt64/bin;C:/Program Files/Git/cmd;C:/Windows/System32;C:/Windows'
$env:GIT_OPTIONAL_LOCKS = '0'
$env:GIT_CONFIG_COUNT = '2'
$env:GIT_CONFIG_KEY_0 = 'core.fscache'
$env:GIT_CONFIG_VALUE_0 = 'true'
$env:GIT_CONFIG_KEY_1 = 'core.preloadIndex'
$env:GIT_CONFIG_VALUE_1 = 'false'
ctest --test-dir $build --parallel 1 --no-tests=error --output-on-failure -R '^cartographe_(sitl_)?t0_contracts$' -V
```

Le pilote de refus des chemins crée une jonction et un lien physique NTFS
dans un dossier jetable. Le compte de test doit pouvoir créer ces témoins.
Sans configuration de la copie privée ou sans les entrées hors Git, la
génération native est signalée `NOT_RUN`. Les tests rapides utilisent un
modèle synthétique réduit.

## Générer et vérifier un paquet sans CTest

```powershell
& "$build/cartographe-model.exe" rebuild $snapshot $fc .runtime/export/cartographe
& "$build/cartographe-model.exe" verify $snapshot .runtime/export/cartographe
& "$build/cartographe-model.exe" verify $snapshot .runtime/export/cartographe --physical
# Le dernier appel doit refuser les propriétés physiques inconnues.
```

La destination doit être neuve. Le JSON renvoyé par `rebuild` identifie le
paquet et ses empreintes. L'horodatage des manifestes peut varier au rejeu.
Les comparaisons de SHA portent sur les octets produits par chaque exécution.
Le fichier [snapshot_manifest.json](snapshot_manifest.json) conserve les
empreintes et paramètres du rejeu publié. Le
[reçu de génération](rebuild_receipt.json) permet de repérer le paquet
privé et de comparer ses métriques.

Les régressions L1/L2, L3/L4/L5, A.5/A.6 et C.2/C.3 se rejouent avec les
[recettes INT.3](../int3/REPORT.md#reproduction-depuis-le-merge-de-revue) depuis ce worktree.
Les [reçus de régression](regressions.json) identifient les batteries
effectivement exécutées et les preuves historiques conservées.
