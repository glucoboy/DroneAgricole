# Moteur d’exploration électromécanique L3

Compiler depuis la racine avec CMake, un compilateur C++17, Qt 6 Core et
Network, et Python 3 pour CTest. Avec MSYS2 UCRT64, placer les DLL Qt et GCC
dans le `PATH`.

```powershell
$build = '.runtime/l3_build'
$run = '.runtime/l3_' + (Get-Date -Format yyyyMMdd_HHmmssfff)
cmake -S architecture_decision_engine -B $build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH=C:/msys64/ucrt64
cmake --build $build --parallel 4
ctest --test-dir $build --output-on-failure
& "$build/architecture_decision_core.exe" --l1 "$build/research/technical_research_core.exe" --output $run
```

La CLI attend un dossier de sortie neuf dont le parent existe. Elle émet
`0` pour `L3_PASS`, `3` pour `L3_CONDITIONAL`, `2` pour `L3_FAIL` et `1`
en cas d’incident d’entrée, d’exécution ou de publication. La présence
du manifeste T0 terminal identifie une exécution finalisée.

Les [bancs](fixtures/benches.json) déclarent les changements de paramètres,
les liaisons, les causes qui déclenchent les variantes et le budget. Le moteur
suit l’ordre déclaré. Le banc diagnostic demande deux échecs locaux avant
l’escalade. Les [exigences](fixtures/requirements.json) sont gelées séparément
et les [critères de réception](fixtures/acceptance.json) contrôlent les sorties.
`--benches`, `--requirements` et `--acceptance` acceptent d’autres fichiers sous
la racine pour les tests de mutation. L’énumération est déterministe et sa
graine est `null`. Le modèle et les rapports L0–L2 utilisent leurs contrats
existants. `decisions.json` porte le cycle de vie des variantes de banc L3.

Consulter `campaign.json`, `decisions.json`, `comparison.json` et `candidates/`
dans le dossier du rejeu. Les projections et rapports L2 sont dans les
fichiers `*-l2.json`. Le rapport L1, sa provenance et sa conclusion
documentaire sont dans `f31-lateral-research.json`. Les horodatages
d’exécution L1 font varier certaines empreintes entre rejeux.

Vérifier les empreintes et les cinq fichiers T0 avec le validateur existant.

```powershell
$validatorBuild = '.runtime/l3_t0_validator'
cmake -S simulation -B $validatorBuild -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH=C:/msys64/ucrt64
cmake --build $validatorBuild --target cartographe-evidence
& "$validatorBuild/cartographe-evidence.exe" validate $run .
```

[Réception L3](../docs/electromechanical_v2/L3_RESULT.md) ·
[Périmètre des résultats](../docs/VALIDATION_QUALIFICATION.md#moteur-electromecanique-v2-l3)
