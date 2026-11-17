# Validateur électromécanique indépendant L4

Depuis la racine du projet, compiler avec Qt 6 Core et un compilateur C++17.
Les contrôles CAO utilisent deux processus du Python embarqué de FreeCAD.
Les bancs Cables utilisent les scripts et modèles existants. Le jeu de
réception déclare ses critères et références dans `fixtures/reference.json`.

```powershell
$build = '.runtime/l4-build'
cmake -S validation_engine -B $build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH=C:/msys64/ucrt64
cmake --build $build --parallel 4
ctest --test-dir $build --output-on-failure

$work = '.runtime/l4-' + (Get-Date -Format yyyyMMdd-HHmmssfff)
New-Item -ItemType Directory -Path $work | Out-Null
$core = "$build/validation_core.exe"
$freecad = 'C:/Program Files/FreeCAD 1.1/bin/python.exe'
python -B validation_engine/tests/connectivity_cases.py --output "$work/electrical"
$seal = (& $core seal --lock "$work/reference_lock.json" --freecad-python $freecad).Trim()
& $core campaign --lock "$work/reference_lock.json" --lock-sha256 $seal `
  --candidates "$work/electrical" --output "$work/reception"
```

Conserver l’empreinte émise par `seal` dans le dossier d’autorité de la
campagne et la transmettre séparément du candidat. Elle fixe la révision
des exigences, la recette, le binaire, les scripts et les deux interpréteurs
de la mesure. Une recompilation ou une modification du référentiel demande
un nouveau gel. Les scripts et interpréteurs s’exécutent sur un hôte de
validation de confiance. Le natif doit être issu d’une source autorisée.
Pour un rejeu sans FreeCAD, omettre `--freecad-python` au gel ou utiliser
`--skip-native` à l’exécution. Les contrôles concernés donnent `NOT_RUN`.

Les sorties d’une campagne se trouvent dans un dossier neuf. Lire
`campaign.json`, puis `SUMMARY.md` et les rapports `cases/*.json`. Les
mesures brutes, projections et traces des deux processus sont sous `native/`.
`original_sources.json` contient les empreintes avant et après contrôle.
`traceability.json` relie chaque exigence aux preuves et aux constats.
Les codes de la CLI sont `0` pour `L4_PASS`, `2` pour `L4_FAIL`, `3` pour
`L4_CONDITIONAL` et `1` pour un arrêt sans finalisation. Un défaut injecté
reconnu par le validateur est une réussite de la recette. Vérifier la présence
du manifeste T0 et le verdict de réception pour interpréter le code retour.

`cartographe-evidence validate <dossier> .` vérifie les artefacts T0.
Avec `jsonschema` 4.x, `python -B validation_engine/tests/verify_reports.py
<dossier>` vérifie les enregistrements et les liens L0 de chaque cas.

## Évaluer un candidat sauvegardé

Le cas `saved-bench` relit un FCStd monodocument compatible avec la géométrie
gelée du banc statique. Le candidat fournit le natif. La campagne fournit
indépendamment les identités, contacts, exclusions, seuils et repères de
mesure. Pour un cas V1, `--candidate` désigne le dossier JSON électrique.
Pour un cas mixte, `--electrical` fournit le graphe électrique et le contrat
de cas détermine la source native. L’identifiant de variante peut être fourni
avec `--candidate-id`.

```powershell
& $core validate --lock "$work/reference_lock.json" --lock-sha256 $seal `
  --case saved-bench --candidate "$work/reception/native/native-nominal/built/candidate.FCStd" `
  --candidate-id variante-cable --output "$work/revalidation"
```

Pour le banc de convergence L5, le cas `consolidated-bench` se gèle avec
`--configuration convergence_manager/fixtures/native/reference.json`.
Le validateur reçoit le natif et le gel, dont les entrées `model-system`
et `model-requirements` fixent le périmètre de mesure. Utiliser la
[recette L5](../convergence_manager/README.md) pour rejouer la consolidation.

Les rapports de sortie portent la projection `validation_report`, les
`validation_findings` et les `technical_evidence` L0. Les champs L4 conservent
les tolérances, les observations structurées, le périmètre et l’empreinte du
natif. La consommation L5 vérifie la finalisation, les SHA-256
des artefacts, l’identité du validateur, la même référence et les mêmes
critères avant une comparaison. Elle traite les contrôles obligatoires
ouverts et chaque périmètre séparément. Le verdict global de réception des
tests L4 est distinct du verdict d’un candidat. Les contrôles de graphe
électrique décrivent le dossier soumis. La concordance avec le montage réel
requiert une projection de confiance et des preuves applicables.
