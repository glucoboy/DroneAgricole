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

## Problème paramétrique V3

Préparer la demande [v3.problem_spec/1](../docs/electromechanical_v3/problem_spec.schema.json)
avec les SHA-256 du domaine synthétique, du natif racine et de
l'observation indépendante. Indiquer la graine entière, les plafonds de
propositions et de créations natives, la boîte de translation et les
objectifs Pareto dans l'ordre de départage. Les bornes XYZ sont fermées
et exprimées en millimètres dans le repère de placement du domaine.
`support_zones` prépare une restriction des identifiants d'ancrages en L3.
La campagne V3-C utilise les ancrages imposés par le domaine de composition
et refuse une demande qui renseigne ce champ.

```powershell
& "$build/architecture_decision_core.exe" v3-problem --root . --request $request `
    --domain $domain --model $nativeRoot --observation $observation --output "$run/problem_spec.json"
```

Le parent du fichier de sortie doit exister. Avec le code `0`, la CLI
publie le fichier neuf et retourne son SHA-256. Une demande invalide
retourne `1`. La compilation du problème reste en lecture des entrées.
L5 vérifie l'autorité, les budgets, la fermeture et chaque proposition
avant la construction. Le problème donne un domaine de recherche et
les critères de comparaison à L5.

| Phase | Usage |
|---|---|
| `T0` | Préparer les données à engager avant la recherche. |
| `T1` | Chercher dans le domaine de départ déclaré. |
| `T2` | Fournir aussi `--base-problem <problem_spec T1>`. Le SHA du fichier T1 est inscrit dans `base_problem_sha256`. Le modèle, l'observation, le domaine, la graine, le budget et les objectifs restent ceux de T1. La campagne V3-C restreint strictement la boîte de translation. |
| `T3` | Appliquer le même contrat à un autre banc synthétique déjà autorisé. La preuve de campagne compare l'identité des bancs. |
