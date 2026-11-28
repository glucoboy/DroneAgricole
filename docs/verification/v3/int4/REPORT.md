# Intégration V3-INT.4

**V3_INT4_GO** sur Windows amd64 pour le commit de code `48245a446b949e92995e2aeb6a9dd2fdf7b55017`. Le [reçu d’acceptation](acceptance.json) donne les critères et les limites. Le [manifeste Git](merge_manifest.json) distingue les têtes fusionnées des commits testés par les lots d’entrée et identifie les deux parents de chacune des trois fusions.

## Résolution des divergences

| Chemin | Notre changement | Leur changement | Résolution | Vérification |
|---|---|---|---|---|
| `.gitattributes` | Préservation INT.3 et règle LF pour les pilotes C.4 | Règles LF A.7 et préservation octet pour octet des lacunes | Git a combiné les deux ajouts avec les règles antérieures. | `git check-attr` et empreintes des preuves. Le CSV A.5 garde son blob LF et sa copie Windows CRLF. |
| DOC-VAL | Qualification historique C.4 et registre INT.3 | Section A.7, puis section SIM.1 et son entrée de journal | Les deux résolutions conservent les contributions et leurs liens. | Ancres distinctes et présence des trois lots dans le journal. |
| DOC-SW | Pose et validateur C.4 | Réception A.7 en lecture seule, puis export SIM.1 sur copie | Les deux résolutions conservent les entrées du journal. | Sections et résultats des trois capacités. |
| DOC-MEC | Deux bancs C.4 | Collecte d’appui pour P64 et P66 | Les rubriques et les deux entrées de journal sont conservées. | Ancres et arbres de référence. |
| CMake | L3, L4, L5 et T0 de la base | CLI A.7 avec matrice épinglée, exporteur et tests SIM.1 | Les ajouts touchent deux fichiers CMake distincts. | Compilation neuve et commandes effectives. |
| Natifs et producteurs | Natifs cartographe, XLinks, simulation historique et anciens bancs | Deux bancs C.4 et producteurs SIM.1 | Les nouveaux bancs et producteurs gardent les blobs source. | Objets Git, fermeture XLink, inventaire et empreintes avant et après. |

## Résultats du rejeu

| Exigence ou frontière | Rejeu du code gelé | Preuve |
|---|---|---|
| Contrats et régressions scellées | CTest L3 5/5, L4 7/7, L5 13/13 avec A.7, T0 2/2 à 30 s. L1 24/24 et L2 7/7, 115 entrées identiques et deux sorties L2 identiques octet par octet. | [Compilations, CTest et copies L1/L2](regressions.json) |
| Pose, deux faisceaux, appui et services | T1, T2 et T3 finalisés avec contre-mesures. Le nouvel obstacle T2 recoupe le deuxième câble T1 de 0,303056 mm³. T4 finalisé à budget court avec zéro admission. 17 cas C.4 contradictoires. | [Rejeux C.4](native_replays.json) |
| Réception documentaire et construction | 27 contrôles par porteur P64/P66, deux reçus recalculés, A.7 25/25, A.5 50/50, deux effets A.6 signés et remesurés, deux séries INT.3 de 14/14 et 13 nouveaux cas croisés. | [A.5, A.6, A.7 et jonctions](boundary_checks.json) |
| Export hors ligne et provenance | 5/5 tests et génération native, 156 sources scellées, 18 produits, 361 occurrences, 21 boîtes et quatre rotors. Refus des entrées absentes ou modifiées, de l’historique périmé et du mode physique. | [SIM.1](sim1_snapshot_checks.json) |
| Références et contre-mesures | 791 natifs cartographe suivis, fermeture historique de 137 XLinks et 13 originaux fabricant contrôlés. La revue Git indépendante n’a relevé aucun écart critique. | [Scellés](reference_integrity.json) · [Revue indépendante](independent_review.json) |

La chaîne signée A.6 couvre le Workholding P64 synthétique. La réception documentaire donne zéro lot inspecté, `production_trust_pin=EMPTY`, `cartographer_mutation=DENY` et le refus de `CREATE_SUPPORT(iso)` réel. La réception physique, Gazebo, PX4, le vol et arm64 restent **À valider** dans leurs périmètres respectifs.

