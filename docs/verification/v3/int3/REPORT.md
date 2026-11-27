# Qualification V3-INT.3

**Verdict `V3_INT3_GO`** pour la jonction C.3/A.6 sur bancs synthétiques sous Windows amd64. Le [reçu d’acceptation](acceptance.json) porte les critères et les liens d’intégrité. Le [manifeste de clôture](closure_manifest.json) identifie les révisions, les arbres et les rejeux. La [matrice des capacités](capability_matrix.json) précise le périmètre de qualification.

## Ascendance et identité du code

| Contribution | SHA Git complet |
|---|---|
| Base V3-INT.2.1 | `27144abf9841ba6502d29f2f76b15ff33092d186` |
| Tête C.3 fusionnée | `08ec9c4baba84d9486e7d1df3a356c0d35583646` |
| Merge C.3 avec la base | `6e5fd7176ddbb26f5a1df0dd368032af2a803079` |
| Tête A.6 fusionnée | `6461198f341af9e1f79aef061cb65d6fa531b283` |
| Merge A.6 et code testé par les étapes 1 et 2 | `558b40fce8a33cb97b28d98418fb258585836873` |
| Remise d’intégration et ancêtre commun de la revue | `60790ca713bd3e243b1a2581014927b5e7169ac4` |
| Revue indépendante, enfant direct de la remise | `2d0087412491695364308971d1057d89e93f1bed` |
| Merge de revue utilisé pour les rejeux de clôture | `f6dd9df52ef9d90a507284696cc6cf6d588a1c69` |

Les parents du merge C.3 sont INT.2.1 et la tête C.3. Les parents du merge A.6 sont le merge C.3 et la tête A.6. Les parents du merge de revue sont la remise d’intégration puis la revue indépendante. Le commit portant ce rapport ajoute les preuves de clôture au merge de revue. Pour identifier ce commit dans Git, utiliser `git log -1 --format=%H -- docs/verification/v3/int3/acceptance.json`. [Graphe et reçus sources](independent/git_history_review.json) · [Intégration et résolution des conflits](integration/merge_manifest.json)

Les étapes 1 et 2 désignent le même code intégré et leurs deux jeux de binaires sont rattachés à leurs propres reçus de compilation. Les arbres des sources L3/L4/L5/T0, des schémas et des bancs concordent entre ce code et le merge de revue. La remise avait ajouté le pilote de refus `test_v3_int3_a6_boundaries.py` hors build, des preuves, des attributs de préservation des octets et trois mises à jour des documents vivants. La revue ajoute ses preuves, ses pilotes de rejeu, ses entrées et une mise à jour de DOC-VAL. Les 17 supports de la remise, les 21 de la revue, les 76 blobs du merge de code et les trois reçus sources ont été authentifiés. [Reçu d’intégration](integration/acceptance.json) · [Reçu de revue](independent/independent_review.json) · [Contrôle du merge](independent/merge_integrity.json) · [Reconstruction indépendante](independent/independent_rebuild.json)

## Observations critiques

