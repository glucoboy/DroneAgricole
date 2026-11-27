# Rejeu et passation V3-INT.3

Le SHA à reconstruire figure dans [acceptance.json](acceptance.json). Les
généalogies et divergences entre sources figurent dans
[merge_manifest.json](merge_manifest.json). Le verdict et les limites
d'interprétation sont tenus dans [DOC-VAL](../../../../VALIDATION_QUALIFICATION.md#cartographe-v3-int3).

## Recompiler depuis une copie neuve

Depuis la racine d'un clone Windows amd64 disposant du même FreeCAD avec
Cables et de MSYS2 UCRT64, ouvrir PowerShell 7.4 ou supérieur et exécuter les commandes
suivantes. La redirection conserve les octets de la recette publiée. Utiliser des dossiers privés neufs et l'option Qt offscreen.

```powershell
git fetch origin refs/heads/codex/v3-int3-integration
$published = (git rev-parse FETCH_HEAD).Trim()
$proof = 'docs/verification/v3/int3/integration'
$tested = (git show "${published}:$proof/acceptance.json" | ConvertFrom-Json).tested_commit
$recipe = Join-Path (Get-Location) '.runtime/replay-int3-builds.py'
New-Item -ItemType Directory -Force .runtime | Out-Null
git show "${published}:$proof/recipes/replay_builds.py" > $recipe
git worktree add --detach .runtime/int3-review $tested
Set-Location .runtime/int3-review
New-Item -ItemType Directory -Force .runtime/b | Out-Null
& 'C:/msys64/ucrt64/bin/python.exe' -B $recipe
```

Le pilote compile les six configurations avec les options C++17
explicites. Le premier CTest L4 du pilote enregistre les cas exercés sans interpréteur
natif. Exécuter ensuite L4 complet avec la configuration FreeCAD. Le
reçu [regressions.json](regressions.json) distingue les deux séries.

```powershell
$env:Path = 'C:/msys64/ucrt64/bin;' + $env:Path
$env:QT_QPA_PLATFORM = 'offscreen'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:ELECTROMECHANICAL_FREECAD_PYTHON = 'C:/Program Files/FreeCAD 1.1/bin/python.exe'
$python = 'C:/msys64/ucrt64/bin/python.exe'
$freecad = $env:ELECTROMECHANICAL_FREECAD_PYTHON
$openssl = 'C:/msys64/ucrt64/bin/openssl.exe'
$b = (Resolve-Path .runtime/b).Path
ctest --test-dir "$b/l4" --no-tests=error --output-on-failure --output-junit "$b/logs/ctest-l4-native.xml" -V
```

Les commandes exécutées, leurs horaires et les SHA-256 des binaires,
fichiers compile_commands.json, journaux et JUnit sont dans
[builds.json](builds.json) et [regressions.json](regressions.json).
Les binaires, fermetures générées et fichiers détaillés de compilation
sont archivés dans .runtime.

## Campagnes synthétiques et références

