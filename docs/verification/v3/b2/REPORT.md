# V3 B.2 — Rejeu de la contre-validation XLink

[Résultat dans DOC-VAL](../../../VALIDATION_QUALIFICATION.md#cartographe-v3-b2) ·
[Reçu](acceptance.json) · [Exécutions](regressions.json) · [Mesures](native_replay.json).

| Contrôle | Contrat et portée |
|---|---|
| `v3_verify.py` | Validation native `v3.native_validation/1` après sauvegarde. Pose, topologie native, rayons, interférences, service et appui. Les préfixes `L2_` et `L4_` identifient les familles de contrôles. |
| `v3_cross_measure.py` | Observation `v3.cross_measurement/1` dans un nouveau processus FreeCAD. Fermeture, poses, continuité, rayons analytiques et BRep recomposés, distances et appuis. Les repères sont confrontés au profil scellé et les effets aux paramètres de l’opération. |
| `interconnection_core validate` | Dossier logique L0/L2 C4 et autorité d’interface séparée. Rejeu de l’oracle historique. Application directe à un FCStd `NOT_APPLICABLE`. |
| `validation_core xlink` | Projection `ADAPTED` du rayon nominal et de la paire câble/obstacle. Les portées des exclusions AABB, des autres paires de dégagement et de l’électricité sont indiquées par cas. |
| `cartographe-evidence validate` | Contrats T0, empreintes et finalisation à l’emplacement publié. |

## Reproduire sur Windows amd64

1. Compiler `convergence_manager` et `validation_engine` en C++17 suivant
   les commandes dans [les régressions](regressions.json). Rejouer CTest et
   ses gardes de chemins sur un poste autorisant les liens Windows privés.
2. Exécuter [`replay_v3_b1.py`](../../../../convergence_manager/tests/replay_v3_b1.py)
   avec les deux profils B.1 et le profil de variations B.2 épinglé. Utiliser
   son `replay.json` comme entrée de `replay_v3_b2.py`. Chaque cas produit une
   observation de référence, une observation candidate si sauvegardée, et
   un `candidate-result.json` compatible avec le schéma versionné.
3. Rejouer `test_v3_b1_boundary.py`, `test_v3_b2_evidence.py` et
   `test_v3_b2_native_faults.py`. Employer un nouveau dossier par exécution
   et prendre le C4 `PASS` du même rejeu pour les injections. Les copies
   modifiées et rejetées sont privées et consignées en quarantaine.
4. Exécuter `replay_v3_b2_legacy.py` pour la comparaison L4. Les oracles
   privés V2.1 Q1–Q3 demandent les témoins aux empreintes de la matrice
   historique. L2 attend les octets CRLF de son manifeste gelé.

Les commandes, natifs, observations détaillées et journaux de cette passe
sont conservés sous `.runtime/v3-b2`. Les SHA versionnés permettent de
vérifier leur identité. Le [contrat candidat](../../../electromechanical_v3/candidate_result.schema.json)
sert aux consommateurs de ces résultats de banc.
