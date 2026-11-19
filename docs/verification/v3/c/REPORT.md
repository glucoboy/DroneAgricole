# V3-C — Rejouer la convergence sur banc XLink

[Résultat dans DOC-VAL](../../../VALIDATION_QUALIFICATION.md#cartographe-v3-c) ·
[Reçu](acceptance.json) · [Gel des outils](perturbation_freeze.json) · [Scénarios](generalization.json)

L3 rattache le problème de recherche au domaine scellé, aux octets du modèle
et à une observation FreeCAD. L5 refait cette mesure de référence sur une
copie. Le solveur échantillonne les translations à partir des bornes et de
la graine. Le parcours part des ports orientés, puis le criblage compare
l’enveloppe du câble aux solides observés. Le moteur explore un parcours
direct et des détours latéraux. Les obstacles signalés par le criblage
peuvent changer l’ordre des familles.

`v3-build` vérifie les bornes, la fermeture d’impact et la composition à
partir d’un [`v3.mutation_plan/2`](../../../electromechanical_v3/mutation_plan_v2.schema.json).
L’autorité fixe les rotations, les supports et les contraintes électriques.
La recherche varie la translation et la route. Les ancrages Workholding
ont chacun une seule valeur autorisée. Le classement compare les candidats
qui satisfont la contre-validation B.2, puis considère la longueur du
parcours et le dégagement de service. L’ordre des métriques et l’identifiant
du candidat départagent le front de Pareto.

## Exécuter le rejeu

Depuis la racine, compiler L3 et L5 en C++17/Qt6 avec CMake et Ninja. Employer
un dossier neuf sous `.runtime` et les outils indiqués dans les [régressions](regressions.json).

```powershell
$env:Path = 'C:/msys64/ucrt64/bin;' + $env:Path
$run = ".runtime/v3-c/replay-$([Guid]::NewGuid().ToString('N'))"
python -B convergence_manager/tests/replay_v3_c.py `
  --core .runtime/v3-c/qual-build/convergence_core.exe `
  --l3 .runtime/v3-c/l3/build/architecture_decision_core.exe `
  --freecad 'C:/Program Files/FreeCAD 1.1/bin/python.exe' `
  --python C:/msys64/ucrt64/bin/python.exe `
  --t0 .runtime/v3-a-regressions/build-t0/cartographe-evidence.exe `
  --output $run
```

La recette vérifie les SHA après T1, T2, T3 et T4. Le resserrement T2 est
choisi après T1 selon la règle gelée et garde le témoin de faisabilité.
Chaque phase conserve le problème L3, les observations, les traces et le
front calculé. Le reçu T0 de la phase identifie le dossier natif retenu.
Chaque fermeture admissible contient le document principal et toutes ses
dépendances. Les natifs et rapports bruts restent locaux. Un nouveau rejeu
produit de nouveaux identifiants de processus, dates et SHA d’archives.
