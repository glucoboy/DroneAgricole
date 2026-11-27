# Revue contradictoire V3-INT.3

La remise `60790ca713bd3e243b1a2581014927b5e7169ac4` et les deux parents du
merge de code `558b40fce8a33cb97b28d98418fb258585836873` ont été rapprochés
de GitHub. Le worktree neuf est issu de la remise. Les arbres entre les
deux SHA concordent pour les sources, les bancs et leurs données. Le test de
refus ajouté dans la remise a été rejoué séparément sur le checkout de la
remise, avec les binaires rattachés au merge de code.

La recette de refus finale correspond aux empreintes d’`acceptance.json`
et d’`adversarial.json#/boundary_replay/runtime_recipe`. Le rejeu de cette
recette finalise 14 refus. L’empreinte de l’essai intermédiaire indiquée
dans `adversarial.json#/recipes/3` ne correspond pas au fichier à son chemin
publié et a été refusée. Les preuves de cet essai intermédiaire ont été
écartées de la décision. Le manifeste du merge fournit 76 blobs vérifiés et
le reçu d’acceptation 17 supports directs vérifiés. Les références de la
remise et les observations indépendantes sont identifiées dans les reçus
de la revue. [Graphe Git](git_history_review.json) · [Intégrité du merge](merge_integrity.json)

## Résultats réexécutés

C.3 conserve respectivement 12, 12 et 9 candidats admissibles en T1, T2 et
T3. Le nouveau solide T2 intersecte `cordon` de 1,45152 mm³ sur T1. Sur la
fermeture T2 rouverte, le tracé de `cordon` et l’empreinte du natif changent.
Les deux faisceaux ont zéro intersection avec le solide sauvegardé. Les 33
réouvertures recalculent les métriques et les fronts Pareto de 5, 5 et 3 membres.
Les contrôles OCCT couvrent aussi les arcs, la tangence, les ports, le service
et les ancrages. T4 atteint l’échéance prescrite avec `INCONCLUSIVE` et zéro
candidat. [Preuve C.3](c3_native_recheck.json)

Les deux nouvelles demandes Workholding P64 ont des identifiants distincts.
Les signatures Ed25519 ont été vérifiées avec des clés publiques de revue et
de registre séparées. Les deux transactions atteignent `COMMITTED_PRIVATE`.
Sur les FCStd rouverts séparément, la modification signée déplace l’appui
de −0,375 mm en X et réduit sa largeur de 0,07 mm. Les contrôles L2/L4/T0 des
deux modèles passent. Les 32 refus de la suite et trois refus synthétiques
complémentaires produisent les résultats attendus. Les sept pannes ou
scénarios de concurrence reproduisent les états attendus. Le reçu interrompu
en publication a été restitué octet pour octet dans un dossier privé distinct
à partir du journal authentifié, après contrôle des 18 artefacts. [Preuve A.6](a6_signed_recheck.json)

Les 14 cas de jonction conçus pour cette revue couvrent le plan v4, l’option
héritée, la fermeture C.3 présentée sous une revue Workholding, la modification
de la pose et du datum après signature, le parent, la jonction et la fermeture
jetable comme sorties, la demande physique, P66, la concurrence, la révocation
et deux réemplois d’un reçu Workholding. Pour les refus avant admission,
les entrées et le journal authentifié gardent les mêmes empreintes, les
attestations sont finalisées lorsqu’un reçu est prévu et aucun espace natif
privé n’apparaît. La déduction d’absence de lancement autorisé s’appuie sur
ces observations et sur l’appel natif subordonné à la réservation dans le code.
Un concurrent obtient `AUTHORITY_STATE_BUSY` et l’autre publie une seule
transaction. La révocation avant commit laisse un état `QUARANTINED`, une
seule consommation et zéro publication. La candidate C.3 rouverte conserve
ses empreintes et la portée `BENCH_TEST_ONLY`. [Batterie de jonction](cross_boundary_adversarial.json)

| Suite | Résultat observé |
|---|---|
| CTest strict | L3 5/5, L4 7/7 avec FreeCAD, L5 12/12, T0 2/2 au plafond de 30 s. Le premier L4 sans configuration FreeCAD a enregistré un cas sauté, puis L4 natif a exercé les sept cas. Le filtre volontairement vide retourne 8. |
| INT.2.1 | L1 24/24 et L2 7/7 sur références historiques. Les deux matrices L2 concordent octet pour octet, sur 115 entrées recopiées. Le checkout brut et le témoin modifié sont refusés par contrôle d’empreinte. Le défaut XLink injecté sur copie est rejeté. |
| C.2 | T1 à T3 gardent respectivement 3, 3 et 2 candidats. Après gel et restriction indépendante, T2 passe de `plate-b` à `plate` avec une nouvelle fermeture et T0 valide. T3 emploie le second banc. Les neuf refus du contrat et onze défauts natifs donnent les résultats attendus. |
| A.5 | 50 cas du scénario de préadmission passent. La même demande signée est admise en `TEST_ONLY` avec OpenSSL et refusée en `REVIEW_NOT_CONFIGURED` sans OpenSSL, avec zéro construction dans les deux cas. |
| Génération historique du modèle cartographe | Le test seul reproduit `stale CAD manifest`. Cet écart du lot Gazebo figurait hors des critères de remise INT.3. |

