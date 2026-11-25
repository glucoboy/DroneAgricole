# Rejouer V3-INT.2

[Acceptation](acceptance.json) · [Fusion et empreintes](merge_manifest.json) ·
[Commandes et reçus](regressions.json) · [Refus](adversarial.json) ·
[Périmètres](capability_matrix.json) ·
[DOC-VAL](../../../VALIDATION_QUALIFICATION.md#cartographe-v3-int2)

## Préparer les builds

Utiliser le commit de fusion indiqué dans `acceptance.json` avec un
checkout propre sous `.runtime` de la racine V3-D scellée. Utiliser
Windows amd64, MSYS2 UCRT64, C++17, Qt 6, Ninja et le Python de FreeCAD
1.1.3 avec OCCT 7.8.1 et Cables 0.3.7. Les versions, arguments CMake,
binaires et empreintes sont dans `regressions.json`. Transposer les
chemins locaux vers un dossier `.runtime` neuf.

Compiler L3, L4 et le validateur T0, puis L5 avec les chemins des
quatre exécutables et du Python FreeCAD attendus par CMake. Garder
`L5_A5_PHYSICAL_TRUST_SHA256` vide. Préparer un deuxième build L5 avec
`-DCMAKE_DISABLE_FIND_PACKAGE_OpenSSL=TRUE -DBUILD_TESTING=OFF`
et compiler le seul exécutable `convergence_core`.

## Vérifier les deux voies

1. Rejouer [C.2](../c2/REPORT.md), T1 puis T3, sur des copies privées avec
   les mêmes binaires et le même gel. Garder T2 historique en l’absence
   d’une nouvelle perturbation indépendante après ce gel. Pour chaque
   candidat admis par T1/T3, vérifier les empreintes du gel et les reçus
   avec `check_candidate` et `pareto_check` de
   `convergence_manager/tests/collect_v3_c2_evidence.py`. Vérifier les
   deux ports par câble, la topologie, les deux options d’appui de T1,
   la fixation engagée, zéro interférence interdite, les PID et
   identifiants de workers distincts et la revalidation T0. Le collecteur
   complet C.2 attend aussi T2.
2. Rejouer les refus C.2 et les injections natives avec la transaction
   T1 retenue. Pour le contrôle complémentaire, copier sa fermeture
   `cad` et son `candidate-job.json` dans un dossier privé neuf.
   Retirer `parts/Obstacle.FCStd` de cette copie et lancer
   `v3_verify.py --root <copie-cad> --job <copie-job> --output <reçu>`
   via le Python FreeCAD. Lire le verdict du reçu même si le processus
   retourne 0. Comparer les empreintes de la transaction originale.
3. Rejouer [A.5](../a5/REPORT.md) et
   `test_v3_a5_authority.py` avec le binaire normal. Pour isoler l’effet
   de l’absence de crypto, créer une fixture signée jetable avec
   `SigningFixtures` et `AdmissionFixture` de cette suite. Soumettre la
   même demande en premier au binaire sans OpenSSL, puis au binaire
   normal. Contrôler l’empreinte identique, `REVIEW_NOT_CONFIGURED`
   puis la préadmission `TEST_ONLY` et zéro transaction.
4. Rejouer [les régressions INT.1](../int1/REPORT.md) et
   [A.2–A.4](../a4/REPORT.md). Le témoin A.4 de refus de transaction
   attend la fermeture de test A.3 à `admission/input`, à côté de son
   dossier de sortie. Rejouer également le contrôle des sept paires
   historiques V3-D en lecture seule avec le Python FreeCAD.
5. Exécuter le CTest complet L3. Couvrir les 12 tests L5 par le rejeu
   groupé INT.1 puis le test isolé de réconciliation. Rejouer
   `l2_reconcile` sur le checkout puis les sept tests Python depuis
   la copie `.runtime/v3-b2/historical/l2-sealed` avec le même binaire
   L2 issu de L3. Rejouer aussi la suite L1 depuis la racine V3-D
   avec `TECHNICAL_RESEARCH_CORE` pointant vers le nouveau binaire.
   Garder les empreintes LF/CRLF et les codes de retour séparés. Les deux
   jeux d’octets sont nécessaires pour reproduire l’écart historique.
6. Comparer la fermeture XLink et les 142 entrées protégées avant et après
   les essais, en utilisant le reçu V3-A comme manifeste. Conserver
   les journaux, binaires et candidats sous `.runtime`. Les originaux
   et clés de test restent hors Git.

Les logs T0 conservent les essais avec la limite CTest de 30 secondes
et le résultat de `cartographe-evidence self-test-sitl` exécuté
directement. Cette commande travaille sur des fixtures de contrats.

## Recalculer le verdict

Depuis ce dossier, vérifier les quatre empreintes, puis appliquer la
règle du reçu aux contrôles critiques et aux suites larges du checkout.

```powershell
$acceptance = Get-Content acceptance.json -Raw | ConvertFrom-Json -AsHashtable
foreach ($proof in $acceptance.evidence) {
    $observed = (Get-FileHash -LiteralPath $proof.path -Algorithm SHA256).Hash
    if ($observed -ne $proof.sha256) { throw "Empreinte divergente $($proof.path)" }
}
if (@($acceptance.critical_checks.Values | Where-Object { $_ -ne 'PASS' }).Count) {
    $verdict = 'V3_INT2_NO_GO'
} elseif (@($acceptance.broad_checkout_checks.Values | Where-Object { $_ -ne 'PASS' }).Count) {
    $verdict = 'V3_INT2_CONDITIONAL'
} else {
    $verdict = 'V3_INT2_GO'
}
if ($verdict -ne $acceptance.verdict) { throw "Verdict divergent $verdict" }
$verdict
```
