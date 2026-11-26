# Rejouer les preuves V3-A.6

La révision exécutable testée et les empreintes des résultats figurent dans
[acceptance.json](acceptance.json). Le [protocole](protocol.md) décrit le
verrou, les états et la procédure de récupération. Exécuter les essais
sous Windows amd64, MSYS2 UCRT64, Qt 6, C++17, OpenSSL 3 et FreeCAD 1.1.3,
avec le code exécutable de cette révision, le harnais du commit de preuves
et le validateur T0
`cartographe-evidence` compilé localement. Conserver les sorties dans des
dossiers neufs sous `.runtime`. Les tests génèrent leurs attestations et clés
jetables de banc à chaque exécution.

## Compilation locale

Utiliser des chemins d’outils déjà installés et le même environnement pour
les builds et les essais. Cette commande met les résultats sous le checkout
A.6. Elle laisse la recette scellée INT.2.1 et ses références historiques en place.

```powershell
$env:Path = 'C:/msys64/ucrt64/bin;' + $env:Path
$env:QT_QPA_PLATFORM = 'offscreen'
$env:PYTHONUTF8 = '1'
$racine = (Get-Location).Path.Replace('\', '/')
$run = "$racine/.runtime/build-a6"
$python = 'C:/msys64/ucrt64/bin/python.exe'
$openssl = 'C:/msys64/ucrt64/bin/openssl.exe'
$freecad = 'C:/Program Files/FreeCAD 1.1/bin/python.exe'
$commun = @('-G','Ninja','-DCMAKE_BUILD_TYPE=Release','-DCMAKE_CXX_STANDARD=17',
    '-DCMAKE_CXX_STANDARD_REQUIRED=ON','-DCMAKE_CXX_EXTENSIONS=OFF',
    '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON','-DCMAKE_PREFIX_PATH=C:/msys64/ucrt64',
    "-DPython3_EXECUTABLE=$python")
function Build-A6($nom, $source, $options = @()) {
    cmake -S $source -B "$run/$nom" @commun @options
    if ($LASTEXITCODE) { throw "Configuration $nom" }
    cmake --build "$run/$nom" --parallel 3
    if ($LASTEXITCODE) { throw "Compilation $nom" }
}
Build-A6 l3 architecture_decision_engine
Build-A6 l4 validation_engine
Build-A6 t0 simulation
$natif = @("-DL5_FREECAD_PYTHON=$freecad", "-DL5_T0_VALIDATOR=$run/t0/cartographe-evidence.exe",
    '-DL5_A5_PHYSICAL_TRUST_SHA256=')
Build-A6 l5 convergence_manager ($natif + @(
    "-DL5_L1_EXECUTABLE=$run/l3/research/technical_research_core.exe",
    "-DL5_L3_EXECUTABLE=$run/l3/architecture_decision_core.exe",
    "-DL5_L4_EXECUTABLE=$run/l4/validation_core.exe", "-DL5_A5_OPENSSL_EXECUTABLE=$openssl"))
Build-A6 l5-faults convergence_manager ($natif + @('-DL5_A6_FAULT_INJECTION=ON'))
Build-A6 l5-no-crypto convergence_manager @('-DBUILD_TESTING=OFF',
    '-DCMAKE_DISABLE_FIND_PACKAGE_OpenSSL=TRUE','-DL5_A5_PHYSICAL_TRUST_SHA256=')
$l5 = "$run/l5/convergence_core.exe"
$l5AvecInjections = "$run/l5-faults/convergence_core.exe"
$l5SansCrypto = "$run/l5-no-crypto/convergence_core.exe"
```

## Campagne

1. Lancer les trois phases en remplaçant les variables par les chemins
   absolus des exécutables de cette compilation. Le rejeu défensif a besoin
   de la possibilité de créer une jonction et un lien physique jetables
   dans son propre dossier.

   ```powershell
   & $python -B convergence_manager/tests/test_v3_a6_transactions.py --phase positive --core $l5 --openssl $openssl --output .runtime/a6-positive
   & $python -B convergence_manager/tests/test_v3_a6_transactions.py --phase adversarial --core $l5 --no-crypto $l5SansCrypto --openssl $openssl --output .runtime/a6-adversarial
   & $python -B convergence_manager/tests/test_v3_a6_transactions.py --phase faults --core $l5AvecInjections --openssl $openssl --output .runtime/a6-faults
   ```
2. Rejouer L3/L5, T0, A.5 et C.2 avec les références scellées INT.2.1.
   Le gel C.2 référence le commit de code par son SHA, et l’évaluateur T2
   attend la clôture T1 avant de retirer l’option de support retenue.
   Il lie la restriction au gel, au problème et au candidat T1 effectivement
   observé. Rejouer T3 sur l’autre banc puis les refus, les défauts natifs et
   la contre-vérification C.2. Utiliser `tools/replay_sealed_test.py` en
   gardant les références d’origine intactes.

   ```powershell
   ctest --test-dir "$run/l3" --no-tests=error --output-on-failure
   ctest --test-dir "$run/l5" --no-tests=error --output-on-failure
   ctest --test-dir "$run/t0" --no-tests=error -R '^cartographe_(sitl_)?t0_contracts$' --output-on-failure
   ```

   Si le plafond enregistré de 30 s expire pour T0 SITL, consigner ce
   résultat et vérifier le même test avec un plafond local de 120 s. Pour
   reproduire ce rejeu, inclure le `CTestTestfile.cmake` du build T0 dans un
   autre répertoire privé, puis y appliquer
   `set_tests_properties(cartographe_sitl_t0_contracts PROPERTIES TIMEOUT 120)`.
   Garder le répertoire de travail du build T0 pour les deux tests.
3. Avant et après, comparer l’inventaire du checkout, l’archive historique A
   et une copie privée à la [fermeture scellée](../a/native_receipt.json).
   Les trois différences LF/CRLF historiques ne concernent que des preuves
   textuelles du checkout. La comparaison s’effectue sur les octets
   existants. Vérifier toutes les empreintes natives et l’ensemble des
   chemins XLink. Résultats et limites dans [regressions.json](regressions.json).

## Matrice d’admission livrée

| Domaine | Opération et porteur | Résultat |
|---|---|---|
| `TEST_ONLY / SYNTHETIC_BENCH` | `CREATE_SUPPORT(anchor:iso-carrier)`, P64 de banc, profil Workholding, revue exacte et bornes valides | Une transaction privée à consommation unique si chaque contrôle passe. |
| `TEST_ONLY / SYNTHETIC_BENCH` | P66, autre occurrence, autre opération ou effet hors domaine | `DENY`. |
| `TEST_ONLY / CARTOGRAPHER_PRIVATE_CAD` | Toute demande | `DENY`. |
| `PHYSICAL_MEASURED / CARTOGRAPHER_PRIVATE_CAD` | `CREATE_SUPPORT(anchor:iso-carrier)`, P64 ou P66 | `DENY`, `construction=NOT_RUN`, `physical_reception=NOT_RUN`. |

Deux supports synthétiques ont été vérifiés dans la même fermeture scellée,
avec tailles `[8,8,3]` et `[7.9,8,3]` mm et poses locales respectives
`[0,0,0]` et `[-0.5,0,0]` mm. La seconde position et la seconde taille
donnent des observations et une sauvegarde différentes. La contre-validation
porte sur les objets et leurs liens, les surfaces d’appui, les fixations,
les collisions, l’accès de service, les rayons de courbure et la topologie
L2 applicables au banc. [Preuves natives](native_validation.json)