Les empreintes L1/L2, les procès-verbaux de CTest et les attestations C.2/A.5
figurent dans le reçu des régressions. Les variations de fins de ligne de
trois métadonnées XLink ont été vérifiées en mémoire et les rejeux L2 ont
restauré les octets historiques uniquement sur une copie jetable. [Régressions](regressions.json)

## Reproduction

Sur Windows `amd64`, la revue utilise MSYS2 UCRT64, GCC 16.2.0, Qt 6.11.2,
OpenSSL 3.6.4, FreeCAD 1.1.3, OCCT 7.8.1 et Cables 0.3.7. Les six builds
neufs emploient C++17 sans extensions. Le build nominal et la variante
sans crypto ont les pannes injectées désactivées. Les chemins FreeCAD et T0
sont fixés à la compilation et la racine de confiance de production est vide.
Les lignes de commande, codes, binaires, caches de compilation et empreintes
des journaux sont inventoriés dans les preuves. [Build indépendant](independent_rebuild.json)

Depuis la racine du worktree de la remise, avec des sorties `.runtime`
neuves et les références historiques locales indiquées dans la recette
d’intégration, les commandes de préparation et de rejeu principales sont
les suivantes. Les commandes complètes des appels natifs, leurs options
et leurs résultats sont dans les reçus liés ci-dessus.

```powershell
$env:Path = 'C:/msys64/ucrt64/bin;' + $env:Path
$env:QT_QPA_PLATFORM = 'offscreen'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONDONTWRITEBYTECODE = '1'
$python = 'C:/msys64/ucrt64/bin/python.exe'
$fc = 'C:/Program Files/FreeCAD 1.1/bin/python.exe'
$openssl = 'C:/msys64/ucrt64/bin/openssl.exe'
$integration = 'docs/verification/v3/int3/integration'
$recipes = 'docs/verification/v3/int3/independent/recipes'
New-Item -ItemType Directory -Force .runtime/b,.runtime/r/logs,.runtime/r/tmp | Out-Null
Copy-Item -LiteralPath "$integration/recipes/guards.ps1" -Destination .runtime/r/guards.ps1
Copy-Item -LiteralPath "$integration/recipes/replay_regressions.py" -Destination .runtime/r/regressions.py
& $python -B .runtime/r/regressions.py before
& $python -B "$integration/recipes/replay_builds.py"
$env:ELECTROMECHANICAL_FREECAD_PYTHON = $fc
ctest --test-dir .runtime/b/l4 --no-tests=error --output-on-failure --output-junit "$pwd/.runtime/b/logs/ctest-l4-native.xml" -V
& .runtime/r/guards.ps1 -Phase Sealed
& $python -B .runtime/r/regressions.py f16 .runtime/b/l3/research/technical_research_core.exe
& .runtime/r/guards.ps1 -Phase T1
# Attendre une restriction C.2 calculée après le nouveau gel par un évaluateur distinct.
& .runtime/r/guards.ps1 -Phase T2 -Perturbation .runtime/c2-evaluator/perturbation.json
& .runtime/r/guards.ps1 -Phase T3
& .runtime/r/guards.ps1 -Phase Boundaries
& .runtime/r/guards.ps1 -Phase Collect
& .runtime/r/guards.ps1 -Phase A5
```

Les recettes de revue viennent de `origin/codex/v3-int3-independent-review`.
Extraire leurs octets dans le worktree de la remise à l’aide de PowerShell
7.4 ou supérieur. Le rejeu doit être exécuté sur la révision exacte de la
remise. Les commandes suivantes donnent le lanceur C.3 et sa contre-mesure.

