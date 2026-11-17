# Reçu de validation L3

**L3_PASS** · `T-EM-ENGINE-L3` · Windows amd64 · 13 novembre 2026

Les deux rejeux nominaux ont validé 27 critères sur 27. Les 13 tests L3,
25 tests L2, 24 tests L1 et 73 tests de régression du moteur FreeCAD ont
réussi. Les deux dossiers T0, cinq projections L0 et le rapport L1
passent leurs validateurs. La revue indépendante a confirmé les refus
sur les mutations de graphe, de seuil, de classement et d’empreinte.

| Banc | Verdict |
|---|---|
| F31 / PM08–CAN1 | Détours supérieur et inférieur rejetés sur le service. Translation de PM08 admissible sur le banc. |
| F40/F41 | Deux échecs locaux déclenchent l’implantation et l’interface déportée. Le passif et le déplacement passent seuls. L’actif reste `INCONCLUSIVE`. |
| Décisions contradictoires | Consolidation rejetée à −3 mm de marge commune. Combinaison témoin admise. |
| Fiche inconnue | L1 `UNKNOWN`. Provenance de la fiche droite conservée. Variante latérale `INCONCLUSIVE` après trois essais de course. |
| Déplacement | Quatre liaisons réévaluées pour PM08 et quatre pour P75. |

## Commandes exécutées

```powershell
$build = '.runtime/l3_build'
cmake -S architecture_decision_engine -B $build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH=C:/msys64/ucrt64
cmake --build $build --parallel 4
ctest --test-dir $build --output-on-failure

$validator = '.runtime/l3_t0_validator'
cmake -S simulation -B $validator -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH=C:/msys64/ucrt64
cmake --build $validator --target cartographe-evidence
foreach ($runL3 in '.runtime/l3_reception','.runtime/l3_rejeu') {
    & "$build/architecture_decision_core.exe" --l1 "$build/research/technical_research_core.exe" --output $runL3
    & "$validator/cartographe-evidence.exe" validate $runL3 .
}

$env:ELECTROMECHANICAL_FREECAD_PYTHON = 'C:/Program Files/FreeCAD 1.1/bin/python.exe'
python -B -m unittest discover -s electromechanical_engine/tests -v
```

Le dossier local `.runtime/l3_reception/` contient la campagne, les
candidats, les décisions, la comparaison et le manifeste T0. Le rejeu
retrouve les décisions et mesures. Les horodatages L1 modifient les
empreintes des rapports qui les incorporent. Les 137 natifs actifs et
les 138 fichiers de la copie L0 concordent avec leurs empreintes initiales.
La compatibilité matérielle et la réalisation native des candidats L3
restent **À valider**.

[Preuve structurée](../verification/architecture_decision_l3.json) ·
[DOC-VAL](../VALIDATION_QUALIFICATION.md#moteur-electromecanique-v2-l3)
