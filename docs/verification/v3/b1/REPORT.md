# Rejeu et preuves V3 B.1

Le [reçu d’acceptation](acceptance.json) fixe les verdicts, la révision de
code et les empreintes. La [matrice](capabilities.json) relie les opérateurs
aux commandes, aux plans et aux résultats. Le
[premier verdict V3-B](../b/acceptance.json) est conservé à son empreinte
historique. La branche B.1 part de l’admission A.1 `2b83b176b19136b57888b670b3e816c2f0b46bd0`.

## Portée des mesures

| Essai | Résultat |
|---|---|
| B1-1 · Banc historique C4 | L5 rejoue la translation +Y de 12 mm, les deux volumes de service et le cheminement. Les quatre conducteurs et huit contacts appariés passent. Le recoupement câble/obstacle de la référence est levé sur le candidat rouvert. |
| B1-2 · Deux poses sur le second banc | La pose globale `[78, 42, 7]` mm à 135° et la pose parent `[12, -3, 2]` mm à −30° sont soumises au même binaire. La seconde correspond à `[78, 45, 8]` mm et 60° dans la racine. La pose, le solide et la définition externe de l’occurrence sœur sont préservés. |
| B1-3 · Transactions composées | Les deux plans reconstruisent le `WireFlex` et son `Cable`, déplacent la platine et créent une platine percée. Les surfaces d’appui mesurent 56,00 et 62,23 mm². Les goujons, l’accès, la continuité et l’absence d’interférence interdite sont contrôlés sur les géométries rouvertes. |
| B1-4 · Injections | La collision, le rayon de 3,5 mm pour un seuil de 5 mm et l’appui décalé de 0,3 mm produisent des candidats mesurés et rejetés. Les points dupliqués déclenchent le rollback après une première mutation. Le journal de l’interruption montre une publication absente, puis une reprise dans une nouvelle copie. Les gardes de version, provenance, repère, brochage, cache, portée, chemins et empreintes ont leurs reçus. |
| B1-5 · Cartographe | Le rejeu V3-A en lecture seule retrouve 137 documents et 2 772 poses. Les 142 fichiers sources concordent bit à bit. Les mutations du cartographe restent `NOT_RUN`. L’admission de conception reste `NO_GO` et la réception physique `NOT_RUN`. |

Le second banc reprend les terminaisons numériques C4 et ajoute une
structure d’assemblage avec définition partagée, parent tourné et
supports. Les rayons sont mesurés sur des trajectoires nominales
analytiques. Le périmètre géométrique couvre les placements rigides
et les liaisons éditables du document racine. Les charges, vibrations,
l’usure et les états dynamiques du matériel restent **À valider**. Les
deux extensions ont un contrat et renvoient `UNSUPPORTED`. Les profils
ne fournissent ni variante de connecteur documentée ni jonction à instancier.

Pour `CHANGE_CONNECTOR_VARIANT`, les empreintes doivent rattacher la fiche,
l’embase, le brochage et les repères indépendants à la variante fournisseur
autorisée. La réception exige l’accouplement, la continuité et le contrôle
des incompatibilités, dont la clé et le brochage. J2/J3 du BMS restent
**À valider**.

Pour `CHANGE_INTERFACE_TOPOLOGY`, la liste ordonnée d’éditions décrit
les jonctions, déports et segments et nomme leurs extrémités. Une
admission future devra vérifier la conservation des nets, des NC et des
domaines isolés, la compatibilité des terminaisons et la fermeture
d’impact de la composition. Les empreintes du plan identifient les
preuves, dont la conformité dépendra des mesures après réouverture.

## Compilation et rejeu

Depuis la racine sous Windows amd64. Les chemins L1/L3/L4 et T0 ci-dessous
correspondent à l’environnement local du [rejeu A.1](../a1/REPORT.md).
Utiliser des exécutables reconstruits avec les recettes de ce rejeu si les
binaires locaux ont été supprimés. Les bancs scellés sont versionnés.