| Contrôle | Observation et preuve |
|---|---|
| C.3 T1–T4 | La revue revalide 12, 12 et 9 candidats sauvegardés pour T1 à T3. La contre-mesure des 33 natifs rouverts confirme les fronts Pareto de 5, 5 et 3 candidats et les contrôles de corridor, d’arcs, de tangence, de ports, de service et d’ancrage. T4 atteint son échéance de recherche avec `INCONCLUSIVE` et zéro candidat, résultat attendu de l’essai. La première itération C.3 conditionnelle reste traçable dans `prior_iteration`, avec le refus T3 initial et son commit de preuve. [Intégration](integration/native_c3.json) · [Contre-mesure](independent/c3_native_recheck.json) · [Historique C.3](../c3/acceptance.json) |
| Obstacle C.3 post-gel | Un évaluateur distinct publie une nouvelle boîte après le gel de T1. Elle intersecte `cordon` de 1,45152 mm³ sur T1. La fermeture T2 sauvegardée et rouverte contient le nouvel obstacle, avec un nouveau tracé de `cordon`, une nouvelle empreinte de la racine et zéro intersection pour les deux faisceaux. [Entrée indépendante](independent/inputs/c3-t2-perturbation.json) · [Réfutation et contre-mesure T2](independent/c3_native_recheck.json) |
| A.6, deux effets signés | Les deux transactions Workholding P64 atteignent `COMMITTED_PRIVATE`. Le rejeu indépendant vérifie une clé publique Ed25519 de revue et une de registre par transaction, puis l’effet mesuré après réouverture de deux copies. L’effet modifié déplace l’appui de −0,375 mm sur X et réduit sa largeur de 0,07 mm. Les vérifications L2/L4/T0 passent sur les deux modèles. [Reçu de transactions](integration/native_a6.json) · [Rejeu signé indépendant](independent/a6_signed_recheck.json) |
| A.6, refus et journal | La revue reproduit 32 refus, trois refus complémentaires et les sept scénarios de panne injectée ou de concurrence. Après interruption de publication, le reçu a été restitué octet pour octet avec un journal authentifié et la confiance préservée, après vérification de 18 artefacts. [Refus et défauts intégrés](integration/adversarial.json) · [Rejeu et reprise indépendante](independent/a6_signed_recheck.json) |
| Frontières C.3 ↔ A.6 | Sur le merge de clôture, 14/14 cas de la recette finale publiée et 14/14 cas du pilote indépendant. Les deux séries couvrent notamment le plan v4 présenté sous autorité A.6, les empreintes et la pose après signature, le refus physique, l’isolement des sorties, la révocation et la concurrence. Les cas de refus avant admission vérifient l’absence de réservation, de modification du journal et de sortie native. [Matrice de jonction](integration/boundary_matrix.json) · [Cas de revue et rejeu de la recette finale](independent/cross_boundary_adversarial.json) · [Rejeux de clôture](closure_manifest.json) |
| Régressions sur le merge de clôture | CTest L3 5/5, L4 7/7 avec FreeCAD, L5 12/12, T0 2/2 en série avec 30 s de plafond par test. L1 historique 24/24 et L2 scellé 7/7 avec deux matrices identiques sur 115 entrées. La reprise INT.2.1 et les essais C.2/A.5 figurent dans les régressions de la revue. [Régressions de revue](independent/regressions.json) · [Procès-verbaux de clôture](closure_manifest.json) |
| Empreintes et XLink | Cinq profils, cinq graphes et quinze natifs des bancs concordent. Les 142 entrées du scellé cartographe concordent sur la copie historique, dont 137 documents XLink. Trois métadonnées de checkout présentent la normalisation CRLF→LF déjà documentée. Les octets historiques sont rétablis sur les seules copies jetables du rejeu. [Scellés et graphe](independent/merge_integrity.json) · [Inventaire protégé](independent/reference_integrity.json) |
| Frontière physique | Zéro lot inspecté et zéro candidat cartographe. `CREATE_SUPPORT(iso)` réel refusé (`PHYSICAL_ADMISSION_NOT_CONFIGURED`). Racine de confiance de production vide, aucune réception physique, aucune construction du cartographe. [Registre physique A.6](../a6/physical_readiness.json) |

La référence `integration/adversarial.json#/recipes/3` associe l’empreinte d’un essai intermédiaire au chemin de la recette finale. Elle a été écartée comme preuve de cet essai. La recette finale correspond à l’empreinte directe publiée par le reçu d’intégration et a été rejouée indépendamment puis sur le merge de clôture. [Disposition de l’écart](independent/merge_integrity.json) · [Rejeu de la recette authentifiée](independent/cross_boundary_adversarial.json)

## Reproduction depuis le merge de revue

Depuis la racine d’une copie de travail dédiée au merge de revue, prévoir des répertoires privés neufs. Le poste de clôture utilise MSYS2 UCRT64, GCC 16.2.0 en C++17 sans extensions, Qt 6.11.2, OpenSSL 3.6.4, FreeCAD 1.1.3, OCCT 7.8.1 et Cables 0.3.7. Le pilote configure six builds, dont les variantes sans OpenSSL et avec injection de pannes. Il lance T0 avant la compilation parallèle. L4 requiert `ELECTROMECHANICAL_FREECAD_PYTHON` pour exercer le cas natif. Les journaux CTest et les dossiers produits restent privés.

