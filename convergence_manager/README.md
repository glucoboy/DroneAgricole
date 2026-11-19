# Campagne de convergence électromécanique L5

Compiler depuis la racine avec un compilateur C++17, Qt 6 Core et Network,
CMake et Python. Le parcours natif utilise le Python de FreeCAD avec Part
et Cables Workbench. Sous MSYS2 UCRT64, les DLL Qt et GCC doivent être dans
le `PATH`.

```powershell
$prefix = 'C:/msys64/ucrt64'
$freecad = 'C:/Program Files/FreeCAD 1.1/bin/python.exe'
$python = (Get-Command python).Source
$l3build = '.runtime/l5-l3-build'
$l4build = '.runtime/l5-l4-build'
$l5build = '.runtime/l5-build'
$t0build = '.runtime/l5-t0-build'
New-Item -ItemType Directory -Force .runtime | Out-Null
cmake -S architecture_decision_engine -B $l3build -G Ninja -DCMAKE_BUILD_TYPE=Release "-DCMAKE_PREFIX_PATH=$prefix"
cmake --build $l3build --parallel 4
cmake -S validation_engine -B $l4build -G Ninja -DCMAKE_BUILD_TYPE=Release "-DCMAKE_PREFIX_PATH=$prefix"
cmake --build $l4build --parallel 4
cmake -S simulation -B $t0build -G Ninja -DCMAKE_BUILD_TYPE=Release "-DCMAKE_PREFIX_PATH=$prefix"
cmake --build $t0build --target cartographe-evidence --parallel 4
$l1 = (Resolve-Path "$l3build/research/technical_research_core.exe").Path
$l3 = (Resolve-Path "$l3build/architecture_decision_core.exe").Path
$l4 = (Resolve-Path "$l4build/validation_core.exe").Path
$t0 = (Resolve-Path "$t0build/cartographe-evidence.exe").Path
cmake -S convergence_manager -B $l5build -G Ninja -DCMAKE_BUILD_TYPE=Release "-DCMAKE_PREFIX_PATH=$prefix" `
  "-DL5_L1_EXECUTABLE=$l1" "-DL5_L3_EXECUTABLE=$l3" "-DL5_L4_EXECUTABLE=$l4" `
  "-DL5_FREECAD_PYTHON=$freecad" "-DL5_T0_VALIDATOR=$t0"
cmake --build $l5build --parallel 4
ctest --test-dir $l5build --output-on-failure
```

```powershell
$run = '.runtime/l5-' + (Get-Date -Format yyyyMMdd-HHmmssfff)
$l5args = @('--output', $run, '--l1', $l1, '--l3', $l3, '--l4', $l4,
  '--python', $python, '--freecad-python', $freecad)
& "$l5build/convergence_core.exe" @l5args --steps 8
& "$l5build/convergence_core.exe" @l5args
& $t0 validate $run .
```

Le code `4` indique une pause. Reprendre avec les mêmes chemins, entrées et
binaires. Conserver l’ensemble du dossier de campagne, y compris
`authority/`, `attempts/`, `investigations/` et `consolidations/`. Chaque
opération réservée sans reçu peut être reprise dans un dossier neuf
selon le budget. Un changement d’entrée ou d’outil demande un nouveau dossier.
Les codes `0`, `3` et `2` correspondent respectivement à `L5_PASS`,
`L5_CONDITIONAL` et `L5_FAIL`. Le code `1` indique une erreur de configuration,
d’intégrité ou de publication. Vérifier le manifeste T0 terminal avant de
consommer un résultat CLI.