```powershell
$env:Path = 'C:/msys64/ucrt64/bin;' + $env:Path
$repo = (Get-Location).Path
$build = "$repo/.runtime/v3-b1/final-build"
$freecad = 'C:/Program Files/FreeCAD 1.1/bin/python.exe'
$t0 = "$repo/.runtime/v3-a-regressions/build-t0/cartographe-evidence.exe"
cmake -S convergence_manager -B $build -G Ninja -DCMAKE_BUILD_TYPE=Release `
  -DCMAKE_CXX_STANDARD=17 -DCMAKE_CXX_STANDARD_REQUIRED=ON `
  "-DL5_FREECAD_PYTHON=$freecad" "-DL5_T0_VALIDATOR=$t0" `
  "-DL5_L1_EXECUTABLE=$repo/.runtime/v3-a-regressions/build-l1-l3/research/technical_research_core.exe" `
  "-DL5_L3_EXECUTABLE=$repo/.runtime/v3-a-regressions/build-l1-l3/architecture_decision_core.exe" `
  "-DL5_L4_EXECUTABLE=$repo/.runtime/v3-a-regressions/build-l4/validation_core.exe"
cmake --build $build --parallel 4
ctest --test-dir $build -R '^(l5_|v3_graph_contract|l2_interconnection)' --output-on-failure

$run = ".runtime/v3-b1/replay-$([Guid]::NewGuid().ToString('N'))"
python -B convergence_manager/tests/replay_v3_b1.py `
  --core "$build/convergence_core.exe" --freecad $freecad --t0 $t0 `
  --profile docs/electromechanical_v3/bench_b1_c4/profile.json `
  --profile docs/electromechanical_v3/bench_b1_workholding/profile.json --output $run
python -B convergence_manager/tests/test_v3_b1_boundary.py `
  --core "$build/convergence_core.exe" --freecad $freecad --t0 $t0 --output "$run-boundary"
```

Chaque cas sauvegarde la commande `convergence_core v3-build`, ses
arguments, son code de retour et le plan. `0` signifie `PASS`, `2`
`FAIL`, `3` `UNSUPPORTED`, `4` `INCONCLUSIVE` et `1` une erreur d’entrée
ou d’exécution avant résultat. En cas de `PASS`, la candidate locale se
trouve dans `output/transaction/cad/`. En cas de rejet mesuré, consulter
`candidate_state` avant d’utiliser le natif. Les échecs de construction
retiennent le journal et les reçus sans `cad/`. Les copies interrompues
restent privées dans `.attempt-*` pour diagnostic.

## Récupération des pièces et preuves

Les natifs candidats, journaux, sorties CTest et rapports complets sont
dans `.runtime/v3-b1/`. Le [manifeste](artifacts.json) permet d’identifier
les fichiers de cette exécution par chemin et SHA-256. Un rejeu recalcule
les mêmes critères et génère ses propres identifiants de processus,
dates et SHA d’archives FreeCAD. Les procédures Q1/Q2/Q3, les oracles
et le montage du témoin L2 byte-exact restent décrits par A.1. Les
[régressions exécutées](regressions.json) indiquent les chemins, les
codes et les preuves de cette passe.

Le lot final passe les neuf tests CTest sélectionnés et les sept preuves
T0 sont de nouveau valides à leur emplacement publié. Le rejeu L2 actif
retrouve l’écart d’empreinte historique LF/CRLF. Les sept scénarios de
rapprochement passent sur la copie privée scellée en CRLF.

```powershell
git diff --stat 2b83b176b19136b57888b670b3e816c2f0b46bd0 HEAD
git diff --name-status 2b83b176b19136b57888b670b3e816c2f0b46bd0 HEAD
```

Pour V3-C, les quatre opérateurs sont disponibles dans le périmètre de
plans scellés vérifié par L5. Un nouveau modèle ou de nouvelles actions
demandent leur propre profil, vérification de l’autorité et fermeture
d’impact. Les mesures B.2 restent historiques. Aucune exécution V3-C,
V3-D ni GO3A/GO3B/GO4 n’est incluse dans les résultats B.1.