```powershell
$env:Path = 'C:/msys64/ucrt64/bin;' + $env:Path
$env:QT_QPA_PLATFORM = 'offscreen'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONDONTWRITEBYTECODE = '1'
$python = 'C:/msys64/ucrt64/bin/python.exe'
$freecad = 'C:/Program Files/FreeCAD 1.1/bin/python.exe'
$openssl = 'C:/msys64/ucrt64/bin/openssl.exe'
$env:ELECTROMECHANICAL_FREECAD_PYTHON = $freecad
$proof = 'docs/verification/v3/int3'
$build = '.runtime/close-b'
$run = '.runtime/close-r'
$guards = '.runtime/close-g'
New-Item -ItemType Directory $build,$run,"$run/logs","$run/tmp",$guards | Out-Null
Copy-Item "$proof/integration/recipes/replay_regressions.py" "$run/regressions.py"
& $python -B "$run/regressions.py" before
$driver = Get-Content "$proof/integration/recipes/replay_builds.py" -Raw
$driver.Replace('".runtime/b"', '".runtime/close-b"') |
  Set-Content -Encoding utf8NoBOM "$build/replay_builds.py"
& $python -B "$build/replay_builds.py"
& $python -B "$run/regressions.py" sealed `
  "$build/l3/research/technical_research_core.exe" `
  "$build/l3/interconnection/interconnection_core.exe"
```

Le rejeu scellé utilise les copies historiques `.runtime/v3-b2/historical/l2-sealed` et `.runtime/v3-a/native-20261118-065605213/staged` à la racine du dépôt principal. Le rejeu des refus prend le plan et la fermeture C.3 T1 archivés sous `.runtime/int3-c3/t1/T1/candidates/v3-c-001`, dont les octets ont été authentifiés. Pour régénérer un témoin admissible du même code dans un nouveau dossier privé, suivre la [recette C.3 d’intégration](integration/REPORT.md#campagnes-synthétiques-et-références). Pour répéter les mesures signées A.6 et l’évaluation indépendante post-gel, suivre le [protocole de revue](independent/REPORT.md#reproduction). Toute nouvelle campagne T2 requiert un obstacle émis après son propre gel.

```powershell
$code = '558b40fce8a33cb97b28d98418fb258585836873'
$tip = 'f6dd9df52ef9d90a507284696cc6cf6d588a1c69'
$candidate = '.runtime/int3-c3/t1/T1/candidates/v3-c-001'
$argsCommon = @('--core', "$build/l5/convergence_core.exe", '--openssl', $openssl,
  '--freecad', $freecad, '--t0', "$build/t0/cartographe-evidence.exe",
  '--c3-plan', "$candidate/proposal.json",
  '--c3-transaction', "$candidate/construction/transaction")
& $python -B convergence_manager/tests/test_v3_int3_a6_boundaries.py @argsCommon `
  --output "$guards/published" --tested-commit $tip
& $python -B "$proof/independent/recipes/recheck_boundaries.py" @argsCommon `
  --fault-core "$build/l5-faults/convergence_core.exe" `
  --output "$guards/independent-r2" --tested-commit $code
& $python -B "$run/regressions.py" after
```

Le pilote indépendant nécessite le droit Windows de créer une jonction NTFS dans son dossier privé. La première tentative de clôture s’est arrêtée sur la création du témoin `mklink /j`. Le nouveau dossier privé a servi au rejeu avec ce droit. Le manifeste conserve les traces des deux exécutions. [Procès-verbaux de clôture](closure_manifest.json)

## Périmètre et suites

Les deux suites T0 utilisent des données de test des contrats locaux, dont les états terminaux SITL. La génération historique du modèle cartographe a reproduit le défaut `stale CAD manifest`, classé hors des critères des bancs INT.3. Les essais Gazebo/PX4 complets, le vol, la réception physique, la cible arm64, la coupure électrique réelle, la restauration complète du magasin de confiance et l’ancrage monotone externe restent **À valider**. La reprise du reçu A.6 observée porte sur la perte du reçu externe avec journal et confiance préservés.

La porte cartographe reste `cartographer_mutation=DENY`, `cartographer_candidate_count=0`, `physical_reception=NOT_RUN` et `production_trust_pin=EMPTY`. D.1 reste conditionné par les relevés du lot réel, le dossier d’appui applicable, une revue habilitée et une autorisation distincte. C.4 et A.7 dépendent d’une nouvelle décision de planning. [Matrice des capacités et des limites](capability_matrix.json) · [Conditions de réception](../a6/physical_readiness.json) · [DOC-VAL](../../../VALIDATION_QUALIFICATION.md#cartographe-v3-int3)