La [configuration](fixtures/campaign.json) fixe les budgets, les hypothèses,
les alternatives criblées par L3, l’ordre des portefeuilles, les exigences
de couverture et les objectifs dans l’ordre d’arbitrage. Déclarer les
corrections locales avant les familles d’alternatives du même problème.
Les affectations
`route:<liaison>` référencent le catalogue natif. Les clés d’équipements,
plaques, cordons, connecteurs et brochages peuvent entrer dans le contrôle
de fusion. Leur mise en œuvre exige une capacité native et un contrôle
indépendant correspondants. Un portefeuille est construit avec les seules
affectations de ses membres, appliquées au modèle de base. Le résultat
`campaign.json` désigne au plus un fichier consolidé. `selection.json` conserve
les choix, les rejets, les preuves L4 et les objectifs comparés.

L’API C++ est déclarée dans [Campaign.hpp](src/Campaign.hpp). Elle reçoit une
configuration, un manifeste et un `Backend` isolant l’inventaire, L1, L3,
la construction et L4. Le backend reçoit un dossier neuf par opération.
Il renvoie le chemin relatif au dossier de campagne, l’empreinte du natif
construit et les observations structurées. La CLI publie ensuite les
artefacts T0 et leurs empreintes. Voir le
[périmètre validé](../docs/VALIDATION_QUALIFICATION.md#moteur-electromecanique-v2-l5).

<a id="preflight-go3a--go3b"></a>
## Préflight GO3A / GO3B

Depuis la racine, avec les 180 fichiers du manifeste historique présents,
rejouer avec des dossiers distincts sous `.runtime/`. Le parcours peut être
compilé et testé sans lancer FreeCAD.

```powershell
cmake -S convergence_manager -B .runtime/v21-gate-build -G Ninja -DL5_V21_GO3A_TEST=ON
cmake --build .runtime/v21-gate-build
ctest --test-dir .runtime/v21-gate-build --output-on-failure
$core = '.runtime/v21-gate-build/convergence_core.exe'
& $core preflight --mode historical --output .runtime/v21-history
& $core preflight --mode explore --output .runtime/v21-explore --steps 2
& $core preflight --mode explore --output .runtime/v21-explore
& $core preflight --mode final --output .runtime/v21-final
```

Lire `preflight.json` dans chaque dossier. Les codes sont `0` pour un plan
autorisé, `2` pour un refus, `4` pour une pause et `1` pour une erreur
d’entrée ou de publication. `--plan` sélectionne une autre demande
d’exploration. `--receipt` accepte un reçu de réception pour vérifier son
rattachement à L4. Le préflight ordonne la préparation d’essais et la
commande `run` exécute la campagne L5 historique.

<a id="autorites-cartographe-v3-a3"></a>
## Autorités cartographe V3-A.3

Le dossier `v3.a3.operation_admission/1` associe chaque occurrence et
opération à ses préconditions. L’entrée actuelle accepte les demandes
`v3.admission_scope/1` et, pour la construction, les plans
`v3.mutation_plan/1` dans les périmètres scellés. L’analyse d’impact
du cartographe conserve sa voie en lecture seule. Le dossier A.3
soumis comme demande retourne `CONTRACT_VERSION_UNSUPPORTED` et ses
références déclarées dans une demande de mutation du cartographe
retournent `CARTOGRAPHER_AUTHORITIES_UNRESOLVED`.

Une future admission requiert un reçu indépendant. Il liera l’émetteur
et sa signature, la provenance et les empreintes des pièces, le lot et
la révision applicables, la version d’autorité, le sceau géométrique et
l’identifiant de la capacité à une occurrence et une opération. La
preuve contiendra les objets autorisés, les bornes dans leurs repères,
les contrôles et seuils applicables, la copie privée, la réouverture,
le rollback et le reçu T0. Le constructeur et le validateur vérifieront
indépendamment leur périmètre et refuseront une provenance, un objet,
une capacité ou un sceau divergents. Cette consommation est **Planifié**.

La recette de non-escalade utilise le binaire V3-I et une fermeture
privée scellée. Elle soumet le dossier A.3, sa variante avec auto-autorisation
et toutes les occurrences de sa matrice. [Recette A.3](../docs/verification/v3/a3/REPORT.md)
