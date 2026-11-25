# Rejouer le témoin logiciel V3-A.5

[Dossier de collecte](measurement_packet.md) · [Revue](review_protocol.md) ·
[Contrat](admission_contract.schema.json) · [Opération préalable](create_support_iso_readiness.json)

Compiler `convergence_manager` en C++17 avec Qt 6 Core et OpenSSL.
La recette Windows amd64 part de la branche A.5 et de la référence
[INT.1](../int1/acceptance.json). Fournir le chemin de l’exécutable
OpenSSL du même environnement pour la campagne `TEST_ONLY`. Le chemin
de confiance de ce témoin se trouve sous un nouveau dossier `.runtime`.

```powershell
$env:Path = 'C:/msys64/ucrt64/bin;' + $env:Path
$build = '.runtime/v3-a5-build'
cmake -S convergence_manager -B $build -G Ninja -DCMAKE_BUILD_TYPE=Release `
  -DCMAKE_PREFIX_PATH=C:/msys64/ucrt64 `
  -DPython3_EXECUTABLE=C:/msys64/ucrt64/bin/python.exe
cmake --build $build --parallel 4
ctest --test-dir $build -R 'a5|a4_material_evidence' --output-on-failure
```

Pour une demande déjà préparée, donner la copie XLink et la configuration de
confiance de test à l’opérateur du banc. Une sortie fraîche est requise.
Calculer le SHA-256 de la configuration fournie par le propriétaire du banc.

```text
convergence_core v3-admission --root <checkout> --request <demande.json>
  --sandbox <copie> --output <sortie-neuve> --a5-trust <confiance-test.json>
  --a5-trust-sha256 <empreinte-test>
```

Le témoin positif concerne la préadmission bornée d’une opération sur banc.
La consommation de la décision de test change l’état du registre local.
Conserver le reçu d’admission, le code retour et les empreintes des entrées.
Pour rejouer un scénario indépendant, préparer un jeu de données neuf et
des clés de test jetables. Les clés privées et les sources brutes restent
dans le dossier privé. Les refus gardent leur motif et zéro transaction.

La campagne physique commence par [les relevés de lot](measurement_packet.md)
et dépend du responsable habilité. Les autorisations publiques courantes
figurent dans [les décisions](authority_decisions.json).