## Reproduction

Créer un checkout propre du commit de code. Le poste utilise Windows amd64, GCC 16.2.0, Qt 6.11.2, CMake/CTest 4.4.2, Python UCRT64 3.14.7, OpenSSL 3.6.4, FreeCAD 1.1.3, OCCT 7.8.1 et Cables 0.3.7. Ajouter UCRT64 au chemin des exécutables, activer `QT_QPA_PLATFORM=offscreen` et `PYTHONUTF8=1`, puis définir `ELECTROMECHANICAL_FREECAD_PYTHON` au Python de la distribution FreeCAD. Utiliser des répertoires neufs.

1. Utiliser la [recette de construction INT.3](../int3/integration/recipes/replay_builds.py) avec `-DCMAKE_CXX_STANDARD=17`, `-DCMAKE_CXX_STANDARD_REQUIRED=ON`, `-DCMAKE_CXX_EXTENSIONS=OFF`, `-DCMAKE_CXX_FLAGS=-std=c++17` et `-DCMAKE_EXPORT_COMPILE_COMMANDS=ON`. Construire la cible `cartographe-evidence` de `simulation` dans un sous-dossier `.runtime` du checkout. Épingler ce binaire pour L5. GCC sans option annonce `202002L`. La sonde stricte annonce `201703L` et définit `__STRICT_ANSI__`.
2. Utiliser `ctest --test-dir <build-t0> --parallel 1 -R '^cartographe_(sitl_)?t0_contracts$' -V` sur un créneau isolé des compilations et campagnes FreeCAD. Les deux plafonds CMake valent 30 s. Donner à `--output-junit` un chemin absolu. Le passage final utilise `GIT_OPTIONAL_LOCKS=0`, `core.fscache=true` et `core.preloadIndex=false` avec la configuration de session décrite dans la [recette SIM.1](../sim1/README.md). Les premières tentatives T0 figurent dans [regressions.json](regressions.json).
3. Construire L3 depuis `architecture_decision_engine`, L4 depuis `validation_engine` et L5 depuis `convergence_manager`. Épingler L1/L3/L4/T0, OpenSSL et FreeCAD selon la recette INT.3, avec `L5_A5_PHYSICAL_TRUST_SHA256` vide. Construire les variantes `l5-faults` et `l5-no-crypto`. Rejouer les suites en série, avec le délai général CTest de 120 s et les plafonds individuels CMake. Pour L1/L2 et F16, utiliser le [pilote scellé](../int3/integration/recipes/replay_regressions.py) et les copies historiques indiquées dans la [clôture INT.3](../int3/REPORT.md#reproduction-depuis-le-merge-de-revue).
4. Exécuter la [recette native C.4](../c4/README.md) sur les binaires neufs. Le répertoire d’exécution et le reçu de perturbation se placent sous `.runtime` du checkout. Faire choisir le nouvel obstacle par un évaluateur distinct, après le gel de code et la passation du T1 de ce rejeu. Une autre exécution T2 demande son propre gel et une nouvelle entrée indépendante.
5. Rejouer le [pilote A.7](../../../../convergence_manager/tests/test_v3_a7_reception.py) avec `--tool` vers `cartographe_reception` et un nouveau `--output`. Le pilote lance le contrôleur distinct des reçus. Les variantes A.6, les deux pilotes INT.3 et les cas de jonction sont détaillés dans [boundary_checks.json](boundary_checks.json). La création des témoins NTFS exige les permissions Windows correspondantes.
6. Pour SIM.1, utiliser la [recette de copie privée et d’export](../sim1/README.md) dans une destination neuve alimentée par les originaux autorisés. Rejouer les cinq cas `^cartographe_model_`, vérifier le paquet et recalculer les empreintes de cette exécution. Le SDF et l’airframe servent à l’aperçu hors ligne avec propriétés physiques complètes inconnues.

Les preuves donnent les chemins et les SHA-256 des journaux sous `.runtime/int4/` et précisent les chemins privés imposés par les gardes. Les sorties volumineuses restent hors Git. Résoudre le commit de preuves avec `git log -1 --format=%H -- docs/verification/v3/int4/acceptance.json`.
