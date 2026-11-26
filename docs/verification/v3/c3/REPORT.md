# Preuves V3-C.3 sur banc synthétique

`V3_C3_CONDITIONAL` sur le commit source
`4600062ba7c277352c5c5914bce99782aead2f63`. T1, T2 et T4
satisfont leurs critères. T3 a épuisé son budget sans candidate admissible.

| Phase | Propositions | Constructions | Contre-validations | Admissibles | Résultat |
|---|---:|---:|---:|---:|---|
| T1 | 64 | 12 | 8 | 8 | Deux faisceaux vérifiés, `cordon` à 5,94 mm du plan nominal |
| T2 | 64 | 12 | 9 | 9 | Trajet de `cordon` reconstruit, excursion de 9,24 mm |
| T3 | 64 | 12 | 0 | 0 | `NO_FEASIBLE_CANDIDATE_FOUND_WITHIN_BUDGET` |
| T4 | 0 | 0 | 0 | 0 | `INCONCLUSIVE` après épuisement du budget d’admission |

L’évaluateur indépendant et le rejeu mesurent la même intersection de
16,573 mm³ avec `cordon` en T1. La candidate T2 retrouve un dégagement
de 1,49 mm pour `cordon` et de 9,33 mm pour `cordon-b`. Les deux
volumes d’intersection sont nuls sur la géométrie rouverte. La pose
`[101.5, 5, 0]` mm et l’appui `plate-b` sont identiques aux deux
phases. Le trajet de `cordon` passe de 76,210 à 78,555 mm et retrouve
le même rayon minimal de 5 mm. `cordon-b` reste à 75,844 mm et à
7 mm de rayon minimal. L’appui mesure 272 mm². Le front T1 oppose
par exemple un gain de longueur de 2,922 mm à une perte de dégagement
inter-faisceaux de 0,00715 mm, qui change d’un pas de comparaison de
0,01 mm dans le classement. [Mesures](native_delta.json) ·
[Collision indépendante](external_perturbation_receipt.json) ·
[Classement](pareto.json)

T3 exerce une autre hiérarchie XLink et un obstacle différent. Neuf
constructions rencontrent l’obstacle détecté au criblage. Les trois
autres ont un dernier arc qui sort du polycorridor sur 2,330 à
2,939 mm alors que les segments proposés restent dans les boîtes.
Le diagnostic OCCT confirme le défaut au passage entre la boîte
volumique et la bande nominale. La vérification native a refusé les
douze candidates. La correction à éprouver sur une autre itération
consiste à tester les arcs dans l’union des boîtes avant construction,
à générer un retour tangent plus tôt si nécessaire et à réserver du
budget aux variantes sans alerte d’obstacle. [Diagnostic](generalization.json)

Les suites L3 (5/5), L5 (12/12), L4 (7/7) et T0 (2/2) passent.
Les 11 cas adversariaux C.3, les 50 cas A.5 et les contrôles
d’intégrité XLink passent. C.2 donne 3, 3 et 2 candidates admissibles
en T1/T2/T3 sur les mêmes exécutables, avec rejeu du vecteur historique
réindexé en T2. [Régressions](regressions.json) · [Cas adversariaux](adversarial.json)

## Rejeu

Compiler L3, L5 et T0 depuis un checkout Windows amd64 propre du commit
source. L’environnement testé utilise MSYS2 UCRT64, Qt 6.11.2, C++17 et
FreeCAD 1.1.3 avec OCCT 7.8.1 et Cables 0.3.7. Les commandes de régression
et les versions détaillées figurent dans [le reçu](regressions.json). Les
fermetures de référence sont versionnées dans
[le banc T1](../../../electromechanical_v3/bench_c3_spatial/profile.json)
et [le banc T3](../../../electromechanical_v3/bench_c3_spatial_secondary/profile.json).
Les candidates et leurs fichiers de rejeu résident sous `.runtime`.

```powershell
$env:Path = 'C:/msys64/ucrt64/bin;' + $env:Path
$env:QT_QPA_PLATFORM = 'offscreen'
$env:PYTHONUTF8 = '1'
$python = 'C:/msys64/ucrt64/bin/python.exe'
$runner = 'convergence_manager/tests/replay_v3_c3.py'
$options = @(
    '--core', '.runtime/engine/l5/convergence_core.exe',
    '--l3', '.runtime/engine/l3/architecture_decision_core.exe',
    '--t0', '.runtime/r3/t0/cartographe-evidence.exe',
    '--freecad', 'C:/Program Files/FreeCAD 1.1/bin/python.exe',
    '--python', $python, '--output', '.runtime/qual-c3'
)
& $python -B $runner @options --phase T1
& $python -B $runner @options --phase T3
& $python -B $runner @options --phase T4
# Le pilote remet $perturbation et $shaIndependante après le gel T1.
& $python -B $runner @options --phase T2 --perturbation $perturbation --perturbation-sha256 $shaIndependante
```

T2 attend un reçu indépendant émis après le gel en UTC et lié aux
empreintes du gel, de la racine native T1 et du problème T1. Le fichier
se place sous `.runtime` dans un dossier distinct de la campagne.
`T2-HANDOFF.json` indique les chemins, empreintes et champs attendus.
L’obstacle est un solide de type boîte aligné sur ROOT en millimètres.
Une nouvelle exécution de T1 produit un nouveau gel et requiert une
nouvelle entrée évaluateur.

## Portée

Les bancs autorisent une translation XY et gardent l’altitude et
l’orientation de l’équipement fixes. Les câbles explorent des corridors
XYZ avec progression longitudinale, raccords circulaires et supports
issus des familles paramétriques scellées. Le classement compare des
valeurs mesurées sur les candidates construites.

Le budget fixe 64 propositions, 12 constructions, 12 contre-validations
et 540 secondes pour l’admission. Une transaction déjà engagée peut
finaliser son reçu. Une candidate terminée après l’échéance est exclue
du classement. T4 vérifie cette règle avec un budget d’admission d’une
seconde. La réception TTL/USB, le montage et le vol restent `NOT_RUN`.
Le cartographe reste `DENY`.
