# Résolution des conflits V3-INT.3

| Fichier | Décision enregistrée dans le merge A.6 | Contrôle reproductible |
|---|---|---|
| [.gitattributes](../../../../../.gitattributes) | Les deux règles LF sont conservées. Les règles INT.2.1 et des scellés historiques précèdent ces ajouts. | git check-attr text eol -- convergence_manager/tests/replay_v3_c3.py convergence_manager/tests/test_v3_a6_transactions.py |
| [v3_mutate.py](../../../../../convergence_manager/native/v3_mutate.py) | Le constructeur de l’obstacle C.3 précède la signature A.6 de mutate. Le test de portée du profil spatial précède l’ouverture. Le drapeau d’interruption reste dans la branche de sauvegarde native privée. | git diff HEAD^1 HEAD -- convergence_manager/native/v3_mutate.py |
| [V3Transaction.cpp](../../../../../convergence_manager/src/V3Transaction.cpp) | Le champ authorized_effect vient du seul contexte A.6 admis. Le schéma spatial conserve la branche multifaiseaux et transmet le contrat, l’obstacle contrôlé et l’exigence L4 spatiale. | git diff HEAD^2 HEAD -- convergence_manager/src/V3Transaction.cpp |
| [DOC-VAL](../../../../VALIDATION_QUALIFICATION.md) | Les deux sections et leurs entrées de journal sont conservées, avec les deux itérations C.3 et la limite de réception A.6. | git diff HEAD^1 HEAD -- docs/VALIDATION_QUALIFICATION.md |
| [DOC-SW](../../../../architecture/ARCHITECTURE_LOGICIELLE.md) | Les deux descriptions et les entrées de journal se suivent dans la section V3. | git diff HEAD^2 HEAD -- docs/architecture/ARCHITECTURE_LOGICIELLE.md |

Dans les commandes ci-dessus, HEAD désigne le merge testé de
[acceptance.json](acceptance.json).

La première fusion C.3 se termine sans conflit. La fusion explicite d’A.6
signale les cinq conflits ci-dessus. Git émet aussi un avertissement sur
le marqueur de conflit de .gitattributes pendant la fusion. La vérification
des attributs s’effectue après résolution et le diff final passe
git diff --check.

Dans v3_verify.py, la fusion automatique garde les contrôles de ports,
d’arcs, de collisions et d’obstacle de C.3, puis la mesure des cotes de
l’appui signé et de son engagement de solides pour A.6.
v3_cross_measure.py, spécifique au rejeu spatial et aux bancs historiques,
est identique à la source C.3. Le DOC-MEC est également repris de C.3.

La commande git diff --exit-code SOURCE MERGE -- docs/verification/v3/LOT
vérifie chaque jeu de reçus contre sa branche d’origine. La comparaison des
fichiers divergents et de leurs empreintes est dans
[merge_manifest.json](merge_manifest.json).