```powershell
New-Item -ItemType Directory -Force $recipes | Out-Null
$review = 'origin/codex/v3-int3-independent-review'
foreach ($file in 'audit_merge.py','a6_review_runner.py','c3_evaluator_t2.py',
                  'c3-recheck.py','collect-c3-receipt.py','recheck_boundaries.py') {
    git show "${review}:$recipes/$file" > "$recipes/$file"
}
$c3 = 'convergence_manager/tests/replay_v3_c3.py'
$common = @('--core','.runtime/b/l5/convergence_core.exe','--l3','.runtime/b/l3/architecture_decision_core.exe',
  '--t0','.runtime/b/t0/cartographe-evidence.exe','--freecad',$fc,'--python',$python,'--output','.runtime/c3-review')
foreach ($phase in 'T1','T3','T4') { & $python -B $c3 @common --phase $phase }
# L’évaluateur distinct produit la nouvelle boîte à partir du gel T1 et de sa copie XLink.
$entry = (Resolve-Path -LiteralPath '.runtime/c3-evaluator/perturbation.json').Path
$sha = (Get-FileHash -LiteralPath $entry).Hash.ToLowerInvariant()
& $python -B $c3 @common --phase T2 --perturbation $entry --perturbation-sha256 $sha
foreach ($phase in 'T1','T2','T3','T4') {
    & $python -B "$recipes/c3-recheck.py" phase $phase .runtime/c3-review .runtime/c3-countermeasure
}
```

Le reçu C.3 contient les appels de mesure, les preuves OCCT et le classement
Pareto recalculé. Les entrées T2 archivées identifient les gels de cette revue
et la géométrie observée. Un nouveau gel exige de nouvelles entrées émises
par des évaluateurs distincts. [Protocoles C.3](c3_native_recheck.json) · [Entrée C.3](inputs/c3-t2-perturbation.json) · [Entrée C.2](inputs/c2-t2-perturbation.json)

Les quatre séquences A.6 prennent les mêmes binaires épinglés au build.
Les commandes individuelles de lancement, de signature et de mesure sont
conservées dans le reçu A.6.

```powershell
$a6 = "$recipes/a6_review_runner.py"
$a6tools = @('--root','.','--build','.runtime/b','--openssl',$openssl,'--freecad',$fc)
& $python -B $a6 positive @a6tools --work .runtime/a6-r-positive-r2
& $python -B $a6 refusals @a6tools --work .runtime/a6-r-refusals-r2
& $python -B $a6 independent-refusals @a6tools --work .runtime/a6-r-extra
& $python -B $a6 faults @a6tools --work .runtime/a6-r-faults
& $fc -I -B -X utf8 $a6 recover --root . --work .runtime/a6-r-faults/during-publication `
  --report .runtime/a6-r-recovery/recovery.json
```

Pour rejouer les frontières sur la même candidate, fournir le plan et la
transaction T1 du nouveau gel. Les deux exécutions réelles de référence sont
archivées dans le reçu de jonction. Utiliser le SHA du checkout pour la
recette publiée et le SHA du merge de code pour identifier les binaires
dans le pilote indépendant. Le témoin de jonction NTFS nécessite la
permission Windows correspondante.

```powershell
$candidate = '.runtime/c3-review/t1/T1/candidates/v3-c-004'
$tools = @('--core','.runtime/b/l5/convergence_core.exe','--openssl',$openssl,
  '--freecad',$fc,'--t0','.runtime/b/t0/cartographe-evidence.exe',
  '--c3-plan',"$candidate/proposal.json",'--c3-transaction',"$candidate/construction/transaction")
& $python -B convergence_manager/tests/test_v3_int3_a6_boundaries.py @tools `
  --output .runtime/r/published-boundaries --tested-commit 60790ca713bd3e243b1a2581014927b5e7169ac4
& $python -B docs/verification/v3/int3/independent/recipes/recheck_boundaries.py @tools `
  --fault-core .runtime/b/l5-faults/convergence_core.exe `
  --output .runtime/r/boundary-independent-r3 --tested-commit 558b40fce8a33cb97b28d98418fb258585836873
& $python -B .runtime/r/regressions.py after
```

## Portée du verdict

Les 142 entrées protégées, dont 137 documents XLink, gardent les mêmes
empreintes. L’inventaire du cartographe recense 791 documents natifs suivis
dans chaque checkout et zéro ajout. Les exports et preuves ignorés du
checkout principal portent des dates antérieures à la revue. Le checkout
principal est à la révision initiale. La revue conclut `V3_INT3_INDEPENDENT_PASS`
pour les bancs synthétiques et le merge de code précisé ci-dessus. [Intégrité des références](reference_integrity.json)

Les deux suites T0 couvrent les contrats de preuve sur ce poste. Garder le
statut **À valider** pour la réception physique, des essais Gazebo/PX4
complets, la cible `arm64`, le vol, la coupure électrique réelle et la
restauration de l’ensemble du magasin de confiance. L’ancrage monotone
externe reste non qualifié. Les premières tentatives et leurs reprises sont
distinguées dans les reçus concernés. [Verdict et empreintes](independent_review.json)