Effectuer le relevé before des références protégées avec la
[recette de rejeu scellé](#rejeu-scelle) avant les campagnes.

```powershell
$options = @(
    '--core', "$b/l5/convergence_core.exe", '--l3', "$b/l3/architecture_decision_core.exe",
    '--t0', "$b/t0/cartographe-evidence.exe", '--freecad', $freecad,
    '--python', $python, '--output', '.runtime/int3-c3')
$runner = 'convergence_manager/tests/replay_v3_c3.py'
& $python -B $runner @options --phase T1
& $python -B $runner @options --phase T3
& $python -B $runner @options --phase T4
# Après le gel T1, l’évaluateur fournit $entree et $sha depuis un dossier privé hors campagne.
& $python -B $runner @options --phase T2 --perturbation $entree --perturbation-sha256 $sha

$a6 = 'convergence_manager/tests/test_v3_a6_transactions.py'
$l5 = "$b/l5/convergence_core.exe"
& $python -B $a6 --phase positive --core $l5 --openssl $openssl --output .runtime/review-a6-positive
& $python -B $a6 --phase adversarial --core $l5 --no-crypto "$b/l5-no-crypto/convergence_core.exe" --openssl $openssl --output .runtime/review-a6-adversarial
& $python -B $a6 --phase faults --core "$b/l5-faults/convergence_core.exe" --openssl $openssl --output .runtime/review-a6-faults
```

L'évaluateur T2 part du T2-HANDOFF.json créé après T1. Il choisit un
obstacle volumique, le lie aux trois empreintes et vérifie l'intersection
sur une copie privée de la fermeture. Effectuer la contre-mesure après
T2 avec le validateur natif sur la racine sauvegardée. Les commandes
et les résultats de chaque phase sont dans [native_c3.json](native_c3.json).
Les 32 refus A.6 incluent un lien physique et une jonction jetables sous
.runtime. Utiliser le droit Windows à créer ces deux témoins. Les liens,
les données de confiance de test et les copies natives restent dans cette
zone privée. Les détails sont dans [native_a6.json](native_a6.json).

Pour lancer le test intervoies, garder la copie testée propre et choisir
un plan v4 dont la transaction a passé la validation. Fixer le chemin
vers son dossier candidat dans $candidateDir. Les arguments du rejeu
intégré figurent dans [adversarial.json](adversarial.json).

```powershell
git show "${published}:convergence_manager/tests/test_v3_int3_a6_boundaries.py" > .runtime/test_v3_int3_a6_boundaries.py
& $python -B .runtime/test_v3_int3_a6_boundaries.py --core $l5 --openssl $openssl `
  --freecad $freecad --t0 "$b/t0/cartographe-evidence.exe" `
  --c3-plan "$candidateDir/proposal.json" --c3-transaction "$candidateDir/construction/transaction" `
  --output .runtime/review-int3-boundaries --tested-commit $tested
```

Rejouer C.2 T1/T2/T3 et A.5 selon les [recettes INT.2.1](../../int21/README.md)
et le [protocole C.2](../../c2/REPORT.md). Le T2 C.2 utilise son propre
gel et une restriction après T1. Les entrées C.2 et C.3 de la campagne
publiée sont liées à leurs gels respectifs. [C.2 T2](inputs/c2-t2-perturbation.json) ·
[C.3 T2](inputs/c3-t2-perturbation.json)

Les entrées historiques du test scellé sont épinglées par leurs empreintes.
Rejouer
[tools/replay_sealed_test.py](../../../../../tools/replay_sealed_test.py)
sur des copies jetables, avec les mêmes sources L1 et L2 que dans
[reference_integrity.json](reference_integrity.json). La matrice
[boundary_matrix.json](boundary_matrix.json) rattache les contrats aux
preuves et aux états attendus.

<a id="rejeu-scelle"></a>
### Rejeu scellé INT.2.1 et contrôles C.2/A.5

Le rejeu INT.3 utilise les recettes ci-dessous dans le worktree neuf.
Avant les campagnes natives, prendre le relevé before. Après les campagnes,
prendre le relevé after. Le dossier parent du worktree sous .runtime
doit contenir la source historique V3-D épinglée, les deux caches de
référence et la fiche F16 hors Git indiqués dans la recette INT.2.1.
Le contrôle vérifie leurs empreintes avant utilisation. Les chemins
du poste dans les reçus sont des références aux sorties de l’exécution.

```powershell
New-Item -ItemType Directory -Force .runtime/r/logs | Out-Null
git show "${published}:$proof/recipes/guards.ps1" > .runtime/r/guards.ps1
git show "${published}:$proof/recipes/replay_regressions.py" > .runtime/r/regressions.py
git show "${published}:$proof/recipes/review_c3.py" > .runtime/r/review_c3.py
& $python -B .runtime/r/regressions.py before
& .runtime/r/guards.ps1 -Phase Sealed
& .runtime/r/guards.ps1 -Phase T1
# Après clôture T1, l’évaluateur C.2 fournit $restriction dans .runtime.
& .runtime/r/guards.ps1 -Phase T2 -Perturbation $restriction
& .runtime/r/guards.ps1 -Phase T3
foreach ($phase in 'Boundaries', 'Collect', 'A5') { & .runtime/r/guards.ps1 -Phase $phase }
# Une fois l’ensemble des campagnes terminé.
& $python -B .runtime/r/regressions.py after
```

Les arguments de la contre-mesure C.3 indépendante sont décrits par
.runtime/r/review_c3.py --help. La recette crée ses propres copies XLink,
contrôle l’intersection hypothétique sur T1 puis le solide enregistré
sur T2. Les deux mesures sont reliées au reçu du nouvel obstacle.

## Passation au prompt 02 de la revue indépendante

La commande de reconstruction ci-dessus crée une nouvelle copie du SHA
testé. Le réviseur construit ses propres binaires et vérifie leur identité,
relit les deux merges et choisit un nouvel exercice de frontières
d'autorité. Donner la priorité à un effet A.6 dont la portée Workholding
ne correspond plus au profil ou à la fermeture, puis à une demande
physique, avec les compteurs, le journal et les sources mesurés avant et
après. Examiner ensuite une contre-mesure native sur sa propre copie
privée. Le résultat doit présenter une mesure d'arcs et de solides C.3
ou la géométrie de l'appui A.6, la fermeture réellement rouverte et le
contrôle T0.

Vérifier la séparation des champs spatiaux et signés dans les jobs,
l'ordre des contrôles avant ouverture FreeCAD, le deuxième contrôle
d'autorité avant commit et la non-réutilisation d'un identifiant après
quarantaine ou récupération d'un reçu. La panne de publication
A.6 de l’étape 1 retrouve le reçu authentifié et les preuves dans
le journal et refuse le rejeu. La restitution exacte des octets
d'admission.json dans un nouveau dossier reste à éprouver. Les résultats de l'étape 1
servent de comparateurs. Le réviseur produit ses propres entrées,
contre-exemples et mesures puis indique les écarts et sa conclusion.
