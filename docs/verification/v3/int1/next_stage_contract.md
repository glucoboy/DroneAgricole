# Passage V3-INT.1 vers V3-C.2 et V3-A.5

Version `v3.int1.next_stage/1`. La base des deux branches est la tête
de `codex/v3-int1-consolidation` dont le [reçu](acceptance.json)
établit `V3_INT1_GO`. Les deux branches s’ouvrent sur cette même tête.
Un verdict différent bloque leur lancement. Les contrôles de la fusion
et les reprises des entrées scellées restent possibles.

## V3-C.2 sur banc synthétique

Le [problème L3](../../../electromechanical_v3/problem_spec.schema.json)
porte le budget et les objectifs. Le [domaine](../../../electromechanical_v3/parametric_domain.schema.json)
gèle les variables, les opérations et leurs compositions. Le
[plan typé](../../../electromechanical_v3/mutation_plan_v2.schema.json)
fournit les valeurs contrôlées par L5. Conserver la lecture des profils C.1.

L’autorité synthétique nomme un profil et sa fermeture XLink. L5 construit
uniquement sur copie privée, puis B.2 mesure la copie rouvrable dans un
processus distinct. Le [reçu candidat](../../../electromechanical_v3/candidate_result.schema.json)
lie cette mesure et les critères au résultat T0. Les objectifs globaux et
par câble de C.2 devront être tirés de ce même candidat, avec des critères
de supportage et de collision déclarés dans le nouveau domaine. Cette
évolution est **Planifié** et dépend du banc synthétique.

## V3-A.5 et données de lot

L’import A.4 consomme un [paquet de mesure](../a4/measurement_form.schema.json)
et une politique remise séparément. Il expose l’état technique du dossier
et retourne `authority=DENY`. Une future revue habilitée signée est
**Planifié**. L’admission doit contrôler son émetteur et lier la décision
au lot, à la révision, au modèle scellé, à l’occurrence, à l’opération et
au domaine. Le chemin de test A.5 peut employer des données synthétiques
`TEST_ONLY`. La décision sur un lot réel dépend de sa preuve applicable.

## Cartographe

Le cartographe reste `READ_ONLY_IMPACT` et `cartographer_mutation=DENY`.
Une éventuelle V3-D.1 requiert une décision distincte. Une autorité A.5
applicable sera nécessaire pour une opération bornée sur copie privée.
La réception physique relève de son propre protocole.
